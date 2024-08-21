# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from datetime import datetime, timedelta
import calendar

class HrOvertimePerMonth(models.Model):
    _name = 'hr.overtime.per.month'

    def _get_last_day_of_current_month(self):
        today = datetime.today()
        next_month = today.replace(day=28) + timedelta(days=4)  # this will never fail
        last_day = next_month - timedelta(days=next_month.day)  # subtract days to get the last day of the month
        return last_day.date()

    def _get_first_day_of_current_month(self):
        today = datetime.today()
        first_day = today.replace(day=1)
        return first_day.date()

    from_date = fields.Date(string='Period Start Date', default=lambda self: self._get_first_day_of_current_month())
    to_date = fields.Date(string='Period End Date', default=lambda self: self._get_last_day_of_current_month())
    overtime_hours = fields.Float(string='Working Hours')
    employee_id = fields.Many2one('hr.employee', string='Employee')


class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    def action_immediate_validate(self):
        for rec in self:
            if rec.state != 'draft':
                rec.action_draft()
            rec.action_confirm()
            rec.action_approve()
            rec.action_validate()

    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_number_of_days(self):
        super(HolidaysRequest, self)._compute_number_of_days()
        unpaid_holiday_status_id = self.env['hr.leave.type'].sudo().search([('name', '=', 'Unpaid')])
        for rec in self:
            if rec.holiday_status_id.id == unpaid_holiday_status_id.id:
                if rec.date_from and rec.date_to:
                    leave_start = rec.date_from.date()
                    leave_end = rec.date_to.date()

                    # Count the number of days in the intersection
                    rec.number_of_days = (leave_end - leave_start).days + 1
                else:
                    rec.number_of_days = 0


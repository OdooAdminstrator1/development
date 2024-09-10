# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from datetime import datetime, timedelta
import calendar

MONTHS_SELECTION = [
    ('1', 'JAN'),
    ('2', 'FEB'),
    ('3', 'MAR'),
    ('4', 'APR'),
    ('5', 'MAY'),
    ('6', 'JUN'),
    ('7', 'JUL'),
    ('8', 'AUG'),
    ('9', 'SEP'),
    ('10', 'OCT'),
    ('11', 'NOV'),
    ('12', 'DES')
 ]
YEARS_SELECTION = [
    ('2023', '2023'),
    ('2024', '2024'),
    ('2025', '2025'),
    ('2026', '2026'),
    ('2027', '2027'),
    ('2028', '2028'),
    ('2029', '2029'),
    ('2030', '2030')
]
class HrOvertimePerMonth(models.Model):
    _name = 'hr.overtime.per.month'

    def _get_default_month(self):
        today = datetime.today()
        return str(today.month)

    def _get_default_year(self):
        today = datetime.today()
        return str(today.year)

    implemented_month = fields.Selection(selection=MONTHS_SELECTION, default=_get_default_month, required=True)
    actual_month = fields.Selection(selection=MONTHS_SELECTION)
    implemented_year = fields.Selection(selection=YEARS_SELECTION, default=_get_default_year, required=True)
    actual_year = fields.Selection(selection=YEARS_SELECTION)
    from_date = fields.Date(string='Period Start Date')
    to_date = fields.Date(string='Period End Date')
    overtime_hours = fields.Float(string='Working Hours', )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)


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


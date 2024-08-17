# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from datetime import datetime, timedelta
import calendar

class HrOvertimePerMonth(models.Model):
    _name = 'hr.overtime.per.month'

    def _get_last_day_of_current_month(self):
        today = datetime.today()
        range = calendar.monthrange(today.year, today.month)
        first_day = today.replace(day=range[1])
        return first_day.date()

    def _get_first_day_of_current_month(self):
        today = datetime.today()
        range = calendar.monthrange(today.year, today.month)
        first_day = today.replace(day=range[0])
        return first_day.date()

    from_date = fields.Date(string='Period Start Date', default=lambda self: self._get_first_day_of_current_month())
    to_date = fields.Date(string='Period End Date', default=lambda self: self._get_last_day_of_current_month())
    overtime_hours = fields.Float(string='Working Hours')
    employee_id = fields.Many2one('hr.employee', string='Employee')


class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    def action_immediate_validate(self):
        for rec in self:
            rec.action_draft()
            rec.action_confirm()
            rec.action_approve()
            rec.action_validate()
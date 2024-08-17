# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrOvertimePerMonth(models.Model):
    _name = 'hr.overtime.per.month'

    from_date = fields.Date(string='Period Start Date')
    to_date = fields.Date(string='Period End Date')
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
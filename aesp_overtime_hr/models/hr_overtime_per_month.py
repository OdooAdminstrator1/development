# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrOvertimePerMonth(models.Model):
    _name = 'hr.overtime.per.month'

    from_date = fields.Date(string='Period Start Date')
    to_date = fields.Date(string='Period End Date')
    overtime_hours = fields.Float(string='Working Hours')
    employee_id = fields.Many2one('hr.employee', string='Employee')



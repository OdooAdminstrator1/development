from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, plaintext2html


class aespPaySlip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        res = super(aespPaySlip, self).action_payslip_done()
        self._action_create_account_move()
        group_by_account_id = {}
        total_debit = 0
        for line in self.move_id.line_ids.filtered(lambda a: a.debit > 0):
            if line.account_id.id in group_by_account_id.keys():
                group_by_account_id[line.account_id.id] += line.balance
                total_debit += line.balance
            else:
                group_by_account_id[line.account_id.id] = line.balance
                total_debit += line.balance

        partner_id = int(self.env['ir.config_parameter'].get_param('aesp_overtime_hr.payroll_vendor'))
        if not partner_id:
            raise UserError("Please Define Payroll Vendor Before From Setting")
        invoice_line_id = []
        for item in group_by_account_id.keys():
            invoice_line_id.append((0, 0, {
                'account_id': item,
                'price_unit': group_by_account_id[item]
            }))
        new_move_id = self.env['account.move'].create({
            'partner_id': partner_id,
            'move_type': 'in_invoice',
            'invoice_line_ids': invoice_line_id
        })
        self.move_id.unlink()
        self.move_id = new_move_id
        return res

    def _get_worked_day_lines_values(self, domain=None):
        result = super(aespPaySlip, self)._get_worked_day_lines_values(domain)
        result = self.correct_unpaid_work_day_line(result)
        work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'OPM')])
        emp_id = self.contract_id.employee_id
        hours = self.env['hr.overtime.per.month'].search([('employee_id', '=', emp_id.id),
                                                          ('from_date', '>=', self.date_from),
                                                          ('to_date', '<=', self.date_to),
                                                          ])
        result.append({
            'sequence': work_entry_type.sequence,
            'work_entry_type_id': work_entry_type.id,
            'number_of_days': 30,
            'number_of_hours': sum(hour.overtime_hours for hour in hours),
        })
        return result

    def correct_unpaid_work_day_line(self, result):
        unpaid_work_entry = self.env['hr.work.entry.type'].search([('code', '=', 'LEAVE90')])
        for item in result:
            if item['work_entry_type_id'] == unpaid_work_entry.id and item['number_of_days'] > 0:
                leaves = self.env['hr.leave'].search([('employee_id', '=', self.employee_id.id),
                                             ('state', '=', 'validate'),
                                             ('date_from', '<=', self.date_to),  # Leave starts before or on the end date
                                             ('date_to', '>=', self.date_from),
                                             ])
                total_leave_days = 0

                for leave in leaves:
                    # Calculate the actual days included in the period
                    leave_start = max(leave.date_from.date(), self.date_from)
                    leave_end = min(leave.date_to.date(), self.date_to)

                    # Count the number of days in the intersection
                    total_leave_days += (leave_end - leave_start).days + 1  # +1 to include both endpoints
                item['number_of_days'] = total_leave_days
        return result


class HrPayslipWorkedDaysInherited(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'contract_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        super(HrPayslipWorkedDaysInherited, self)._compute_amount()
        for worked_days in self.filtered(lambda wd: not wd.payslip_id.edited):
            if worked_days.code == 'OPM':
                emp_id = worked_days.contract_id.employee_id
                hours = self.env['hr.overtime.per.month'].search([('employee_id', '=', emp_id.id),
                                                          ('from_date', '>=', worked_days.payslip_id.date_from),
                                                          ('to_date', '<=', worked_days.payslip_id.date_to),
                                                          ])
                worked_days.amount = worked_days.contract_id.overtime_hour_wage * sum(hour.overtime_hours for hour in hours)


class HrContractInherited(models.Model):
    _inherit = 'hr.contract'

    overtime_hour_wage = fields.Float(string='Overtime Rate Per Hour')
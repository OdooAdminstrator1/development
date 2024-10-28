
import time
import babel
from odoo import models, fields, api, tools, _
from datetime import datetime


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    loan_line_id_17 = fields.Integer( string="Loan Installment", help="Loan installment")


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'



    def compute_sheet(self):
        for data in self:
            print("Data:", data)
            if (not data.employee_id) or (not data.date_from) or (not data.date_to):
                return
            if data.input_line_ids.input_type_id:
                data.input_line_ids = [(5, 0, 0)]

            loan_line = data.struct_id.rule_ids.filtered(
                lambda x: x.code == 'LO')


            if loan_line:
                get_amount = self.env['hr.loan'].search([
                    ('employee_id', '=', data.employee_id.id),
                    ('state', '=', 'delivered')
                ], limit=1)


                if get_amount:
                    for lines in get_amount:
                        for line in lines.loan_lines:
                            if data.date_from <= line.date <= data.date_to:
                                if not line.paid:
                                    if line.active:
                                        amount = line.amount
                                        name = loan_line.id
                                        loan = line.id
                                        check_lines = []
                                        new_name = self.env['hr.payslip.input.type'].search([
                                            ('code', '=', 'LO')])
                                        line = (0, 0, {
                                            'input_type_id': new_name.id,
                                            'amount': amount,
                                            'name': 'LO',
                                            'loan_line_id_17': loan
                                        })
                                        check_lines.append(line)
                                        data.write({'input_line_ids': check_lines})
                                        data.input_line_ids.loan_line_id_17 = loan
                                        # self.input_data_line(name, amount, loan)
        return super().compute_sheet()

    def action_payslip_done(self):
        for payslip in self:
            for l in payslip.input_line_ids:
                if l.loan_line_id_17:
                    line = self.env['hr.loan.line'].browse(l.loan_line_id_17)
                    line.paid = True
                    line.payslip_id = payslip.id
                    line.loan_id._compute_loan_amount()
        return super(HrPayslip, self).action_payslip_done()

    def input_data_line(self, name, amount, loan):
        for data in self:
            check_lines = []
            new_name = self.env['hr.payslip.input.type'].search([
                ('input_id', '=', name)])
            line = (0, 0, {
                'input_type_id': new_name,
                'amount': amount,
                'name': 'LO',
                'loan_line_id_17': loan
            })
            check_lines.append(line)
            data.write({'input_line_ids': check_lines})
            data.input_line_ids.loan_line_id_17 = loan


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    input_id = fields.Many2one('hr.salary.rule')


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    company_id = fields.Many2one('res.company', 'Company', copy=False, readonly=True, help="Comapny",
                                 default=lambda self: self.env.user.company_id)


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    company_id = fields.Many2one('res.company', 'Company', copy=False, readonly=True, help="Comapny",
                                 default=lambda self: self.env.user.company_id)


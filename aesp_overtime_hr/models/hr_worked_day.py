from odoo import api, fields, models


class aespPaySlip(models.Model):
    _inherit = 'hr.payslip'

    def _get_worked_day_lines_values(self, domain=None):
        result = super(aespPaySlip, self)._get_worked_day_lines_values(domain)
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
from datetime import date, datetime,timedelta
from odoo import api, fields, models
import calendar
from dateutil.relativedelta import relativedelta


#                raise ValidationError(_("This modification is not allowed in the current state."))


class HrContractInherited(models.Model):
    _inherit = "hr.contract"
    leave_status = fields.Selection([('totaly', 'Totaly'), ('partially', 'Partially'), ('none', 'None')],string='Status',compute='_compute_leave_status',)
    deserved_days=fields.Float("Deserved Time off Days",compute="_deserved_days")
    total_leaves=fields.Float("Total Paid Leaves",compute="_deserved_days")
    time_off_processing=fields.Boolean("Total Paid Leaves",compute="_contract_in_treatment", store=True)
    net_sal=fields.Monetary('Basic Salary',compute="_deserved_days",sorted=True )
    allowance=fields.Float('Allowance percent', default=1   )
    rest_time_off = fields.Monetary('Time Off Wage',compute="_deserved_days",sorted=True )
    invoice_id=fields.Many2one('account.move', 'Account Move')


    @api.depends('allowance')
    def _deserved_days(self):
        vacation_per_month = self.env['ir.config_parameter'].sudo().get_param('hr_paid_dayoff.vacation_per_month')
        startup_date = self.env['ir.config_parameter'].sudo().get_param('hr_paid_dayoff.startup_date')
        treat_date=fields.Date.to_date(startup_date) if startup_date else False
        for contract in self:
            deserved_days=0
            total_leaves=0
            net_sal=0
            rest_time_off=0
            if contract._contract_check(treat_date):
                contract_date_from=contract.date_start
                total_months=0
                total_months=self.months_between(contract_date_from,contract.date_end+timedelta(days=1))
                contract_date_to=contract_date_from+relativedelta(months=total_months)
                deserved_days=total_months*float(vacation_per_month) 
                total_leaves=contract._total_leaves(contract_date_from,contract_date_to,contract.employee_id.id)
                if total_leaves<deserved_days:
                   # net_salary = self._get_net_salary_via_salary_rules(contract)
                    net_sal = self._get_net_salary(contract) # contract.wage
                    rest_time_off=net_sal*(deserved_days-total_leaves)/30
                contract.deserved_days=deserved_days
                contract.total_leaves=total_leaves
                contract.net_sal=net_sal
                contract.rest_time_off=rest_time_off*contract.allowance


    def _compute_leave_status(self):
        for rec in self:
            rec.leave_status='none'

    def action_process_timeoff(self):
        self.ensure_one()
        partner_id = int(self.env['ir.config_parameter'].sudo().get_param('hr_paid_dayoff.emps_vac_vendor_id'))
        vals={
            'partner_id': partner_id,
            'move_type': 'in_invoice',
            'date': datetime.now().date(),
            'invoice_date': datetime.now().date(),
        }
        invoice  = self.env['account.move'].create(vals)
        line_vals = {
            'name': 'Paid time off',
            'quantity': 1,
            'price_unit': self.rest_time_off ,   # <-- Cost price
            'move_id': invoice.id,
        }
        self.env['account.move.line'].create(line_vals)
       # invoice._onchange_invoice_line_ids()
        self.invoice_id= invoice  

    def _contract_in_treatment(self):
        startup_date = self.env['ir.config_parameter'].sudo().get_param('hr_paid_dayoff.startup_date')
        treat_date=fields.Date.to_date(startup_date) if startup_date else False
        for rec in self:
            rec.time_off_processing= True
            if not (rec.state=='close'):
                rec.time_off_processing= False
            if rec.date_start>treat_date:
                rec.time_off_processing= False
            if not rec.date_end or treat_date>rec.date_end:
                rec.time_off_processing= False

    def _contract_check(self,treat_date):
        rec=self
        if not treat_date:
            return False
        if not (rec.state=='open' or rec.state=='close'):
            return False
        if rec.date_start>treat_date:
            return False
        if not rec.date_end or treat_date>rec.date_end:
            return False
        return True
            

    def _total_leaves(self,date_from, date_to,employee_id):
        leaves=self.env['hr.leave'].search([('employee_id','=',employee_id),('state', '=', 'validate'),
                                            ('holiday_status_id.name', '=', 'Paid Time Off'),
                                            ('date_from', '<=', date_to),('date_to', '>=', date_from)])
        total_days = sum(leaves.mapped('number_of_days'))
        return total_days

    def action_rest_time_off(self):
        # 1. Read the startup_date from config_parameter
        startup_date = self.env['ir.config_parameter'].sudo().get_param(
            'hr_paid_dayoff.startup_date'
        )
        if startup_date:
            startup_date = fields.Date.to_date(startup_date)

        # 2. Base domain
        domain = [('state', 'in', ['close'])]

        # 3. Add date range condition if startup_date exists
        if startup_date:
            domain.extend([
                ('date_start', '<=', startup_date),
                ('date_end', '>', startup_date)
            ])

        # 4. Return dynamic action
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rest of Time Off',
            'res_model': 'hr.contract',
            'views': [
                (self.env.ref('hr_paid_dayoff.view_contract_time_off').id, 'tree'),
                (self.env.ref('hr_paid_dayoff.view_contract_time_off_form').id, 'form')
            ],
            # 'view_mode': 'tree,form',
            # 'view_id': self.env.ref('hr_paid_dayoff.view_contract_time_off').id,
            'domain': domain,
        }

    def months_between(self,date1, date2):
        months = 0
        while True:
            # Get days in current month
            days_in_month = calendar.monthrange(date1.year, date1.month)[1]
            # Calculate start of next month
            next_month = date1 + timedelta(days=days_in_month)
            if next_month > date2:
                break
            months += 1
            if months==12:
                break
            date1 = next_month
        return months
    
    def _get_net_salary_via_salary_rules(self,  contract):
        """Simulate payslip computation using salary rules."""
        today = fields.Date.today()
        date_from = today.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)

        payslip = self.env['hr.payslip'].new({
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'date_from': date_from,
            'date_to': date_to,
            'struct_id': contract.structure_type_id.id,  # Link to the salary structure
        })

        payslip._compute_contract_id()
        payslip._compute_date_from()
        payslip._compute_date_to()
        
        # Compute the lines (this is the key method)
        payslip._compute_worked_days_line_ids()
        
        # Find the NET rule
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        
        if net_line:
            # Get the computed amount
            return net_line.amount
        else:
            # Fallback to sum of all lines with category 'NET'
            net_amount = sum(payslip.line_ids.filtered(
                lambda l: l.category_id.code == 'NET'
            ).mapped('total'))
            return net_amount

    def _get_net_salary(self,contract):
        """Return (basic + allowances) for this contract under normal conditions."""

        employee = contract.employee_id

        # 1. Determine date range (current month, but within contract dates)
        today = fields.Date.today()
        date_from = today.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        if date_from < contract.date_start:
            date_from = contract.date_start
        if date_to > (contract.date_end or date_to):
            date_to = contract.date_end or date_to

        # 2. Salary structure
        structure = contract.structure_type_id.default_struct_id or contract.struct_id
        if not structure:
            # Fallback: use basic wage only
            return contract.wage

        # 3. Get the main work entry type
        main_work_entry = self._get_main_work_entry_type(contract)
        if not main_work_entry:
            return contract.wage   # cannot compute without work entry type

        # 4. Compute standard working days/hours for the period
        calendar = contract.resource_calendar_id
        if not calendar:
            return contract.wage

        from_dt = datetime.combine(date_from, datetime.min.time())
        to_dt = datetime.combine(date_to, datetime.max.time())
        standard_hours = calendar.get_work_hours_count(from_dt, to_dt)   # no compute_leaves arg
        hours_per_day = calendar.hours_per_day or 8.0
        standard_days = standard_hours / hours_per_day if hours_per_day else 0.0

        # 5. Build worked days lines (only the main type, others get zero)
        WorkEntryType = self.env['hr.work.entry.type']
        all_types = WorkEntryType.search([])
        worked_lines = []
        for wet in all_types:
            worked_lines.append((0, 0, {
                'work_entry_type_id': wet.id,
                'code': wet.code or 'WORK100',
                'number_of_days': standard_days if wet == main_work_entry else 0.0,
                'number_of_hours': standard_hours if wet == main_work_entry else 0.0,
                'contract_id': contract.id,
            }))

        # 6. Create temporary payslip
        tmp_payslip = self.env['hr.payslip'].create({
            'name': f"Temp Simulation - {employee.name}",
            'employee_id': employee.id,
            'contract_id': contract.id,
            'struct_id': structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'worked_days_line_ids': worked_lines,
        })

        # 7. Force the payslip to use only this contract
        tmp_payslip.write({'contract_id': contract.id})   # ensure it's set

        # 8. Compute the sheet (this sets state='done' and fills line_ids)
        tmp_payslip.compute_sheet()

        # 9. Sum BASIC and ALW lines
        basic_total = sum(tmp_payslip.line_ids.filtered(lambda l: l.category_id.code == 'BASIC').mapped('total'))
        allowance_total = sum(tmp_payslip.line_ids.filtered(lambda l: l.category_id.name == 'Allowance').mapped('total'))
        net_base = basic_total + allowance_total

        # 10. Clean up
        tmp_payslip.button_cancel()   # sets state='cancel'
        tmp_payslip.unlink()

        return net_base

    def _get_main_work_entry_type(self,contract):
        """Helper to find the employee's primary work entry type."""
        employee = contract.employee_id
        # Option A: from employee (if you have a custom field)
        if hasattr(employee, 'work_entry_type_id') and employee.work_entry_type_id:
            return employee.work_entry_type_id
        # Option B: from the contract's calendar first attendance line
        calendar = contract.resource_calendar_id
        if calendar and calendar.attendance_ids:
            return calendar.attendance_ids[0].work_entry_type_id
        # Option C: search for a default work entry type (code = 'WORK100')
        return self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)

    def get_normal_net_salary(self, contract):
        """
        Return the normal monthly net salary for an employee
        ignoring absences, leaves and overtime.

        Works even if the contract is expired.
        """

        # Get latest contract (active or expired)

        if not contract:
            return 0.0

        structure = contract.structure_type_id.default_struct_id
        if not structure:
            return 0.0

        date_to = contract.date_end or datetime.today().date()
        date_from = contract.date_start if contract.date_start > date_to - relativedelta(months=1) else date_to - relativedelta(months=1) + relativedelta(days=1)

        # Create a temporary payslip
        payslip = self.env['hr.payslip'].new({
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': structure.id,
            'date_from': date_to,
            'date_to': date_from,
        })

        # Force worked days to a full month
        worked_days = [{
            'name': 'Normal Working Days',
            'sequence': 1,
            'code': 'WORK100',
            'number_of_days': 30,
            'number_of_hours': 240,
            'contract_id': contract.id,
        }]

        payslip.compute_sheet()
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        net_salary = sum(net_line.mapped('total'))
        payslip.write({'state': 'cancel'})
        payslip.unlink()  # remove temporary payslip


        return net_salary

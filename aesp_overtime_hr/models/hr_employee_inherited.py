from datetime import date
from datetime import timedelta
from odoo import api, fields, models
from odoo.osv import expression


class EmployeeInherited(models.Model):
    _inherit = "hr.employee"

    def _get_contracts(self, date_from, date_to, states=['open'], kanban_state=False):
        contracts = super(EmployeeInherited, self)._get_contracts(date_from, date_to, states, kanban_state)
        all_contract = []
        for emp in contracts.employee_id:
            valid_contracts = []
            emp_contract = contracts.filtered(lambda v: v.employee_id.id == emp.id)
            # same wage
            if len(set([item.wage for item in emp_contract])) != 1:
                continue
            for i in range(len(emp_contract)):
                current_contract = emp_contract[i]
                if i == 0:
                    valid_contracts.append(current_contract)
                else:
                    previous_contract = emp_contract[i - 1]

                    # Check for non-overlapping condition
                    if current_contract.date_start == previous_contract.date_end + timedelta(days=1):
                        valid_contracts = [current_contract]
                    else:
                        valid_contracts.append(current_contract)

            all_contract = all_contract + valid_contracts

        return contracts.filtered(lambda c: c.id in [item.id for item in all_contract])

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

    def _get_actual_contracts(self, date_from, date_to, states=['open'], kanban_state=False):
        state_domain = [('state', 'in', states)]
        if kanban_state:
            state_domain = expression.AND([state_domain, [('kanban_state', 'in', kanban_state)]])

        return self.env['hr.contract'].search(
            expression.AND([[('employee_id', 'in', self.ids)],
                            state_domain,
                            [('date_start', '<=', date_to),
                             '|',
                             ('date_end', '=', False),
                             ('date_end', '>=', date_from)]]))

    def check_for_contiguous_contract(self, date_from, date_to):
        self.ensure_one()
        contracts = self._get_actual_contracts(date_from, date_to, states=['open', 'close']).filtered(lambda c: c.active)
        emp_contracts = contracts.filtered(lambda v: v.employee_id.id == self.id)
        if len(set([item.wage for item in emp_contracts])) != 1:
            return False
        valid_contracts = []
        all_contract = []
        for i in range(len(emp_contracts)):
            current_contract = emp_contracts[i]
            if i == 0:
                valid_contracts.append(current_contract)
            else:
                previous_contract = emp_contracts[i - 1]

                # Check for non-overlapping condition
                if current_contract.date_start == previous_contract.date_end + timedelta(days=1):
                    valid_contracts = [current_contract]
                else:
                    valid_contracts.append(current_contract)

        if len(emp_contracts.ids) != len(valid_contracts):
            return True
        else:
            return False

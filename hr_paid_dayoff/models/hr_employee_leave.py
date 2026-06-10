from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError
import calendar
from typing import List

# Module hr_paid_dayoff

class EmployeeInherited(models.Model):
    _inherit = "hr.leave"
    deserved_days=fields.Float("Deserved perid",compute="_deserved_days")
    total_leaves=fields.Float("Total token",compute="_deserved_days")
    deserved_ratio = fields.Char(
        string="Total / Deserved",
        compute="_deserved_days",
    )
    leave_type_name = fields.Char(string='leave type', related='holiday_status_id.name',)

    @api.depends('date_from', 'date_to', 'employee_id','holiday_status_id')
    def _deserved_days(self):
        self.ensure_one()
        vacation_per_month =float( self.env['ir.config_parameter'].sudo().get_param('hr_paid_dayoff.vacation_per_month'))

        contracts=self.get_contract(self.date_from,self.employee_id.id)
        deserved_days=0
        total_leaves=0
        deserved_ratio='/'
        if contracts:
            contract=contracts[0]
            total_months=self.months_between(contract.date_start,self.date_from)
            deserved_days=total_months*float(vacation_per_month) 

            leaves=self._get_emp_leaves(contract.date_start,contract.date_end,self.employee_id.id)
            
            prev_leaves= leaves.filtered(lambda l: l.date_from < self.date_from)
            futur_leaves= leaves.filtered(lambda l: l.date_from > self.date_from).sorted(key=lambda l: l.date_from, reverse=True)
            total_leaves = sum(prev_leaves.mapped('number_of_days'))


            if not (total_leaves<deserved_days and len(futur_leaves)==0):
                max_leave = max(leaves, key=lambda l: l.date_from)
                lst_futute=create_monthly_allocation(contract.date_start,max_leave.date_from.date(),monthly_amount=vacation_per_month,deduct_total=max_leave.number_of_days)
                futur_leaves=futur_leaves-max_leave
                while len(futur_leaves)>0:
                    current=futur_leaves[0]
                    futur_leaves=futur_leaves-current
                    target_month=self.months_between(contract.date_start,current.date_from)
                    leftover = deduct_from_months_up_to(lst_futute, target_month=target_month, amount_to_take=current.number_of_days)
                    if leftover>0:
                        break
                
                deserved_days_future= sum(sublist[1] for sublist in lst_futute if sublist[0]  <= total_months)
                if deserved_days_future<deserved_days:
                    deserved_days=deserved_days_future

                

            if deserved_days:
                deserved_ratio = f"{total_leaves :.2f}/{deserved_days :.2f}"
            else:
                deserved_ratio = f"{total_leaves:.2f}/0.00"

        self.deserved_days=deserved_days
        self.total_leaves=total_leaves
        self.deserved_ratio=deserved_ratio


    @api.depends('date_from', 'date_to', 'employee_id','holiday_status_id')
    def _total_leaves(self,date_from, date_to):
        leaves=self.env['hr.leave'].search([('employee_id','=',self.employee_id.id),('state', '=', 'validate'),
                                            ('holiday_status_id.name', '=', 'Paid Time Off'),
                                            ('date_from', '<=', date_to),
                                            ('date_to', '>=', date_from)])
        total_days = sum(leaves.mapped('number_of_days'))
        return total_days


    def _get_emp_leaves(self,date_start, date_end,employee_id):
        domain=[('employee_id','=',employee_id),('state', '=', 'validate'),
                                            ('holiday_status_id.name', '=', 'Paid Time Off'),
                                            ('date_from', '>=', date_start)]
        if date_end:
            domain.extend([('date_from', '<', date_end)])
        leaves=self.env['hr.leave'].search(domain)
        return leaves


    def get_contract(self,date_from,employee_id):
        state_domain = [('state', 'in', ['open','close'])]

        return self.env['hr.contract'].search(
            expression.AND([[('employee_id', '=', employee_id)],
                            state_domain,
                            [('date_start', '<=', date_from),
                             '|',
                             ('date_end', '=', False),
                             ('date_end', '>=', date_from)]]))


    def months_between(self,date1, date2):
        months = 0
        while True:
            # Get days in current month
            days_in_month = calendar.monthrange(date1.year, date1.month)[1]
            # Calculate start of next month
            next_month = date1 + timedelta(days=days_in_month)
            if next_month > date2.date():
                break
            months += 1
            if months==12:
                break
            date1 = next_month
        return months


    def months_between2(self,date1, date2,quant,days):
        months_des = []
        months=0
        while True:
            # Get days in current month
            days_in_month = calendar.monthrange(date1.year, date1.month)[1]
            # Calculate start of next month
            next_month = date1 + timedelta(days=days_in_month)
            if next_month > date2:
                break
            months += 1
            months_des.extend([[months,quant]])
            date1 = next_month
        months_des.reverse()
        for k in months_des:
            if quant>=days:
                k[1]=quant-days
                break
            else:
                k[1]=0.0
                days=days-quant  
      
        return months_des 
   

    
    @api.constrains('number_of_days', 'total_leaves', 'deserved_days', 'holiday_status_id')
    def _check_leave_balance(self):
        """
        Ensure that for paid time off, the current leave duration plus total_taken does not exceed deserved_days.
        """
        for leave in self:
            # Only apply validation for paid time off types
            if leave.holiday_status_id.name != 'Paid Time Off':
                continue

            # Use 'number_of_days' as the leave duration (standard field in hr.leave)
            # If you use a custom duration field, replace it accordingly.
            duration = leave.number_of_days

            # Prevent validation if deserved_days is not yet computed or zero/negative
            if leave.deserved_days <= 0:
                # Option 1: skip if no entitlement (e.g., unpaid leave type)
                # Option 2: raise error if a positive duration is requested with zero balance
                if duration > 0:
                    raise ValidationError(_(
                        "You have no entitled days (%s) for this paid time off type. "
                        "Cannot request a leave." % leave.deserved_days
                    ))
                continue

            remaining = leave.deserved_days - leave.total_leaves
            if duration > remaining:
                raise ValidationError(_(
                    "Insufficient balance.\n"
                    "Requested duration: %(duration).2f days\n"
                    "Already taken (total_leaves): %(taken).2f days\n"
                    "Total entitled: %(entitled).2f days\n"
                    "Remaining: %(remaining).2f days\n"
                    "This leave request exceeds your remaining balance by %(excess).2f days.",
                    duration=duration,
                    taken=leave.total_leaves,
                    entitled=leave.deserved_days,
                    remaining=remaining,
                    excess=duration - remaining
                ))


    # def action_validate(self):
    #     # Add custom validation logic here

    #     for record in self:
    #         if record.holiday_status_id.is_paid==True:
    #                 pass

    #     return super().action_validate()

def create_monthly_allocation(
    start_date: date,
    end_date: date,
    monthly_amount: float,
    deduct_total: float
) -> List[List]:
    """
    Build a list of months between start_date and end_date (exclusive of end_date's month).
    Each month starts with `monthly_amount`. Then deducts `deduct_total` from the
    latest months backward (like consuming from the end).

    Returns a list of [month_index, amount] in ascending month order (month 1 = first month).
    If deduct_total exceeds total allocation, all amounts become 0.
    """
    # Build month list in ascending order
    months = []
    current = start_date
    month_num = 1
    while True:
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        next_month = current + timedelta(days=days_in_month)
        if next_month > end_date:
            break
        months.append([month_num, monthly_amount])
        current = next_month
        month_num += 1

    if not months:
        return months

    # Apply backward deduction (from the last month to the first)
    remaining_deduction = deduct_total
    for i in range(len(months) - 1, -1, -1):
        if remaining_deduction <= 0:
            break
        available = months[i][1]
        if available <= remaining_deduction:
            months[i][1] = 0.0
            remaining_deduction -= available
        else:
            months[i][1] = available - remaining_deduction
            remaining_deduction = 0.0

    # If something remains, we've exhausted all months; all are already zero.
    return months


def deduct_from_months_up_to(
    monthly_data: List[List],
    target_month: int,
    amount_to_take: float
) -> float:
    """
    Deduct `amount_to_take` from months with index <= target_month,
    starting from the highest index (closest to target_month) backwards.
    Modifies the list in place.

    Returns the amount that could NOT be deducted (0 if fully taken).
    """
    remaining = amount_to_take
    # Traverse from the last month down to the first, but only those <= target_month
    for i in range(len(monthly_data) - 1, -1, -1):
        month_idx, current_amount = monthly_data[i]
        if month_idx > target_month:
            continue
        if remaining <= 0:
            break
        if current_amount <= remaining:
            monthly_data[i][1] = 0.0
            remaining -= current_amount
        else:
            monthly_data[i][1] = current_amount - remaining
            remaining = 0.0
    return remaining

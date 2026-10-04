from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    open_date_id = fields.Many2one('distribution.open.date', string='Open Date')
    distributor_id = fields.Many2one('hr.employee', string='Distributor', domain=[('isdistributor', '=', True)])

    def _check_cash_user_authorization(self):
        for payment in self:
            # Check if the payment belongs to a Cash type journal
            if payment.journal_id and payment.journal_id.type == 'cash':
                # If authorized users are defined, enforce the restriction rule
                if payment.journal_id.cash_user_ids and self.env.user not in payment.journal_id.cash_user_ids:
                    raise ValidationError(_(
                        "Access Denied!\n"
                        "Your user account (%s) is not registered as an authorized operator "
                        "for the cash journal '%s'. Please contact your administrator."
                    ) % (self.env.user.name, payment.journal_id.name))

    def action_post(self):
        # Execute Odoo's standard accounting entry generation first
        res = super(AccountPayment, self).action_post()

        for payment in self:
            # Locate all Pre-Invoices linked to this specific validated payment record
            pre_invoices = self.env['distribution.pre.invoice'].search([('payment_id', '=', payment.id)])
            
            if pre_invoices:
                # 1. Enforce safety validation checks
                expected_total = sum(pre_invoices.mapped('received_amount'))
                if payment.amount != expected_total:
                    raise ValidationError(
                        f"Validation Error: Payment amount ({payment.amount}) does not match "
                        f"the sum of Received Amounts ({expected_total}) of the linked pre-invoices."
                    )
                
                if any(inv.distributor_id != payment.distributor_id for inv in pre_invoices):
                    raise ValidationError("Validation Error: Selected pre-invoices must belong to the payment's distributor.")

                # 2. Process financial balances on successful validation
                for inv in pre_invoices:
                    inv.posted_amount += inv.received_amount
                    inv.received_amount = 0.0
                    
                    # Compute remaining balance to calculate state adjustments
                    remaining_balance = inv.total_value - inv.posted_amount
                    if remaining_balance <= 0:
                        inv.state = 'paid'
                    else:
                        inv.state = 'partially_paid'

                # 3. Check if all Pre-Invoices for the Open-Date session are 'paid'
                if payment.open_date_id:
                    all_session_invoices = self.env['distribution.pre.invoice'].search([
                        ('open_date_id', '=', payment.open_date_id.id)
                    ])
                    # If everything in this active session is complete, auto-close the session
                    if all_session_invoices and all(inv.state == 'paid' for inv in all_session_invoices):
                        payment.open_date_id.write({
                            'status': 'close',
                            'close_date': fields.Date.context_today(self)
                        })
        return res
    



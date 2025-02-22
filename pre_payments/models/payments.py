from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

# class payments(models.Model):
#     _inherit = "account.payment"
#     advance_ok = fields.Boolean(
#         string='advanced Payment',
#         help="Select if you want to establish a features of advance")
#     can_close=fields.Boolean(string='advanced Payment',compute="_can_close")
    


#     def _can_close(self):
#         lines = self.move_id.line_ids.filtered(lambda line: not line.reconciled and line.account_id.advanced)


#         if lines and self.advance_ok and lines[0].amount_residual>0.0  :
#             self.can_close=True
#         else:
#             self.can_close=False
#         return  self.can_close
    
#     @api.depends('journal_id', 'payment_type', 'payment_method_line_id','advance_ok')
#     def _compute_outstanding_account_id(self):
#         for pay in self:
#             if not pay.advance_ok:
#                 pass
#             else:
#                 if pay.payment_type == 'inbound':
#                     pay.outstanding_account_id = (pay.payment_method_line_id.payment_account_id
#                                                 or pay.journal_id.company_id.account_journal_payment_debit_account_id)
#                 elif pay.payment_type == 'outbound':
#                     pay.outstanding_account_id = (pay.payment_method_line_id.payment_account_id
#                                                 or pay.journal_id.company_id.account_journal_payment_credit_account_id)
#                 else:
#                     pay.outstanding_account_id = False
#                 print('--------outstanding_account_id1-------'+str(pay.outstanding_account_id) )

#     @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer','advance_ok')
#     def _compute_destination_account_id(self):
#         self.destination_account_id = False
#         for pay in self:
#             if not pay.advance_ok or pay.is_internal_transfer:
#                 super(payments, pay)._compute_destination_account_id()
#             else:
#                 # if pay.is_internal_transfer:
#                 #     pay.destination_account_id = pay.journal_id.company_id.transfer_account_id
#                 if pay.partner_type == 'customer':
#                     # Receive money from invoice or send money to refund it.
#                     if pay.partner_id:
#                         pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_advacc_receivable_id.id 
#                     else:
#                         pay.destination_account_id = self.env['account.account'].search([
#                             ('company_id', '=', pay.company_id.id),
#                             ('internal_type', '=', 'receivable'),
#                             ('deprecated', '=', False),
#                         ], limit=1)
#                 elif pay.partner_type == 'supplier':
#                     # Send money to pay a bill or receive money to refund it.
#                     if pay.partner_id:
#                         pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_advacc_payable_id.id
#                     else:
#                         pay.destination_account_id = self.env['account.account'].search([
#                             ('company_id', '=', pay.company_id.id),
#                             ('internal_type', '=', 'payable'),
#                             ('deprecated', '=', False),
#                         ], limit=1)
#                 print('--------destination_account_id1-------'+str(pay.destination_account_id) )



class AccountPayment(models.Model):
    _inherit = "account.payment"

    advance_ok = fields.Boolean(
        string='advanced Payment',
        help="Select if you want to establish a features of advance")
    taxes = fields.Many2many("account.tax", string="Customer Taxes", 
                             help="Taxes used for payments")
    is_taxed=fields.Boolean(compute='_is_taxed',  readonly=True)
    total_tax_amount = fields.Monetary(string='Total Tax Amount', compute='_compute_total_tax_amount', store=True, readonly=True)

    @api.depends('amount', 'taxes', 'advance_ok', 'payment_type')
    def _is_taxed(self):
        for pay in self:
            pay.is_taxed= pay.taxes and pay.advance_ok and pay.payment_type=='inbound'
    


    @api.depends('amount', 'taxes', 'advance_ok', 'payment_type')
    def _compute_total_tax_amount(self):
        for payment in self:
            total_tax = 0.0
            if payment.taxes and payment.advance_ok and payment.payment_type=='inbound':
                for tax in payment.taxes:
                    tax_computation = tax.compute_all(payment.amount, currency=payment.currency_id, partner=payment.partner_id)
                    total_tax += tax_computation.get('total_included', 0.0) - tax_computation.get('total_excluded', 0.0)
            payment.total_tax_amount = total_tax
    

    @api.model
    def create(self, vals):
        # if self.is_taxed:
        #     self.amount -= self.total_tax_amount
        payment = super(AccountPayment, self).create(vals)
        

        # Add the total tax to the payment amount
        

        # Handle journal entries based on payment type (advance payment vs regular payment)
        # payment._create_journal_entries()
        return payment
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        line_vals_list=super(AccountPayment,self)._prepare_move_line_default_vals(write_off_line_vals)
        if self.is_taxed:
            tax_account=0
            tx_amount=self.total_tax_amount
            for tax in self.taxes:
                    tax_account = tax.invoice_repartition_line_ids.account_id
            for line in line_vals_list:
                if line['credit']!=0:
                    line['credit']=line['credit']-tx_amount
            line_vals_list.append({
                'name':  f'Advance payment for ',
                'debit': 0,
                'credit': tx_amount,
                'partner_id': self.partner_id.id,
                'account_id': tax_account.id,
            })
        return line_vals_list 


    def _create_journal_entries(self):
        for payment in self:


            # Handle journal entries for advance payments (prepayments)
            if payment.is_taxed and payment.move_id:
                # For advance payments, create the prepayment journal entry first
                # prepayment_account = payment._compute_destination_account_id()
                
                # if not prepayment_account:
                #     raise UserError("No prepayment account set in the journal.")
                tax_account=0
                for tax in payment.taxes:
                    tax_account = tax.invoice_repartition_line_ids.account_id
                if not tax_account:
                    raise UserError(f"Tax account not found for tax {tax.name}")

                # Compute the total tax for this payment using Odoo's tax calculation method
                # tax_computation = tax.compute_all(payment.amount, currency=payment.currency_id, partner=payment.partner_id)
                # tax_amount = tax_computation.get('total_included', 0.0) - tax_computation.get('total_excluded', 0.0)

                journal_entry_vals = {
                    'payment_id': payment.id,
                    'line_ids': [
                    
                        (0, 0, {
                            'account_id': payment.journal_id.default_account_id.id,
                            'debit': payment.amount,
                            'credit': 0.0,
                            'name': f'Advance payment for {payment.payment_reference}',
                            'partner_id': payment.partner_id.id,
                        }),
                        (0,0,{
                            'account_id': tax_account.id,
                            'credit': payment.total_tax_amount,
                            'debit': 0.0,
                            'name': f'Advance payment for {payment.payment_reference}',
                            'partner_id': payment.partner_id.id,
                            # 'move_id': payment.move_id.id,
                        }),
                        (0, 0, {
                            'account_id': payment.destination_account_id.id, # prepayment_account.id,
                            'credit': payment.amount- payment.total_tax_amount,
                            'debit': 0.0,
                            'name': f'Advance payment for {payment.payment_reference}',
                            'partner_id': payment.partner_id.id,
                        }),
                    ]
                }
               
                # Create the journal entry for advance payment
                move = self.env['account.move'].create(journal_entry_vals)

                # Now calculate and post taxes for the advance payment
                
                # self._create_tax_entries(payment, payment.move_id)



    def _create_tax_entries(self, payment, move=None):
        if payment.is_taxed:
            for tax in payment.taxes:
                tax_account = tax.invoice_repartition_line_ids.account_id
                if not tax_account:
                    raise UserError(f"Tax account not found for tax {tax.name}")

                # Compute the total tax for this payment using Odoo's tax calculation method
                tax_computation = tax.compute_all(payment.amount, currency=payment.currency_id, partner=payment.partner_id)
                tax_amount = tax_computation.get('total_included', 0.0) - tax_computation.get('total_excluded', 0.0)

                # Create journal entries for tax
                
                new_line_1 = {
                            'account_id': tax_account.id,
                            'credit': tax_amount,
                            'debit': 0.0,
                            'name': f'Tax for payment {payment.payment_reference} ({tax.name})',
                            'partner_id': payment.partner_id.id,
                            'move_id': move.id,
                }
                new_line_2 = {
                            'account_id': payment.outstanding_account_id.id,
                            'debit': tax_amount,
                            'credit': 0.0,
                            'name': f'Tax for payment {payment.payment_reference} ({tax.name})',
                            'partner_id': payment.partner_id.id,
                            'move_id': move.id,
                        }


                # Create the journal entry for tax (use the existing move if it's an advance payment, else create a new one)
                if move:
                    move.write({
                       'line_ids': [(4, new_line_1), (4, new_line_2)]  # Add the newly created lines to the existing move
                    })
                # self.env['account.move'].create(journal_entry_vals)

    
    @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer')
    def _compute_destination_account_id(self):

        self.destination_account_id = False
        for pay in self:
            if pay.is_internal_transfer:
                pay.destination_account_id = pay.journal_id.company_id.transfer_account_id
            elif pay.partner_type == 'customer':
                # Receive money from invoice or send money to refund it.
                if pay.partner_id:
                    if pay.advance_ok:
                        if not pay.partner_id.advance_account_receivable_id:
                            raise UserError('There is no Advance Account For This customer')
                        pay.destination_account_id = pay.partner_id.advance_account_receivable_id.id
                    else:
                        pay.destination_account_id = pay.partner_id.with_company(
                            pay.company_id).property_account_receivable_id
                else:
                    pay.destination_account_id = self.env['account.account'].search([
                        ('company_id', '=', pay.company_id.id),
                        ('internal_type', '=', 'receivable'),
                        ('deprecated', '=', False),
                    ], limit=1)
            elif pay.partner_type == 'supplier':
                # Send money to pay a bill or receive money to refund it.
                if pay.partner_id:
                    if pay.advance_ok:
                        if not pay.partner_id.advance_account_payable_id:
                            raise UserError('There is no Advance Account For This Vendor')
                        pay.destination_account_id = pay.partner_id.advance_account_payable_id.id
                    else:
                        pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_account_payable_id
                else:
                    pay.destination_account_id = self.env['account.account'].search([
                        ('company_id', '=', pay.company_id.id),
                        ('internal_type', '=', 'payable'),
                        ('deprecated', '=', False),
                    ], limit=1)

    def _synchronize_from_moves(self, changed_fields):
        not_advance_count = self.with_context(skip_account_move_synchronization=True).filtered(lambda v: v.advance_ok != True)
        if len(not_advance_count) > 0:
            return super(AccountPayment, self)._synchronize_from_moves(changed_fields)
        else:
            return
from odoo import models, fields, api, Command
from odoo.exceptions import UserError

class AccountPayment(models.Model):
    _inherit = "account.payment"

    advance_ok = fields.Boolean(
        string='Advanced Payment',
        help="Select if you want to establish a features of advance")
    
    taxes = fields.Many2many(
        "account.tax", 
        string="Customer Taxes", 
        help="Taxes used for payments")
    
    is_taxed = fields.Boolean(compute='_compute_is_taxed', readonly=True)
    
    total_tax_amount = fields.Monetary(
        string='Total Tax Amount', 
        compute='_compute_total_tax_amount', 
        store=True, 
        readonly=True)
    
    total_payment = fields.Monetary(
        string='Total Payment', 
        compute='_compute_total_payment', 
        store=True, 
        readonly=True)

    @api.depends('amount', 'taxes', 'advance_ok', 'payment_type')
    def _compute_is_taxed(self):
        for pay in self:
            pay.is_taxed = pay.taxes and pay.advance_ok and pay.payment_type == 'inbound'

    @api.depends('amount', 'taxes', 'advance_ok', 'payment_type')
    def _compute_total_tax_amount(self):
        for payment in self:
            total_tax = 0.0
            if payment.is_taxed:
                # Odoo 16 compute_all returns a dictionary including 'taxes' list
                tax_values = payment.taxes.compute_all(
                    payment.amount, 
                    currency=payment.currency_id, 
                    partner=payment.partner_id
                )
                total_tax = tax_values.get('total_included', 0.0) - tax_values.get('total_excluded', 0.0)
            payment.total_tax_amount = total_tax

    @api.depends('amount', 'total_tax_amount')
    def _compute_total_payment(self):
        for payment in self:
            payment.total_payment = payment.amount + payment.total_tax_amount

    @api.onchange('advance_ok')
    def _onchange_advance_ok(self):
        self.ensure_one
        if self.payment_type == 'inbound' and self.advance_ok:
            # Using Odoo 16 suggested sale tax from company
            tax_id = self.company_id.account_sale_tax_id
            if tax_id and not self.taxes:
                self.taxes = [Command.set(tax_id.ids)]

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        """
        Injects the tax line into the payment's journal entry.
        """
        line_vals_list = super()._prepare_move_line_default_vals(write_off_line_vals)
        
        if self.is_taxed and self.total_tax_amount > 0:
            tx_amount = self.total_tax_amount
            tax_account = self.taxes.invoice_repartition_line_ids.filtered(lambda l: l.account_id).account_id
            tx_amount_currency=self.currency_id._convert(
                        tx_amount,
                        self.company_id.currency_id,
                        self.company_id,
                        self.date,
                    )
            if not tax_account:
                return

            # Adjust existing lines to include tax in the liquidity/destination balance
            for line in line_vals_list:
                if line.get('debit', 0.0) > 0:
                    line['debit'] += tx_amount
                    new_amount_currency=self.currency_id._convert(
                        line['debit'],
                        self.company_id.currency_id,
                        self.company_id,
                        self.date,
                    )
                    if line.get('amount_currency'):
                        line['amount_currency'] =new_amount_currency


            # Append the dedicated tax line
            line_vals_list.append({
                'name': f'Advance Tax payment from {self.partner_id.name}',
                'currency_id' : self.currency_id.id,
                'amount_currency' : -tx_amount_currency,
                'debit': 0.0,
                'credit': tx_amount,
                'partner_id': self.partner_id.id,
                'account_id': tax_account[0].id, # Use first available tax account
            })
            
        return line_vals_list

    @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer', 'advance_ok')
    def _compute_destination_account_id(self):
        """
        Odoo 16 uses account_type instead of internal_type.
        """
        super()._compute_destination_account_id()
        for pay in self:
            if pay.is_internal_transfer:
                continue
            
            if pay.advance_ok and pay.partner_id:
                if pay.partner_type == 'customer':
                    if not pay.partner_id.advance_account_receivable_id:
                        raise UserError('There is no Advance Account For This customer')
                    pay.destination_account_id = pay.partner_id.advance_account_receivable_id
                
                elif pay.partner_type == 'supplier':
                    if not pay.partner_id.advance_account_payable_id:
                        raise UserError('There is no Advance Account For This Vendor')
                    pay.destination_account_id = pay.partner_id.advance_account_payable_id

    def _synchronize_from_moves(self, changed_fields):
        # Optimized filter for Odoo 16
        if all(self.mapped('advance_ok')):
            return
        return super()._synchronize_from_moves(changed_fields)

    def action_post(self):
        ''' draft -> posted '''
        moveid=self.move_id
        moveid._post(soft=False)
        self.filtered(
            lambda pay: pay.is_internal_transfer and not pay.paired_internal_transfer_payment_id
        )._create_paired_internal_transfer_payment()
        if self.is_taxed:
            for mv in self.move_id.line_ids:
                if mv.account_id.advanced:
                    if mv.amount_residual>0:
                        mv.amount_residual=self.total_tax_amount+mv.amount_residual
                        mv.amount_residual_currency=self.total_tax_amount+mv.amount_residual
                    else:
                        mv.amount_residual=mv.amount_residual-self.total_tax_amount
                        mv.amount_residual_currency=mv.amount_residual



                    
                    # if self.is_taxed:
                    #     if mv.amount_residual>0:
                    #         mv.amount_residual=self.total_tax_amount+mv.amount_residual
                    #         mv.amount_residual_currency=self.total_tax_amount+mv.amount_residual
                    #     else:
                    #         mv.amount_residual=mv.amount_residual-self.total_tax_amount
                    #         mv.amount_residual_currency=mv.amount_residual
                    # else:
                    #         mv.amount_residual=abs(mv.balance)
                    #         mv.amount_residual_currency=mv.amount_residual
    


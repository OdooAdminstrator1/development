
from odoo import models, api, fields

class AccountPayment(models.Model):
    _inherit = "account.payment"
    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order',
        domain="[('partner_id', '=', partner_id)]",
    )

    @api.onchange('payment_type', 'advance_ok')
    def _onchange_payment_type_advance(self):
        # Clear production_order_id if conditions are not met
        if not (self.payment_type == 'inbound' and self.advance_ok):
            self.production_order_id = False

class ProductionOrderExt(models.Model):
    _inherit = "production.order"

    adv_payment = fields.Float(
        string='Adv Payment',
        compute='_compute_invoice_totals',
        store=False,
    )

    def _compute_invoice_totals(self):
        for record in self:
            # Get all sale orders linked to this production order
            sale_orders = self.env['sale.order'].search([
                ('production_order_id', '=', record.id)
            ])

            untaxed_sum = 0.0
            paid_untaxed_sum = 0.0
            tax_sum = 0.0
            paid_total = 0.0
            adv_payment=0.0
            adv_payment_debit=0
          #  partner_c = self.env['res.partner'].browse(record.partner_id.advance_account_receivable_id.id)
            adv_customer_acc_payment_id = record.partner_id.advance_account_receivable_id.id
           # adv_customer_acc_payment_id=record.partner_id.advance_account_receivable_id.id
            payments= self.env['account.payment'].search([('advance_ok','=',True),('is_reconciled','=',False),('production_order_id','=',record.id),('state','=','posted'),('partner_id','=',record.partner_id.id)]) 
            for p in payments:
                adv_payment+=p.amount
            
            move_payments=self.env['account.move'].search([('advanced_payment','in',payments.ids)])
            if len(move_payments)>0:
                conceille_payments=self.env['account.move.line'].search([('move_id','in',move_payments.ids),('debit','>',0),('account_id','=',adv_customer_acc_payment_id)])
                for ml in conceille_payments:
                    adv_payment_debit+=ml.debit
            adv_payment=adv_payment-adv_payment_debit

            for sale in sale_orders:
                # Only consider posted invoices
                # filtered_payments=None
                # if sale.production_order_id:
                #     filtered_payments = payments.filtered(lambda p: p.production_order_id.id == sale.production_order_id.id)
                #     for p in filtered_payments:
                #         adv_payment+=p.amount

                posted_invoices = sale.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                for inv in posted_invoices:
                    untaxed = inv.amount_untaxed
                    total = inv.amount_total
                    tax = total - untaxed   # total tax amount
                    paid_total += inv.amount_total - inv.amount_residual

                    untaxed_sum += untaxed
                    tax_sum += tax

                    # Proportional paid amount (excl. tax)
                    if total != 0:
                        paid_proportion = (total - inv.amount_residual) / total
                        paid_untaxed_sum += untaxed * paid_proportion
                    # else: if total is zero, paid_untaxed remains unchanged
            record.total_invoiced_untaxed = untaxed_sum
            record.to_be_invoiced =record.expected_revenue - untaxed_sum
            record.total_paid_untaxed = paid_untaxed_sum+adv_payment
            record.total_paid =paid_total
            record.total_tax = tax_sum
            record.adv_payment=adv_payment

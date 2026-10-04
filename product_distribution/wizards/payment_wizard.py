from odoo import models, fields, api
from odoo.exceptions import ValidationError,UserError

class DistributionPaymentWizard(models.TransientModel):
    _name = 'distribution.payment.wizard'
    _description = 'Pre-Invoice Payment Wizard'

    payment_amount = fields.Float(string='Payment Amount Received', required=True)
    date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)

    @api.model
    def default_get(self, fields_list):
        """ Automatically populates the wizard input field with the aggregate selection value """
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids')
        if active_ids:
            pre_invoices = self.env['distribution.pre.invoice'].browse(active_ids)
            res['payment_amount'] = sum(pre_invoices.mapped('received_amount'))
        return res

    def action_register_payment(self):
        active_ids = self.env.context.get('active_ids')
        pre_invoices = self.env['distribution.pre.invoice'].browse(active_ids)
        
        if not pre_invoices:
            raise ValidationError("Please select at least one pre-invoice record to process payment.")

        # Core Rule Checks
        distributor = pre_invoices[0].distributor_id
        open_date = pre_invoices[0].open_date_id
        
        if any(inv.distributor_id != distributor for inv in pre_invoices):
            raise ValidationError("All selected pre-invoices must belong to the same distributor.")
            
        if any(inv.open_date_id != open_date for inv in pre_invoices):
            raise ValidationError("All selected pre-invoices must originate from the same Open-date session.")

        expected_total = sum(pre_invoices.mapped('received_amount'))
        if self.payment_amount != expected_total:
            raise ValidationError(
                f"The Payment amount ({self.payment_amount}) must exactly equal the sum of "
                f"the Received Amount ({expected_total}) of the selected pre-invoices."
            )

        # Retrieve default customer from settings (falls back to main company profile record)
        customer_id = self._get_general_customer()

        # Build structural mapping arrays for native Odoo Payment Object creation
        payment_vals = {
            'amount': self.payment_amount,
            'date': self.date,
            'partner_id': customer_id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'open_date_id': open_date.id if open_date else False,
            'distributor_id': distributor.id if distributor else False,
        }
        
        # Pull first valid bank/cash accounting journal context definition
        journal = self.env['account.journal'].search([('type', 'in', ('bank', 'cash'))], limit=1)
        if journal:
            payment_vals['journal_id'] = journal.id

        # 1. Create the new Payment Object record
        payment = self.env['account.payment'].create(payment_vals)

        # 2. Map Payment ID reference mapping onto all targeted Pre-Invoices
        pre_invoices.write({'payment_id': payment.id})

        # Redirect user immediately to view the newly compiled Draft Payment record
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }


    def _get_general_customer(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_distribution.default_general_customer_id')
        partner = self.env['res.partner'].browse(int(value)) if value else self.env['res.partner']
        if not partner.exists():
            raise UserError("The general distribution customer is not configured in Settings.")
        return partner
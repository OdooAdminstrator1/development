from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from datetime import  datetime
import json
import qrcode
from io import BytesIO
import base64

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from datetime import datetime
import json
import qrcode
from io import BytesIO
import base64

class AccountAccount(models.Model):
    _inherit = 'account.account'

    advanced = fields.Boolean(index=True, default=False, string="Advanced Account")

    @api.constrains('account_type', 'advanced')
    def _check_advanced_account_type(self):
        for record in self:
            if record.advanced and record.account_type not in ('asset_current', 'liability_current'):
                raise ValidationError(_('Advanced Account must be of type "Current Assets" or "Current Liabilities".'))

class AccountMove(models.Model): # Use models.Model for standard inheritance
    _inherit = "account.move"

    advanced_payment = fields.Many2one('account.payment', 'Advanced Payment')
    origin_payment = fields.Many2one('account.payment', 'Origin Payment')
    qr_code = fields.Char(string="QR Code", compute="_compute_qr_code")
    tax = fields.Monetary(string="Tax", compute="_conciled_tax")
    due_date = fields.Date(string="Delivery Date")
    job_no = fields.Char(string="Job No")

    @api.depends('line_ids', 'state', 'tax_totals')
    def _conciled_tax(self):
        tax_obj = self.env.company.account_sale_tax_id
        # Get the first tax account from repartition lines
        tax_account_id = tax_obj.invoice_repartition_line_ids.filtered(lambda x: x.account_id).account_id[:1].id
        
        for item in self:
            if item.advanced_payment:
                tax_line = item.line_ids.filtered(lambda l: l.account_id.id == tax_account_id)
                item.tax = sum(tax_line.mapped('amount_currency')) if tax_line else 0.0
            elif item.move_type == 'out_invoice' and item.tax_totals:
                # Odoo 16 uses a dict for tax_totals
                item.tax = item.tax_totals.get('amount_total', 0.0) - item.tax_totals.get('amount_untaxed', 0.0)
            else:
                item.tax = 0.0

    # Override for widget logic

    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        
        reconciled_vals = []
        # Optimization: Filter lines already in memory for standard pay terms, 
        # and only search for external advanced lines if necessary.
        standard_lines = self.line_ids.filtered(
            lambda l: l.account_type in ('asset_receivable', 'liability_payable')
        )
        
        # We include your custom 'advanced' accounts in the search
        advanced_lines = self.env['account.move.line'].search([
            ('move_id', '=', self.id),
            ('account_id.advanced', '=', True)
        ])
        
        pay_term_line_ids = standard_lines + advanced_lines
        partials = pay_term_line_ids.matched_debit_ids + pay_term_line_ids.matched_credit_ids
        
        for partial in partials:
            # Counterpart lines are the lines that were reconciled against this move
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            # We want the one that is NOT part of the current move
            counterpart_line = counterpart_lines.filtered(lambda line: line.move_id != self)
            
            if not counterpart_line:
                continue
                
            counterpart_line = counterpart_line[0] # Take the first if multiple

            # In Odoo 16, partial.amount is always in company currency.
            # If the invoice has a foreign currency, we usually want to show the amount_currency.
            if self.currency_id != self.company_id.currency_id:
                amount = partial.amount_currency
            else:
                amount = partial.amount

            if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                continue

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += f" ({counterpart_line.move_id.ref})"

            # Note: 'digits' [69, decimal_places] is a legacy Odoo JS format 
            # usually required by the 'account.payment.term.widget'.
            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': amount,
                'tax': getattr(counterpart_line.move_id, 'tax', False), # Use getattr for safety
                'currency': self.currency_id.symbol,
                'digits': [69, self.currency_id.decimal_places],
                'position': self.currency_id.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'used_payment': counterpart_line.move_id.advanced_payment.name if counterpart_line.move_id.advanced_payment else False,
                'used_payment_id': counterpart_line.move_id.advanced_payment.id if counterpart_line.move_id.advanced_payment else False,
                'used_move_id': counterpart_line.move_id.advanced_payment.move_id.id if counterpart_line.move_id.advanced_payment and counterpart_line.move_id.advanced_payment.move_id else False,
                'ref': ref,
            })
        return reconciled_vals

    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        lines = self.env['account.move.line'].browse(line_id)
        
        if lines[:1].account_id.advanced:
            # FIX: Ensure company context is correct
            company = self.company_id 
            
            # Avoid manual 'write' to amount_residual if possible. 
            # In v16, create your 'cc' move first, then reconcile the new line 
            # against the invoice. This will automatically update residuals.
            
            # ... [Your logic to create the 'cc' move remains similar, 
            # but replace 'company' with 'self.company_id'] ...
            
            # Example fix for the conversion lines:
            # debit_value['debit'] = self.currency_id._convert(abs(value), self.company_id.currency_id, self.company_id, self.date)
            
            return super().js_assign_outstanding_line(line_id) # Or your custom return
        return super().js_assign_outstanding_line(line_id)

    def _compute_qr_code(self):
        for invoice in self:
            if (invoice.move_type == "out_invoice" or invoice.payment_id) and invoice.partner_id:
                qr_data = self._generate_qr_data(invoice)
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                invoice.qr_code = base64.b64encode(buffer.getvalue()).decode('ascii')
            else:
                invoice.qr_code = False

    def _generate_qr_data(self, invoice):
        # Guard against missing dates
        inv_date = invoice.invoice_date or invoice.date or fields.Date.context_today(self)
        date_str = inv_date.strftime("%Y-%m-%d")
        
        name = invoice.partner_id.name or ""
        vat = invoice.partner_id.vat or ""
        
        if invoice.move_type == "out_invoice":
            return f"Partner: {name}\nVAT: {vat}\nDate: {date_str}\nTotal: {invoice.amount_total}\nResidual: {invoice.amount_residual}"
        elif invoice.payment_id:
            return f"Advance: {name}\nVAT: {vat}\nDate: {date_str}\nAmount: {invoice.payment_id.amount}"
        return ""
    

    def _get_reconciled_invoices_partials(self):
        ''' Helper to retrieve the details about reconciled invoices.
        :return A list of tuple (partial, amount, invoice_line).
        '''
        self.ensure_one()
        aux=self
        if self.payment_id and self.payment_id.advance_ok:
            aux=self.env['account.move'].search([('origin_payment','=',self.payment_id.id)])
            if not aux:
                aux=self
        else:
            return super(AccountmoveAdvance, self)._get_reconciled_invoices_partials()

        
        pay_term_lines = aux.line_ids\
            .filtered(lambda line: line.account_internal_type in ('receivable', 'payable'))
        invoice_partials = []

        for partial in pay_term_lines.matched_credit_ids:
            invoice_partials.append((partial, partial.credit_amount_currency, partial.debit_move_id))
        for partial in pay_term_lines.matched_debit_ids:
            invoice_partials.append((partial, partial.debit_amount_currency, partial.credit_move_id))

        # other_payment=self.env['account.move'].search([('origin_payment','=',self.payment_id.id)])
        # if other_payment and self.payment_id.id:
        #     pay_term_lines = other_payment.line_ids\
        #     .filtered(lambda line: line.account_internal_type in ('receivable', 'payable'))

        #     for partial in pay_term_lines.matched_debit_ids:
        #         invoice_partials.append((partial, partial.credit_amount_currency, partial.debit_move_id))
        #     for partial in pay_term_lines.matched_credit_ids:
        #         invoice_partials.append((partial, partial.debit_amount_currency, partial.credit_move_id))
       
        return invoice_partials
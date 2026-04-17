from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from datetime import datetime
import json
import qrcode
from io import BytesIO
import base64

class AccountMove(models.Model):
    _inherit = "account.move"

    advanced_payment = fields.Many2one('account.payment', string='Advanced Payment')
    origin_payment = fields.Many2one('account.payment', string='Origin Payment')
    qr_code = fields.Char(string="QR Code", compute="_compute_qr_code")
    tax = fields.Monetary(string="Tax", compute="_compute_reconciled_tax")
    due_date = fields.Date(string="Delivery Date")
    job_no = fields.Char(string="Job No")

    @api.depends('line_ids.matched_debit_ids', 'line_ids.matched_credit_ids', 'tax_totals')
    def _compute_reconciled_tax(self):
        tax_obj = self.env.company.account_sale_tax_id
        tax_account_id = False
        
        # Get the first account found in the repartition lines
        for inv in tax_obj.invoice_repartition_line_ids:
            if inv.account_id:
                tax_account_id = inv.account_id.id
                break

        for item in self:
            if item.advanced_payment:
                # Find the tax amount from the move lines
                tax_line = item.line_ids.filtered(lambda l: l.account_id.id == tax_account_id)
                item.tax = sum(tax_line.mapped('amount_currency')) if tax_line else 0.0
            elif item.move_type == 'out_invoice':
                # In Odoo 16, tax_totals is a dict
                totals = item.tax_totals or {}
                item.tax = totals.get('amount_total', 0.0) - totals.get('amount_untaxed', 0.0)
            else:
                item.tax = 0.0

    def _compute_payments_widget_to_reconcile_info(self):
        # Trigger standard logic first
        super()._compute_payments_widget_to_reconcile_info()
        
        for move in self:
            # If logic requires complete override of the widget:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False
            
            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            # Filtering lines using Odoo 16 account_type
            pay_term_lines = move.line_ids.filtered(
                lambda line: line.account_type in ('asset_receivable', 'liability_payable')
            )
            
            advance_account_ids = [
                move.commercial_partner_id.advance_account_payable_id.id,
                move.commercial_partner_id.advance_account_receivable_id.id
            ]
            
            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids + advance_account_ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                title = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                title = _('Outstanding debits')

            relevant_lines = self.env['account.move.line'].search(domain)
            if not relevant_lines:
                continue

            content = []
            for line in relevant_lines:
                tax_value_adv = 0.0
                amount = abs(line.amount_residual_currency) if line.currency_id == move.currency_id else \
                    line.company_id.currency_id._convert(abs(line.amount_residual), move.currency_id, move.company_id, line.date)

                if line.account_id.advanced and line.payment_id and line.payment_id.is_taxed:
                    tax_value_adv = line.payment_id.total_tax_amount

                if move.currency_id.is_zero(amount):
                    continue

                content.append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                    'is_advance': line.account_id.advanced,
                    'tax_value_adv': tax_value_adv,
                })

            if content:
                move.invoice_outstanding_credits_debits_widget = {
                    'title': title,
                    'outstanding': True,
                    'content': content,
                    'move_id': move.id,
                }
                move.invoice_has_outstanding = True

    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        # 'line' is the outstanding credit/debit the user clicked in the widget
        line = self.env['account.move.line'].browse(line_id)

        # If not an 'advanced' account, use standard Odoo behavior
        if not line.account_id.advanced:
            return super().js_assign_outstanding_line(line_id)

        company = self.company_id
        journal_date = fields.Date.context_today(self)
        
        # 1. Identify Tax Account from Company Settings
        tax_obj = company.account_sale_tax_id
        tax_account_id = False
        if tax_obj:
            for rep_line in tax_obj.invoice_repartition_line_ids:
                if rep_line.account_id:
                    tax_account_id = rep_line.account_id.id
                    break

        # 2. Determine target Receivable/Payable Account
        if self.move_type == 'in_invoice':
            target_account_id = line.partner_id.property_account_payable_id.id
        elif self.move_type == 'out_invoice':
            target_account_id = line.partner_id.property_account_receivable_id.id
        else:
            target_account_id = line.account_id.id

        # 3. Get Tax Values from Odoo 16 tax_totals dictionary
        tax_value = 0.0
        if self.move_type == 'out_invoice' and self.tax_totals:
            # tax_totals is already a dict in Odoo 16
            tax_value = self.tax_totals.get('amount_total', 0.0) - self.tax_totals.get('amount_untaxed', 0.0)

        # 4. Parse Widget Data for Advanced Tax
        tax_value_adv = 0.0
        origin_payment_id = False
        if tax_value != 0 and self.move_type == 'out_invoice' and self.invoice_outstanding_credits_debits_widget:
            # Widget is stored as a JSON string in the DB field
            widget_data = json.loads(self.invoice_outstanding_credits_debits_widget)
            if widget_data.get('outstanding'):
                for item in widget_data.get('content', []):
                    if item.get('id') == line_id:
                        tax_value_adv = item.get('tax_value_adv', 0.0)
                        origin_payment_id = item.get('account_payment_id')
                        break

        # 5. Handle Currency & Amount Calculation
        # Check if we are dealing with multi-currency
        other_currency = line.currency_id and line.currency_id != company.currency_id and self.currency_id != company.currency_id
        value = 0.0
        full_reconcile = False

        if other_currency:
            # Multi-currency logic
            if abs(self.amount_residual) < abs(line.amount_residual_currency):
                value = self.amount_residual
            else:
                value = line.amount_residual_currency
        else:
            # Single currency (or company currency) logic
            res_converted = self.currency_id._convert(self.amount_residual, company.currency_id, company, self.date)
            if abs(res_converted) <= abs(line.amount_residual):
                value = res_converted
                full_reconcile = True
            else:
                value = line.amount_residual

        # 6. Prepare the Journal Entry Lines
        vsign = 1 if value > 0 else -1
        new_line_ids = []

        # Calculate tax adjustment for this specific partial move
        if tax_value != 0 and self.move_type == 'out_invoice':
            if not full_reconcile:
                tax_value_adv = self._compute_total_tax_amount(tax_obj, abs(value), self.currency_id)
            else:
                tax_value_adv = tax_value

        # A. The Credit Line: Decrease the Advance Account
        credit_vals = {
            'name': _('Advance Clearance: %s', line.move_id.name),
            'partner_id': line.partner_id.id,
            'account_id': line.account_id.id,
            'company_id': company.id,
            'date': journal_date,
        }

        # B. The Debit Line: Increase the Receivable/Payable Account
        debit_vals = {
            'name': _('Advance Transfer to %s', self.name),
            'partner_id': line.partner_id.id,
            'account_id': target_account_id,
            'company_id': company.id,
            'date': journal_date,
        }

        # Apply currency conversions
        if other_currency:
            credit_vals.update({
                'amount_currency': -value,
                'currency_id': self.currency_id.id,
                'credit': self.currency_id._convert(abs(value), company.currency_id, company, self.date),
            })
            debit_vals.update({
                'amount_currency': vsign * (abs(value) - tax_value_adv),
                'currency_id': self.currency_id.id,
                'debit': self.currency_id._convert(abs(value) - abs(tax_value_adv), company.currency_id, company, self.date),
            })
        else:
            credit_vals['credit'] = abs(value)
            debit_vals['debit'] = abs(value) - abs(tax_value_adv)

        new_line_ids.append(Command.create(credit_vals))
        new_line_ids.append(Command.create(debit_vals))

        # C. The Tax Line (if applicable)
        if tax_value != 0 and self.move_type == 'out_invoice' and tax_account_id:
            tax_vals = {
                'name': _('Advance Tax Transfer'),
                'partner_id': line.partner_id.id,
                'account_id': tax_account_id,
                'company_id': company.id,
                'date': journal_date,
            }
            if other_currency:
                tax_vals.update({
                    'amount_currency': vsign * tax_value_adv,
                    'currency_id': self.currency_id.id,
                    'debit': self.currency_id._convert(abs(tax_value_adv), company.currency_id, company, self.date),
                })
            else:
                tax_vals['debit'] = abs(tax_value_adv)
            new_line_ids.append(Command.create(tax_vals))

        # 7. Create and Post the Entry
        move_vals = {
            'move_type': 'entry',
            'date': journal_date,
            'journal_id': self.journal_id.id,
            'company_id': company.id,
            'line_ids': new_line_ids,
            'advanced_payment': line.payment_id.id,
        }

        # Handle custom currency exchange fields if they exist
        if 'report_currency_exchange_rate' in self._fields and self.report_currency_exchange_rate:
            move_vals['report_currency_exchange_rate'] = self.report_currency_exchange_rate

        new_move = self.env['account.move'].create(move_vals)
        new_move.action_post()
        
        # Odoo 16: You might want to keep the name sequence unless you specifically need the ID
        # new_move.write({'name': str(new_move.id)}) 

        # 8. Reconcile
        self.write({'origin_payment': origin_payment_id})

        # Reconcile Original Advance Line with the New Entry's Credit Line
        new_credit_line = new_move.line_ids.filtered(lambda l: l.account_id == line.account_id)
        (line + new_credit_line).reconcile()

        # Reconcile Invoice Line with the New Entry's Debit Line
        new_debit_line = new_move.line_ids.filtered(lambda l: l.account_id.id == target_account_id)
        invoice_reconcilable_lines = self.line_ids.filtered(
            lambda l: l.account_id.id == target_account_id and not l.reconciled
        )
        
        return (invoice_reconcilable_lines + new_debit_line).reconcile()


    def _compute_qr_code(self):
        for invoice in self:
            if invoice.move_type == "out_invoice" or invoice.payment_id:
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
        if invoice.move_type == "out_invoice":
            return (f"Company: {invoice.partner_id.name}\n"
                    f"Tax Id: {invoice.partner_id.vat or ''}\n"
                    f"Date: {invoice.invoice_date}\n"
                    f"Untaxed: {invoice.amount_untaxed}\n"
                    f"Tax: {invoice.amount_tax}")
        elif invoice.payment_id:
            return (f"Company: {invoice.partner_id.name}\n"
                    f"Date: {invoice.date}\n"
                    f"Amount: {invoice.payment_id.amount}")
        return ""

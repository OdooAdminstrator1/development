from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from datetime import timedelta, datetime, date
import json
import qrcode
from io import BytesIO
import base64

class AccountmoveAdvance(models.AbstractModel):
    _inherit ="account.move"

    advanced_payment=fields.Many2one('account.payment','Advanced Payment')
    origin_payment=fields.Many2one('account.payment','Origin Payment')
    qr_code = fields.Char(string="QR Code", compute="_compute_qr_code")
    tax=fields.Monetary(string="tax",compute="_conciled_tax")
    due_date=fields.Date(string="Delivery Date")
    job_no=fields.Char(string="Job No")

    def _conciled_tax(self):
        tax_obj=self.env.company.account_sale_tax_id
        tax_account=0
        for inv in tax_obj.invoice_repartition_line_ids:
                        if inv.account_id:
                            tax_account = inv.account_id.id
        for item in self:
            if item.advanced_payment:
                for line in item.line_ids:
                    if line.account_id.id==tax_account:
                        item.tax=line.amount_currency
                        break
            elif item.move_type == 'out_invoice':
                totals=self._get_total_tax_JSON_values()
                item.tax=totals['total_tax']

            else:
                item.tax=0

    def _compute_payments_widget_to_reconcile_info(self):
        """ In Odoo 16, the outstanding widget logic is slightly different. """
        super(AccountmoveAdvance, self)._compute_payments_widget_to_reconcile_info()
        for move in self:
            # If your logic requires hiding standard outstanding credits/debits:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False
            
            tax_value = 0
            tax_value_adv = 0
            
            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue
            
            if move.move_type == 'out_invoice' and move.tax_totals:
                # Odoo 16: tax_totals is already a dict
                tax_json = move.tax_totals
                tax_value = tax_json.get('amount_total', 0) - tax_json.get('amount_untaxed', 0)

            pay_term_lines = move.line_ids.filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))
            
            # Handling custom advance accounts if they exist on partner
            advance_account_ids = []
            if hasattr(move.commercial_partner_id, 'advance_account_payable_id'):
                advance_account_ids.append(move.commercial_partner_id.advance_account_payable_id.id)
            if hasattr(move.commercial_partner_id, 'advance_account_receivable_id'):
                advance_account_ids.append(move.commercial_partner_id.advance_account_receivable_id.id)

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids + advance_account_ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]
            
            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}
            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                # Your specific logic for taxed advance payments
                if tax_value != 0 and move.move_type == 'out_invoice' and getattr(line.account_id, 'advanced', False) \
                   and line.move_id.payment_id and getattr(line.move_id.payment_id, 'is_taxed', False):
                    
                    tax_value_adv = getattr(line.move_id.payment_id, 'total_tax_amount', 0)
                    
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                    else:
                        amount = line.company_currency_id._convert(
                            abs(line.amount_residual), move.currency_id, move.company_id, line.date
                        )
                else:
                    if line.currency_id == move.currency_id:
                        amount = abs(line.amount_residual_currency)
                    else:
                        amount = line.company_currency_id._convert(
                            abs(line.amount_residual), move.currency_id, move.company_id, line.date
                        )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id, # Odoo 16 often uses currency_id
                    'symbol': move.currency_id.symbol,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'position': move.currency_id.position,
                    'digits': [69, move.currency_id.decimal_places],
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                    'is_advance': getattr(line.account_id, 'advanced', False),
                    'tax_value_adv': tax_value_adv,
                })

            if payments_widget_vals['content']:
                move.invoice_outstanding_credits_debits_widget = json.dumps(payments_widget_vals)
                move.invoice_has_outstanding = True



    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.env['account.move.line'].search([('account_id.advanced', '=', True)]) +self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials =  pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            if not (partial.debit_move_id.statement_id or  partial.credit_move_id.statement_id):
                counterpart_lines = partial.debit_move_id + partial.credit_move_id
                counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)[0]

                #if foreign_currency and partial.currency_id == foreign_currency:
                amount = partial.amount
                #else:
                    #amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id, self.date)

                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue

                ref = counterpart_line.move_id.name
                if counterpart_line.move_id.ref:
                    ref += ' (' + counterpart_line.move_id.ref + ')'

                reconciled_vals.append({
                    'name': counterpart_line.name,
                    'journal_name': counterpart_line.journal_id.name,
                    'amount': amount,
                    'tax':counterpart_line.move_id.tax or False,
                    'currency': self.currency_id.symbol,
                    'digits': [69, self.currency_id.decimal_places],
                    'position': self.currency_id.position,
                    'date': counterpart_line.date,
                    'payment_id': counterpart_line.id,
                    'account_payment_id': counterpart_line.payment_id.id,
                    'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                    'move_id': counterpart_line.move_id.id,
                    'used_payment': counterpart_line.move_id.advanced_payment.name or False,
                    'used_payment_id': counterpart_line.move_id.advanced_payment.id or False,
                    'used_move_id': counterpart_line.move_id.advanced_payment.move_id.id or False,
                    'ref': ref,
                })
        return reconciled_vals
    
    def _get_total_tax_JSON_values(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        ret_vals = {}
        pay_term_line_ids = self.env['account.move.line'].search([('account_id.advanced', '=', True)]) +self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials =  pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        total_tax=0
        total_amount=0
        for partial in partials:
            if not (partial.debit_move_id.statement_id or  partial.credit_move_id.statement_id):
                counterpart_lines = partial.debit_move_id + partial.credit_move_id
                counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)[0]

                if foreign_currency and partial.currency_id == foreign_currency:
                    amount = partial.amount_currency
                else:
                    amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id, self.date)

                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue

                total_amount+=amount
                total_tax+=counterpart_line.move_id.tax 



        ret_vals={'total_amount': total_amount,'total_tax':total_tax or False}
        
        return ret_vals

    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        line = self.env['account.move.line'].browse(line_id)

        # 1. Fallback to standard Odoo behavior if not an 'advanced' account
        if not line.account_id.advanced:
            return super().js_assign_outstanding_line(line_id)

        company = self.company_id
        today = date.today()
        
        # 2. Get Tax Information
        tax_obj = company.account_sale_tax_id
        tax_account_id = next((rep.account_id.id for rep in tax_obj.invoice_repartition_line_ids if rep.account_id), False)

        # 3. Handle Manual Currency Rates (Context Management)
        if self.apply_manual_currency_exchange and hasattr(line.payment_id, 'manual_payment_rate_hidden'):
            self = self.with_context(
                manual_rate=line.payment_id.manual_payment_rate_hidden,
                active_manual_currency=line.payment_id.apply_manual_currency_exchange,
            )

        # 4. Determine Target Account based on move type
        if self.move_type == 'in_invoice':
            target_account_id = line.partner_id.property_account_payable_id.id
        elif self.move_type == 'out_invoice':
            target_account_id = line.partner_id.property_account_receivable_id.id
        else:
            return super().js_assign_outstanding_line(line_id)

        # 5. Extract Amounts from Widget JSON
        amount_adv = 0
        tax_value_adv = 0
        origin_payment_id = False
        
        if self.move_type == 'out_invoice' and self.invoice_outstanding_credits_debits_widget:
            widg = json.loads(self.invoice_outstanding_credits_debits_widget)
            for wg in widg.get('content', []):
                if wg['id'] == line_id:
                    amount_adv = wg.get('amount', 0) - wg.get('tax_value_adv', 0)
                    tax_value_adv = wg.get('tax_value_adv', 0)
                    origin_payment_id = wg.get('account_payment_id')
                    break

        # 6. Calculate Value to Reconcile
        # Odoo 16 uses amount_residual for company currency and amount_residual_currency for foreign
        is_foreign = line.currency_id and line.currency_id != company.currency_id
        
        if is_foreign:
            value = min(abs(self.amount_residual), abs(line.amount_residual_currency))
        else:
            value = min(abs(self.amount_residual), abs(line.amount_residual))

        # 7. Prepare Journal Entry Lines (Bridge Move)
        new_line_ids = []
        
        # Credit Line (Decrease Advanced/Receivable)
        credit_vals = {
            'name': _('Advanced Reconciliation: %s') % (line.move_id.name),
            'account_id': target_account_id if self.move_type == 'out_invoice' else line.account_id.id,
            'partner_id': line.partner_id.id,
            'date': today,
            'credit': abs(value) if not is_foreign else self.currency_id._convert(abs(value), company.currency_id, company, today),
        }
        if is_foreign:
            credit_vals.update({
                'amount_currency': -abs(value),
                'currency_id': line.currency_id.id,
            })
        new_line_ids.append((0, 0, credit_vals))

        # Debit Line (Base Amount)
        debit_vals = {
            'name': _('Advanced Reconciliation: %s') % (line.move_id.name),
            'account_id': line.account_id.id if self.move_type == 'out_invoice' else line.partner_id.property_account_payable_id.id,
            'partner_id': line.partner_id.id,
            'date': today,
            'debit': abs(value) - abs(tax_value_adv),
        }
        if is_foreign:
            debit_vals.update({
                'amount_currency': abs(value) - abs(tax_value_adv),
                'currency_id': line.currency_id.id,
            })
        new_line_ids.append((0, 0, debit_vals))

        # Tax Line (If applicable)
        if tax_value_adv and tax_account_id:
            tax_vals = {
                'name': _('Tax for Advanced Payment'),
                'account_id': tax_account_id,
                'partner_id': line.partner_id.id,
                'date': today,
                'debit': abs(tax_value_adv),
            }
            if is_foreign:
                tax_vals.update({
                    'amount_currency': abs(tax_value_adv),
                    'currency_id': line.currency_id.id,
                })
            new_line_ids.append((0, 0, tax_vals))

        # 8. Create and Post Bridge Move
        move_vals = {
            'move_type': 'entry',
            'date': today,
            'journal_id': self.journal_id.id,
            'company_id': company.id,
            'partner_id': line.partner_id.id,
            'line_ids': new_line_ids,
            'advanced_payment': line.payment_id.id,
        }
        
        # Handle custom currency exchange rate if module exists
        if hasattr(line.move_id, 'report_currency_exchange_rate'):
            move_vals['report_currency_exchange_rate'] = line.move_id.report_currency_exchange_rate

        new_move = self.env['account.move'].create(move_vals)
        new_move.action_post()

        # 9. Trigger Reconciliation
        # Find the line in the new move that matches the target account to reconcile with invoice
        reconcile_lines = new_move.line_ids.filtered(lambda l: l.account_id.id == target_account_id)
        reconcile_lines += self.line_ids.filtered(lambda l: l.account_id.id == target_account_id and not l.reconciled)
        
        self.write({'origin_payment': origin_payment_id})
        
        return reconcile_lines.reconcile()
    

    def _compute_total_tax_amount(self,tax ,amount,currency_id):
        return amount-currency_id.round(amount/(1+tax.amount/100))
    
    def _get_reconciled_invoices_partials(self):
        ''' Helper to retrieve the details about reconciled invoices.
        :return A list of tuple (partial, amount, invoice_line).
        '''
        self.ensure_one()
        aux = self
        
        # Handling the advance payment logic
        if self.payment_id and self.payment_id.advance_ok:
            # Added limit=1 to ensure we don't crash if multiple moves are found
            aux = self.env['account.move'].search([('origin_payment', '=', self.payment_id.id)], limit=1) or self
        else:
            # Standard super call (Python 3 style is cleaner)
            return super()._get_reconciled_invoices_partials()

        # FIX: 'account_internal_type' is now 'account_type'
        # FIX: 'receivable'/'payable' are now 'asset_receivable'/'liability_payable'
        pay_term_lines = aux.line_ids.filtered(
            lambda line: line.account_type in ('asset_receivable', 'liability_payable')
        )
        
        invoice_partials = []
        for partial in pay_term_lines.matched_credit_ids:
            invoice_partials.append((partial, partial.credit_amount_currency, partial.debit_move_id))
        for partial in pay_term_lines.matched_debit_ids:
            invoice_partials.append((partial, partial.debit_amount_currency, partial.credit_move_id))

        return invoice_partials
    
    def _compute_qr_code(self):
        for invoice in self:
            if invoice.move_type=="out_invoice" or invoice.payment_id:
                qr_data = self._generate_qr_data(invoice)
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                dataqrcode = base64.b64encode(buffer.getvalue())
                invoice.qr_code = dataqrcode.decode('ascii')
            else:
                invoice.qr_code = False
    
    def _generate_qr_data(self, invoice):
           # Generate the data to be encoded in the QR code
            qr_data=''
            if invoice.move_type=="out_invoice":
                company_name = invoice.partner_id.name
                company_Tax = invoice.partner_id.vat

                date = invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else ""
                untaxed_amount = invoice.amount_untaxed
                tax_amount = invoice.amount_tax
                paid_tax=invoice.tax
                amount_residual=invoice.amount_residual

                # Ensure Arabic encoding for company name
                company_name_arabic = company_name.encode('utf-8').decode('utf-8')
                qr_data = f"Company: {company_name_arabic}\nTax Id: {company_Tax}\nDate: {date}\nUntaxed Amount: {untaxed_amount}\nTax: {tax_amount}\nPaid Tax: {paid_tax}\nDue Tax:{tax_amount-paid_tax}\nDue Amount:{amount_residual}"
            
            elif invoice.payment_id:
                company_name = invoice.partner_id.name
                company_Tax = invoice.partner_id.vat
                date = invoice.date.strftime("%Y-%m-%d") 
                untaxed_amount = invoice.payment_id.amount
                tax_amount = invoice.payment_id.total_tax_amount
                # Ensure Arabic encoding for company name
                company_name_arabic = company_name.encode('utf-8').decode('utf-8')
                qr_data = f"Company: {company_name_arabic}\nTax Id: {company_Tax}\nDate: {date}\nUntaxed Amount: {untaxed_amount}\nTax: {tax_amount}"
            return qr_data
     

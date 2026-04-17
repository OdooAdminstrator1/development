from odoo import models, fields, api, _,Command
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



    def get_conciled_tax(self):
        self.ensure_one()
        return self.tax

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
        super(AccountMove, self)._compute_payments_widget_to_reconcile_info()
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False
            
            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue
            if  move.move_type == 'out_invoice':
                tax_json=self.tax_totals
                tax_value=tax_json['amount_total']-tax_json['amount_untaxed']

            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
            advance_account_ids = [move.commercial_partner_id.advance_account_payable_id.id,
            move.commercial_partner_id.advance_account_receivable_id.id]
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

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True


    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        lines = self.env['account.move.line'].browse(line_id)

        new_line_ids=[]
        credit_value={}
        debit_value_tax={}
        debit_value={}
        value = 0
        tax_value=0
        tax_json={}
        amount_adv=0
        tax_value_adv=0
        origin_payment_id=False
        journal_date=datetime.date(datetime.now())
        # recoceled = False
        # tax_obj=self.env['account.tax'].search([('type_tax_use','=','sale'),('company_id','=',self.env.company.id)])
        tax_obj=self.env.company.account_sale_tax_id
        # tax_account=tax_obj.tax_group_id.property_tax_receivable_account_id.id
        tax_account=0
        for inv in tax_obj.invoice_repartition_line_ids:
                        if inv.account_id:
                            tax_account = inv.account_id.id

        # company = self.env.company
        full_reconcile=False
        if lines[0].account_id.advanced:
            other=False
            if 'manual_payment_rate' in lines[0].payment_id.fields_get():
                if self.apply_manual_currency_exchange:
                    self = self.with_context(manual_rate=lines[0].payment_id.manual_payment_rate_hidden,
                                             active_manutal_currency=lines[0].payment_id.apply_manual_currency_exchange,
                                             )
            
            if  self.move_type=='in_invoice':
                account=lines[0].partner_id.property_account_payable_id.id
            if  self.move_type == 'out_invoice':
                account = lines[0].partner_id.property_account_receivable_id.id
                tax_json=self.tax_totals
                tax_value=tax_json['amount_total']-tax_json['amount_untaxed']

            if tax_value!=0 and  self.move_type == 'out_invoice':
                widg=self.invoice_outstanding_credits_debits_widget
                if widg['outstanding']:
                    for wg in widg['content']:
                        if wg['id']==line_id:
                            amount_adv=wg['amount']-wg['tax_value_adv']
                            tax_value_adv=wg['tax_value_adv']
                            origin_payment_id=wg['account_payment_id']
                            break
                        else:
                            continue


            if lines[0].currency_id and lines[0].currency_id != self.company_id.currency_id and self.currency_id != self.company_id.currency_id:
                other= True
                if tax_value!=0 and  self.move_type == 'out_invoice':
                        pass
                else:
                    if abs(self.amount_residual) < abs(lines[0].amount_residual_currency):
                        value =  self.amount_residual
                        amount = abs(lines[0].amount_residual_currency) - (self.amount_residual)
                        for l in lines[0].move_id.line_ids:
                            if l.amount_residual != 0:
                                l.write({'amount_residual_currency': (abs(l.amount_residual) / l.amount_residual) * amount})
                                l.write({'amount_residual': (abs(l.amount_residual) / l.amount_residual) * amount/ self.currency_id.rate})
                    else:
                        value = lines[0].amount_residual_currency
                        lines[0].write({'amount_residual': 0})
                        lines[0].write({'amount_residual_currency': 0})
                        lines[0].write({'reconciled': True})

            else: 
                if self.currency_id != self.company_id.currency_id:
                    self.amount_residual=self.currency_id._convert( self.amount_residual, self.company.currency_id, self.company, self.date)

                if abs(self.amount_residual) <= abs(lines[0].amount_residual): #+abs(tax_value_adv) :
                    value=self.amount_residual
                    amount = abs(lines[0].amount_residual)- abs(self.amount_residual) #+abs(tax_value_adv)- (self.amount_residual)
                    full_reconcile=True
                    for l in lines[0].move_id.line_ids:
                        if l.amount_residual_currency:
                            l.write({'amount_residual_currency': (abs(l.amount_residual) / l.amount_residual) * (
                                        l.amount_residual_currency * amount / (lines[0].amount_residual))})
                        if l.amount_residual!=0:
                            l.write({'amount_residual': (abs(l.amount_residual) / l.amount_residual) * amount})
                else:
                    # if lines[0].amount_residual>=0:
                    #     value=lines[0].amount_residual-tax_value_adv
                    # else:
                    #     value=lines[0].amount_residual+tax_value_adv
                    value=lines[0].amount_residual #-tax_value
                    lines[0].write({'amount_residual':0})
                    if lines[0].amount_residual_currency:
                        lines[0].write({'amount_residual_currency': 0})
                    lines[0].write({'reconciled':True})

            
            if other:
                credit_value['amount_currency'] = -value
                credit_value['currency_id'] = self.currency_id.id
                credit_value['credit'] = self.currency_id._convert(abs(value), self.company.currency_id, self.company, self.date)
            else: #check here
                credit_value['credit'] = abs(value)
            credit_value['move_id'] = False
            credit_value['id'] = False

            if self.move_type == 'in_invoice': # vendor invoice
             credit_value['account_id'] = lines[0].account_id.id
            if self.move_type == 'out_invoice': # customer invoice
             credit_value['account_id'] = lines[0].partner_id.property_account_receivable_id.id
            
            credit_value['company_id']=lines[0].company_id.id
            credit_value['amount_residual'] = 0
            credit_value['currency_id'] =lines[0].currency_id.id
            credit_value['parent_state'] = 'posted'
            credit_value['partner_id'] = lines[0].partner_id.id
            credit_value['date'] =journal_date
            credit_value['payment_id']= lines[0].payment_id.id

            if value>0:
                vsign=1
            else:
                vsign=-1
            
            if tax_value!=0 and  self.move_type == 'out_invoice':
                if full_reconcile:
                    tax_value_adv=tax_value
                # else:


            if other:
                debit_value['amount_currency'] =vsign* (abs(value)-tax_value_adv)
                debit_value_tax['currency_id'] = self.currency_id.id
                if tax_value!=0 and  self.move_type == 'out_invoice':
                    debit_value_tax['amount_currency'] = vsign*tax_value_adv
                    debit_value_tax['currency_id'] = self.currency_id.id
                    debit_value['debit'] =self.currency_id._convert(abs(value)-abs(tax_value_adv), self.company.currency_id, self.company, self.date)
                    debit_value_tax['debit'] =self.currency_id._convert(abs(tax_value_adv), self.company.currency_id, self.company, self.date)

                else:
                    debit_value['debit'] =self.currency_id._convert(abs(value), self.company.currency_id, self.company, self.date)
            else:
                if tax_value!=0 and  self.move_type == 'out_invoice':
                    tax_value_adv=self._compute_total_tax_amount(tax_obj,amount=abs(value),currency_id=self.currency_id)
                    debit_value['debit'] = abs(value)-abs(tax_value_adv)
                    debit_value_tax['debit'] = abs(tax_value_adv)
                else:
                    debit_value['debit'] = abs(value)

            debit_value['move_id'] = False
            debit_value['id'] = False
            debit_value_tax['move_id'] = False
            debit_value_tax['id'] = False

            if self.move_type == 'out_invoice': # customer invoice
                debit_value['account_id'] = lines[0].account_id.id # the advance account
                if tax_value!=0:
                    debit_value_tax['account_id'] = tax_account
                    
            if self.move_type == 'in_invoice':
                debit_value['account_id'] = lines[0].partner_id.property_account_payable_id.id
           
            debit_value['company_id'] = lines[0].company_id.id
            debit_value['amount_residual'] = 0
            debit_value['currency_id'] = lines[0].currency_id.id
            debit_value['parent_state'] = 'posted'
            debit_value['partner_id'] =lines[0].partner_id.id
            debit_value['date'] = journal_date
            if tax_value!=0 and  self.move_type == 'out_invoice':
                debit_value_tax['company_id'] = lines[0].company_id.id
                debit_value_tax['amount_residual'] = 0
                debit_value_tax['currency_id'] = lines[0].currency_id.id
                debit_value_tax['parent_state'] = 'posted'
                debit_value_tax['partner_id'] =lines[0].partner_id.id
                debit_value_tax['date'] = journal_date


            # for line in self.line_ids:
            #     new_line_ids.append((0,0,line))



            new_line_ids.append((0, 0, credit_value))
            new_line_ids.append((0, 0, debit_value))
            if tax_value!=0 and  self.move_type == 'out_invoice':
                new_line_ids.append((0, 0, debit_value_tax))
            
            j_id = int(self.env['ir.config_parameter'].sudo().get_param('pre_payment.adv_payment_journal_id'))

          #  j_id,j_name=self.get_joutnal_id(journal_date)
            if 'report_credit' in lines[0].fields_get() and lines[0].move_id.report_currency_exchange_rate:
                cc = self.env['account.move'].create({
                    # 'name': j_name,
                    'move_type': 'entry',
                    'date': journal_date,
                    'journal_id': j_id, # self.journal_id.id,
                    'company_id': self.company_id.id,
                    'line_ids': new_line_ids,
                    # 'payment_id': lines[0].payment_id.id,
                    'report_currency_exchange_rate':lines[0].move_id.report_currency_exchange_rate
                }).id

        # 6. Prepare the Journal Entry Lines
        vsign = 1 if value > 0 else -1
        new_line_ids = []

        # Calculate tax adjustment for this specific partial move
        if tax_value != 0 and self.move_type == 'out_invoice':
            if not full_reconcile:
                tax_value_adv = self._compute_total_tax_amount(tax_obj, abs(value), self.currency_id)
            else:
                # case customer+tax is here
                cc= self.env['account.move'].create({
                        # 'name': j_name,
                        'move_type': 'entry',
                        'date': journal_date,
                        'journal_id': j_id,
                        'company_id': self.company_id.id,
                        'partner_id': lines[0].partner_id.id,
                        'commercial_partner_id': lines[0].partner_id.id,
                        # 'payment_id': lines[0].payment_id.id,
                        'line_ids': new_line_ids
                     }).id
            move=self.env['account.move'].browse(cc)
            move.write({'state':'posted'})
            move.write({'advanced_payment':lines[0].payment_id.id})

            lines = self.env['account.move.line'].search([('move_id','=',cc),('account_id','=',account)])
            # lines = self.env['account.move.line'].search([('move_id','=',cc)])
            # lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].partner_id.property_account_receivable_id.id and not line.reconciled)
            lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
            self.write({'origin_payment':origin_payment_id})
            return lines.reconcile()
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

    def get_joutnal_id(self,journal_date):
        record = self.env['account.journal'].search([('name', '=', 'Advance Payment')], limit=1)
        if record:
            record_id = record.id
            year_str = journal_date.strftime('%Y')
            # 2. Find the highest sequence number already used this year in this journal
            last_move = self.env['account.move'].search([
                ('name', 'like', f'AP/{year_str}/%'),
                ('journal_id', '=', record_id)
            ], order='name desc', limit=1)

            # 3. Increment the number
            next_number = 1
            if last_move:
                # Splits 'AP/2026/0005' and takes the '0005'
                last_seq = last_move.name.split('/')[-1]
                next_number = int(last_seq) + 1

            # 4. Format the new name (zfill(4) makes it 0001, 0002, etc.)
            new_name = f"AP/{year_str}/{str(next_number).zfill(4)}"
            return record_id,new_name

        return False,False
 
    def _compute_total_tax_amount(self,tax ,amount,currency_id):
        return amount-currency_id.round(amount/(1+tax.amount/100))


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
            return super(AccountMove, self)._get_reconciled_invoices_partials()

        
        pay_term_lines = aux.line_ids\
             .filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))
        invoice_partials = []

        for partial in pay_term_lines.matched_credit_ids:
            invoice_partials.append((partial, partial.credit_amount_currency, partial.debit_move_id))
        for partial in pay_term_lines.matched_debit_ids:
            invoice_partials.append((partial, partial.debit_amount_currency, partial.credit_move_id))
       
        return invoice_partials ,[]

    # def _get_reconciled_info_JSON_values(self):
    #     self.ensure_one()
    #     reconciled_vals = []
    #     pay_term_line_ids = self.env['account.move.line'].search([('account_id.advanced', '=', True)]) +self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
    #     partials =  pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
    #     for partial in partials:
    #         if not (partial.debit_move_id.statement_id or  partial.credit_move_id.statement_id):
    #             counterpart_lines = partial.debit_move_id + partial.credit_move_id
    #             counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)[0]
    #             amount = partial.amount
    #             if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
    #                 continue

    #             ref = counterpart_line.move_id.name
    #             if counterpart_line.move_id.ref:
    #                 ref += ' (' + counterpart_line.move_id.ref + ')'

    #             reconciled_vals.append({
    #                 'name': counterpart_line.name,
    #                 'journal_name': counterpart_line.journal_id.name,
    #                 'amount': amount,
    #                 # 'tax':counterpart_line.move_id._conciled_tax or 0,
    #                 'tax':counterpart_line.move_id.get_conciled_tax(),
    #                 'currency': self.currency_id.symbol,
    #                 'digits': [69, self.currency_id.decimal_places],
    #                 'position': self.currency_id.position,
    #                 'date': counterpart_line.date,
    #                 'payment_id': counterpart_line.id,
    #                 'account_payment_id': counterpart_line.payment_id.id,
    #                 'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
    #                 'move_id': counterpart_line.move_id.id,
    #                 'used_payment': counterpart_line.move_id.advanced_payment.name or False,
    #                 'used_payment_id': counterpart_line.move_id.advanced_payment.id or False,
    #                 'used_move_id': counterpart_line.move_id.advanced_payment.move_id.id or False,
    #                 'ref': ref,
    #             })
    #     return reconciled_vals
    

    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        reconciled_vals = []
        for partial, amount, counterpart_line in self._get_reconciled_invoices_partials()[0]:
            reconciled_vals.append(self._get_reconciled_vals(partial, amount, counterpart_line))
        return reconciled_vals

    def _get_reconciled_vals(self, partial, amount, counterpart_line):
        if counterpart_line.move_id.ref:
            reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
        else:
            reconciliation_ref = counterpart_line.move_id.name
        ret =   {
            'name': counterpart_line.name,
            'journal_name': counterpart_line.journal_id.name,
            'amount': amount,
            'tax':counterpart_line.move_id.get_conciled_tax() or 0,
            'currency': self.currency_id.symbol,
            'digits': [69, self.currency_id.decimal_places],
            'position': self.currency_id.position,
            'date': counterpart_line.date,
            'payment_id': counterpart_line.id,
            'partial_id': partial.id,
            'account_payment_id': counterpart_line.payment_id.id,
            'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
            'move_id': counterpart_line.move_id.id,
            'used_payment': counterpart_line.move_id.advanced_payment.name or False,
            'used_payment_id': counterpart_line.move_id.advanced_payment.id or False,
            'used_move_id': counterpart_line.move_id.advanced_payment.move_id.id or False,
            'ref': reconciliation_ref,
        }
        return ret



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
                amount=0
                counterpart_lines = partial.debit_move_id + partial.credit_move_id
                counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)[0]
                amount = counterpart_line.amount_currency

                # if foreign_currency and partial.currency_id == foreign_currency:
                #     amount = counterpart_line.amount_currency
                # else:
                #     amount = partial.company_currency_id._convert( counterpart_line.amount_currency, self.currency_id, self.company_id, self.date)

                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue

                total_amount+=amount
                total_tax+=counterpart_line.move_id.tax 



        ret_vals={'total_amount': total_amount,'total_tax':total_tax or False}
        
        return ret_vals


    

from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from datetime import timedelta, datetime, date
import json


class AccountmoveAdvance(models.AbstractModel):
    _inherit ="account.move"

    advanced_payment=fields.Many2one('account.payment','Advanced Payment')

    def _compute_payments_widget_to_reconcile_info(self):
        super(AccountmoveAdvance, self)._compute_payments_widget_to_reconcile_info()
        for move in self:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False
            tax_value=0
            tax_value_adv=0
            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue
            if  move.move_type == 'out_invoice':
                tax_json=json.loads(self.tax_totals_json)
                tax_value=tax_json['amount_total']-tax_json['amount_untaxed']

            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
            advance_account_ids = [move.commercial_partner_id.advance_account_payable_id.id,
            move.commercial_partner_id.advance_account_receivable_id.id]
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
                if tax_value!=0 and  self.move_type == 'out_invoice' and line.account_id.advanced\
                    and line.move_id.payment_id  and line.move_id.payment_id.is_taxed and line.move_id.payment_id.total_tax_amount>0 :
                    tax_value_adv=line.move_id.payment_id.total_tax_amount
                    if line.currency_id == move.currency_id:
                        # Same foreign currency.
                        amount = abs(line.amount_residual_currency)+abs(tax_value_adv)
                    else:
                        # Different foreign currencies.
                        amount = move.company_currency_id._convert(
                            abs(line.amount_residual)+abs(tax_value_adv),
                            move.currency_id,
                            move.company_id,
                            line.date,
                        )
                else:
                    if line.currency_id == move.currency_id:
                        # Same foreign currency.
                        amount = abs(line.amount_residual_currency)
                    else:
                        # Different foreign currencies.
                        amount = move.company_currency_id._convert(
                            abs(line.amount_residual),
                            move.currency_id,
                            move.company_id,
                            line.date,
                        )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency': move.currency_id.symbol,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'position': move.currency_id.position,
                    'digits': [69, move.currency_id.decimal_places],
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                    'is_advance': line.account_id.advanced or False,
                    'tax_value_adv': tax_value_adv
                    
                })

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = json.dumps(payments_widget_vals)
            move.invoice_has_outstanding = True


    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.env['account.move.line'].search([('account_id.advanced', '=', True)]) +self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials =  pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
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

                ref = counterpart_line.move_id.name
                if counterpart_line.move_id.ref:
                    ref += ' (' + counterpart_line.move_id.ref + ')'

                reconciled_vals.append({
                    'name': counterpart_line.name,
                    'journal_name': counterpart_line.journal_id.name,
                    'amount': amount,
                    'currency': self.currency_id.symbol,
                    'digits': [69, self.currency_id.decimal_places],
                    'position': self.currency_id.position,
                    'date': counterpart_line.date,
                    'payment_id': counterpart_line.id,
                    'account_payment_id': counterpart_line.payment_id.id,
                    'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                    'move_id': counterpart_line.move_id.id,
                    'ref': ref,
                })
        return reconciled_vals

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
        journal_date=datetime.date(datetime.now())
        # recoceled = False
        tax_account=self.env['account.tax'].search([('type_tax_use','=','sale')
                                            ,('company_id','=',self.env.company.id)]).tax_group_id.property_tax_receivable_account_id.id
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
                tax_json=json.loads(self.tax_totals_json)
                tax_value=tax_json['amount_total']-tax_json['amount_untaxed']

            if tax_value!=0 and  self.move_type == 'out_invoice':
                widg=json.loads(self.invoice_outstanding_credits_debits_widget)
                if widg['outstanding']:
                    for wg in widg['content']:
                        if wg['id']==line_id:
                            amount_adv=wg['amount']-wg['tax_value_adv']
                            tax_value_adv=wg['tax_value_adv']
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
                    self.amount_residual=self.currency_id._convert( self.amount_residual, company.currency_id, company, self.date)

                if abs(self.amount_residual) <= abs(lines[0].amount_residual) +abs(tax_value_adv) :
                    value=self.amount_residual
                    amount = abs(lines[0].amount_residual) +abs(tax_value_adv)- (self.amount_residual)
                    full_reconcile=True
                    for l in lines[0].move_id.line_ids:
                        if l.amount_residual_currency:
                            l.write({'amount_residual_currency': (abs(l.amount_residual) / l.amount_residual) * (
                                        l.amount_residual_currency * amount / abs(lines[0].amount_residual))})
                        if l.amount_residual!=0:
                            l.write({'amount_residual': (abs(l.amount_residual) / l.amount_residual) * amount})
                else:
                    if lines[0].amount_residual>=0:
                        value=lines[0].amount_residual+tax_value_adv
                    else:
                        value=lines[0].amount_residual-tax_value_adv
                    lines[0].write({'amount_residual':0})
                    if lines[0].amount_residual_currency:
                        lines[0].write({'amount_residual_currency': 0})
                    lines[0].write({'reconciled':True})

            
            if other:#check here
                credit_value['amount_currency'] = -value
                credit_value['currency_id'] = self.currency_id.id
                credit_value['credit'] = self.currency_id._convert(abs(value), company.currency_id, company, self.date)
            else: 
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

            if value>0:
                vsign=1
            else:
                vsign=-1
            
            if tax_value!=0 and  self.move_type == 'out_invoice' and full_reconcile:
                tax_value_adv=tax_value

            if other:
                debit_value['amount_currency'] =vsign* (abs(value)-tax_value_adv)
                debit_value_tax['currency_id'] = self.currency_id.id
                if tax_value!=0 and  self.move_type == 'out_invoice':
                    debit_value_tax['amount_currency'] = vsign*tax_value_adv
                    debit_value_tax['currency_id'] = self.currency_id.id
                    debit_value['debit'] =self.currency_id._convert(abs(value)-abs(tax_value_adv), company.currency_id, company, self.date)
                    debit_value_tax['debit'] =self.currency_id._convert(abs(tax_value_adv), company.currency_id, company, self.date)

                else:
                    debit_value['debit'] =self.currency_id._convert(abs(value), company.currency_id, company, self.date)
            else:
                if tax_value!=0 and  self.move_type == 'out_invoice':
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

            if 'report_credit' in lines[0].fields_get() and lines[0].move_id.report_currency_exchange_rate:
                cc = self.env['account.move'].create({
                    'move_type': 'entry',
                    'date': journal_date,
                    'journal_id': self.journal_id.id,
                    'company_id': self.company_id.id,
                    'line_ids': new_line_ids,
                    'report_currency_exchange_rate':lines[0].move_id.report_currency_exchange_rate
                }).id

            else:
                # case customer+tax is here
                cc= self.env['account.move'].create({
                        'move_type': 'entry',
                        'date': journal_date,
                        'journal_id': self.journal_id.id,
                        'company_id': self.company_id.id,
                        'line_ids': new_line_ids
                     }).id
            move=self.env['account.move'].browse(cc)
            move.write({'name': cc})
            move.write({'state':'posted'})
            move.write({'advanced_payment':lines[0].payment_id.id})

            lines = self.env['account.move.line'].search([('move_id','=',cc),('account_id','=',account)])
            lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
            return lines.reconcile()
        else:
            return super().js_assign_outstanding_line(line_id)


from datetime import datetime, date

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare
from json import dumps
import json

class Reevaluationline(models.Model):
    _name = "reevaluationline"
    name= fields.Char()
    debit = fields.Float(string='debit', digits=(12, 2))
    credit = fields.Float(string='credit', digits=(12, 2))
    currency_id = fields.Many2one('res.currency',  string="Currency")
    amount_currency = fields.Monetary()

    reevaluation_id = fields.Many2one('reevaluation', 'reevaluation id')
    account_id = fields.Many2one('account.account', string='Account', index=True)
    partner_id = fields.Many2one('res.partner', string="Partner")
class Reevaluation(models.Model):
    _name = "reevaluation"
    @api.onchange('date')
    def _get_reevaluation_account_line_ids(self):
        accounts = self.env['account.account'].search(
            [('currency_revaluation', '=', True),('user_type_id.name', '!=', 'Bank and Cash'), ('user_type_id.type', 'not in', ('receivable', 'payable'))])
        rals = []
        line = {}
        revals= self.env['reevaluation'].search([('state', '=', 'posted')]).mapped('date')
        if revals:
            max_date=max(dat for dat in revals)
            last_reval = self.env['reevaluation'].search([('date', '=', max_date)])
        for account in accounts:
            if revals:
                lines = self.env['account.move.line'].search(
                    [('account_id', '=', account.id), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                     ('date', '<=', self.date),('date', '>', max_date)])
            else:
                lines = self.env['account.move.line'].search(
                    [('account_id', '=', account.id), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                     ('date', '<=', self.date)])

            currencies = set(lines.mapped('currency_id'))
            if revals:
                currencies = set(
                    lines.mapped('currency_id') + last_reval.reevaluation_account_line_ids.mapped(('currency_id')))
            for currency in currencies:
                currency_lines = lines.filtered(lambda  s : s.currency_id.id==currency.id)
                balance = sum(currency_lines.mapped('balance'))
                currency_balance = sum(currency_lines.mapped('amount_currency'))
                if revals:
                    old_balance_line = last_reval.reevaluation_account_line_ids.filtered(lambda  s:
                    s.currency_id.id == currency.id and s.account_id == account )
                    if old_balance_line:
                        currency_balance += old_balance_line.foreign_currency_balance
                        balance += old_balance_line.new_main_currency_balance
                rates = self.currency_rate_ids.search([('currency_id', '=', currency.id)])
                if rates:
                    rate = rates.rate
                else:
                    from_currency = currency
                    to_currency = self.env.company.currency_id
                    company = self.env.company
                    rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                                         self.date)
                new_balance = rate * currency_balance
                adjastment = new_balance - balance
                digits_rounding_precision = self.env.company.currency_id.rounding


                if not float_is_zero(adjastment+currency_balance,precision_rounding=digits_rounding_precision):
                    line = {
                        'account_id': account.id,
                        'currency_id': currency.id,
                        'foreign_currency_balance': currency_balance,
                        'main_currency_balance': balance,
                        'new_main_currency_balance': new_balance,
                        'adjustment_value': adjastment

                    }
                    rals.append((0,0,line))
        self.write({'reevaluation_account_line_ids': [(5, 0, 0)]})
        self.write({'reevaluation_account_line_ids': rals})

    @api.onchange('date')
    def _get_reevaluation_cash_account_line_ids(self):
        params = self.env['ir.config_parameter'].sudo()
        Allow_base_currency_accounts = bool(params.get_param('Allow_base_currency_accounts'))

        if Allow_base_currency_accounts:

            accounts = self.env['account.account'].search([ ('user_type_id.name', '=', 'Bank and Cash')])
        else:
            cur_id=self.env.company.currency_id
            accounts = self.env['account.account'].search([('user_type_id.name', '=', 'Bank and Cash'),('currency_id','!=',False)])
        rals = []
        line = {}
        revals = self.env['reevaluation'].search([('state', '=', 'posted')]).mapped('date')
        if revals:
            max_date = max(dat for dat in revals)
            last_reval = self.env['reevaluation'].search([('date', '=', max_date)])

        for account in accounts:

            if revals:
                lines = self.env['account.move.line'].search(
                    [('account_id', '=', account.id), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                     ('date', '<=', self.date), ('date', '>', max_date)])
            else:
                lines = self.env['account.move.line'].search(
                    [('account_id', '=', account.id), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                     ('date', '<=', self.date)])

            currencies = set(lines.mapped('currency_id'))
            if revals:
                currencies = set(
                    lines.mapped('currency_id') + last_reval.reevaluation_cash_account_line_ids.mapped(('currency_id')))
            for currency in currencies:
                currency_lines = lines.filtered(lambda s: s.currency_id.id == currency.id)

                balance = sum(currency_lines.mapped('balance'))
                currency_balance = sum(currency_lines.mapped('amount_currency'))
                if revals:
                    old_balance_line = last_reval.reevaluation_cash_account_line_ids.filtered(lambda s:
                                                                                         s.currency_id.id == currency.id and s.account_id == account)
                    if old_balance_line:
                        currency_balance += old_balance_line.foreign_currency_balance
                        balance += old_balance_line.new_main_currency_balance
                rates = self.currency_rate_ids.search([('currency_id', '=', currency.id)])
                if rates:
                    rate = rates.rate
                else:
                    from_currency = currency
                    to_currency = self.env.company.currency_id
                    company = self.env.company
                    rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                                         self.date)

                new_balance = rate * currency_balance
                adjastment = new_balance - balance
                digits_rounding_precision = self.env.company.currency_id.rounding

                if not float_is_zero(adjastment+currency_balance, precision_rounding=digits_rounding_precision):
                    line = {
                        'account_id': account.id,
                        'currency_id': currency.id,
                        'foreign_currency_balance': currency_balance,
                        'main_currency_balance': balance,
                        'new_main_currency_balance': new_balance,
                        'adjustment_value': adjastment

                    }
                    rals.append((0, 0, line))
        self.write({'reevaluation_cash_account_line_ids': [(5, 0, 0)]})
        self.write({'reevaluation_cash_account_line_ids': rals})

    @api.onchange('date')
    def _get_reevaluation_partner_line_ids(self):
        accounts = self.env['account.account'].search(
            [('user_type_id.type', 'in', ('receivable', 'payable'))]).mapped('id')

        re_accounts = self.env['account.account'].search(
            [('user_type_id.type', '=', 'receivable')]).mapped('id')
        pa_accounts = self.env['account.account'].search(
            [('user_type_id.type', '=', 'payable')]).mapped('id')
        rals = []
        line = {}
        revals = self.env['reevaluation'].search([('state', '=', 'posted')]).mapped('date')
        if revals:
            max_date = max(dat for dat in revals)
            last_reval=self.env['reevaluation'].search([('date', '=', max_date)])

            re_lines = self.env['account.move.line'].search(
                [('account_id', 'in', re_accounts), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                 ('date', '<=', self.date),('date', '>', max_date)])
            pa_lines = self.env['account.move.line'].search(
                [('account_id', 'in', pa_accounts), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                 ('date', '<=', self.date),('date', '>', max_date)])
        else:

            re_lines = self.env['account.move.line'].search(
                [('account_id', 'in', re_accounts), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                 ('date', '<=', self.date)])
            pa_lines = self.env['account.move.line'].search(
                [('account_id', 'in', pa_accounts), ('currency_id', '!=', False), ('move_id.state', '=', 'posted'),
                 ('date', '<=', self.date)])
        old_re=re_lines.mapped('partner_id')
        old_pa=pa_lines.mapped('partner_id')

        re_partners = set(re_lines.mapped('partner_id'))
        pa_partners = set(pa_lines.mapped('partner_id'))
        if revals:
            old_re_partners = last_reval.reevaluation_partner_line_ids

            old_pa_partners = last_reval.reevaluation_partner_line_ids
            re_partners = set(re_lines.mapped('partner_id') + old_re_partners.mapped('partner_id'))
            pa_partners = set(pa_lines.mapped('partner_id') + old_pa_partners.mapped('partner_id'))
        for parnter in re_partners:
                  plines=re_lines.filtered(lambda quant: quant.partner_id.id == parnter.id)
                  currencies = set(plines.mapped('currency_id'))
                  if revals:
                      currencies = set(plines.mapped('currency_id') + old_re_partners.mapped('currency_id'))

                  for currency in currencies:
                    currency_lines = plines.filtered(lambda quant: quant.currency_id.id == currency.id)

                    balance = sum(line.balance for line in currency_lines)
                    currency_balance = sum(currency_lines.mapped('amount_currency'))
                    rates = self.currency_rate_ids.search([('currency_id', '=', currency.id)])
                    if revals:
                        parnter_account=parnter.property_account_receivable_id
                        if not isinstance(parnter_account.id, int):
                            parnter_account=parnter_account.id
                        old_balance_line=last_reval.reevaluation_partner_line_ids.filtered(lambda  s:
                            s.account_id == parnter_account and
                            s.currency_id.id == currency.id and s.partner_id.id == parnter.id)
                        if old_balance_line:
                            currency_balance += old_balance_line.foreign_currency_balance
                            balance += old_balance_line.new_main_currency_balance
                    if rates:
                        rate = rates.rate
                    else:
                        from_currency = currency
                        to_currency = self.env.company.currency_id
                        company = self.env.company
                        rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                                             self.date)
                    new_balance = rate * currency_balance
                    adjastment = new_balance - balance
                    digits_rounding_precision = self.env.company.currency_id.rounding

                    if not float_is_zero(adjastment+currency_balance, precision_rounding=digits_rounding_precision):
                        line = {
                            'account_id':parnter.property_account_receivable_id.id,
                            'currency_id': currency.id,
                            'foreign_currency_balance': currency_balance,
                            'main_currency_balance': balance,
                            'new_main_currency_balance': new_balance,
                            'adjustment_value': adjastment,
                            'partner_id':parnter.id,


                        }
                        rals.append((0, 0, line))
        for parnter in pa_partners:
            plines = pa_lines.filtered(lambda quant: quant.partner_id == parnter)
            currencies = set(plines.mapped('currency_id'))
            if revals:
                currencies = set(plines.mapped('currency_id')+old_pa_partners.mapped('currency_id'))
            for currency in currencies:
                currency_lines = plines.filtered(lambda quant: quant.currency_id.id == currency.id)


                balance = sum(currency_lines.mapped('balance'))
                currency_balance = sum(currency_lines.mapped('amount_currency'))
                rates = self.currency_rate_ids.search([('currency_id', '=', currency.id)])
                if revals:
                    parnter_account=parnter.property_account_payable_id
                    if not isinstance(parnter_account.id, int):
                        parnter_account = parnter_account.id
                    old_balance_line = last_reval.reevaluation_partner_line_ids.filtered(lambda s:
                        s.account_id == parnter_account and
                         s.currency_id == currency and s.partner_id==parnter)
                    if old_balance_line:
                        currency_balance += old_balance_line.foreign_currency_balance
                        balance += old_balance_line.new_main_currency_balance
                if rates:
                    rate = rates.rate
                else:
                    from_currency = currency
                    to_currency = self.env.company.currency_id
                    company = self.env.company
                    rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                                         self.date)

                new_balance = rate * currency_balance
                adjastment = new_balance - balance
                digits_rounding_precision = self.env.company.currency_id.rounding

                if not float_is_zero(adjastment, precision_rounding=digits_rounding_precision):
                    line = {
                        'account_id': parnter.property_account_payable_id.id,
                        'currency_id': currency.id,
                        'foreign_currency_balance': currency_balance,
                        'main_currency_balance': balance,
                        'new_main_currency_balance': new_balance,
                        'adjustment_value': adjastment,
                        'partner_id': parnter.id

                    }
                    rals.append((0, 0, line))
        # if revals:
        #     for line in old_re_partners:
        #         from_currency = line.currency_id
        #         to_currency = self.env.company.currency_id
        #         company = self.env.company
        #         rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
        #                                                              self.date)
        #         balance=line.main_currency_balance
        #         currency_balance=line.foreign_currency_balance
        #         new_balance = rate * currency_balance
        #         adjastment = new_balance - balance
        #         digits_rounding_precision = self.env.company.currency_id.rounding
        #
        #         if not float_is_zero(adjastment, precision_rounding=digits_rounding_precision):
        #             line = {
        #                 'account_id': line.account_id.id,
        #                 'currency_id': line.currency_id.id,
        #                 'foreign_currency_balance': currency_balance,
        #                 'main_currency_balance': balance,
        #                 'new_main_currency_balance': new_balance,
        #                 'adjustment_value': adjastment,
        #                 'partner_id': line.partner_id.id,
        #
        #             }
        #             rals.append((0, 0, line))
        #     for line in old_pa_partners:
        #         from_currency = line.currency_id
        #         to_currency = self.env.company.currency_id
        #         company = self.env.company
        #         rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
        #                                                              self.date)
        #         balance = line.main_currency_balance
        #         currency_balance = line.foreign_currency_balance
        #         new_balance = rate * currency_balance
        #         adjastment = new_balance - balance
        #         digits_rounding_precision = self.env.company.currency_id.rounding
        #
        #         if not float_is_zero(adjastment, precision_rounding=digits_rounding_precision):
        #             line = {
        #                 'account_id': line.account_id.id,
        #                 'currency_id': line.currency_id.id,
        #                 'foreign_currency_balance': currency_balance,
        #                 'main_currency_balance': balance,
        #                 'new_main_currency_balance': new_balance,
        #                 'adjustment_value': adjastment,
        #                 'partner_id': line.partner_id.id,
        #
        #             }
        #             rals.append((0, 0, line))


        self.write({'reevaluation_partner_line_ids': [(5, 0, 0)]})
        self.write({'reevaluation_partner_line_ids': rals})

    def _get_default_now(self):
        return fields.Date.today()
    @api.onchange('reevaluation_partner_line_ids')
    def _create_jv(self):
        company=self.env.company
        lines=[]
        if not company.currency_exchange_journal_id:
            raise UserError(_("You should configure the 'Exchange Rate Journal' in the accounting settings, ."))
        exchange_journal = company.currency_exchange_journal_id
        balance= sum(  round(lin.adjustment_value, 2) for lin in self.reevaluation_cash_account_line_ids)+sum( round(li.adjustment_value, 2) for li in self.reevaluation_account_line_ids)+sum( round(line.adjustment_value, 2) for line in self.reevaluation_partner_line_ids)
        line={
            'name': _('Revaluation'),
            'debit': balance < 0 and -balance or 0.0,
            'credit': balance > 0 and balance or 0.0,
            'account_id': balance > 0 and exchange_journal.company_id.income_currency_exchange_account_id.id or exchange_journal.company_id.expense_currency_exchange_account_id.id,


        }
        lines.append((0,0,line))
        for par in self.reevaluation_partner_line_ids:
            line_acc = {
                'name': _('Currency exchange rate difference'),
                'credit': par.adjustment_value < 0 and -par.adjustment_value or 0.0,
                'debit': par.adjustment_value > 0 and par.adjustment_value or 0.0,
                'account_id':par.account_id,
                'partner_id': par.partner_id.id,
                "currency_id": par.currency_id.id,
                "amount_currency": 0.0,

            }
            lines.append((0, 0, line_acc))
        for acc in self.reevaluation_account_line_ids:
            line_acc = {
                'name': _('Currency exchange rate difference'),
                'credit': acc.adjustment_value < 0 and -acc.adjustment_value or 0.0,
                'debit': acc.adjustment_value > 0 and acc.adjustment_value or 0.0,
                'account_id':acc.account_id.id ,
                'currency_id': acc.currency_id.id,
                'amount_currency': 0.0,


            }
            lines.append((0, 0, line_acc))
        for accc in self.reevaluation_cash_account_line_ids:
            line_accc = {
                'name': _('Currency exchange rate difference'),
                'credit': accc.adjustment_value < 0 and -accc.adjustment_value or 0.0,
                'debit': accc.adjustment_value > 0 and accc.adjustment_value or 0.0,
                'account_id':accc.account_id.id ,
                'currency_id': accc.currency_id.id,
                'amount_currency': 0.0,


            }
            lines.append((0, 0, line_accc))

        jv= {

                'journal_id': exchange_journal.id,
                'move_type': 'entry',
                'ref': self.name,

                'company_id': self.env.company.id,
                'date': self.date,
                'line_ids':lines

        }

        self.write({'account_move_id': jv})
        self.write({'line_ids': [(5, 0, 0)]})
        self.write({'line_ids': lines})

    def post(self):

        lines=[]
        revals = self.env['reevaluation'].search([('state', '=', 'posted')]).mapped('date')
        if not revals:

            data_unaffected_earnings = self.env.ref('account.data_unaffected_earnings')

            account_unaffected_earnings = self.env['account.account'].search([('user_type_id', '=', data_unaffected_earnings.id)])
            if(account_unaffected_earnings):
                lines_current_year = self.env['account.move.line'].search_count([('account_id','=',account_unaffected_earnings.id)])
                if(lines_current_year>0):
                    if(self.line_ids):
                        raise UserError(_("You Can Not Add Revaluation With Unclosed Account's Balance"))

        for par in self.line_ids:
            line_acc = {
                'name':par.name,
                'credit': par.credit,
                'debit': par.debit,
                'account_id':par.account_id.id,
                'partner_id': par.partner_id.id,
                "currency_id": par.currency_id.id,
                "amount_currency": 0.0,
                'amount_residual': 0.0,
                'amount_residual_currency': 0.0,
            }
            lines.append((0, 0, line_acc))
        res = self.env['account.move'].create({
            'journal_id': self.env.company.currency_exchange_journal_id.id,
            'move_type': 'entry',
            'ref': self.name,

            'company_id': self.env.company.id,
            'date': self.date,
            'line_ids': lines
        })
        move = self.env['account.move'].browse(res.id)
        move.write({'name': str(res.id)})

        move.write({'state': 'posted'})
        self.write({'account_move_id': res.id})
        self.write({'state': 'posted'})
        if self.lock_date:
            res=self.env['account.change.lock.date'].create({
                'fiscalyear_lock_date' : self.date
            })
            res.change_lock_date()

    name = fields.Char(string="name", required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today)
    lock_date = fields.Boolean(default=False)
    reevaluation_account_line_ids = fields.One2many('reevaluation_account_line', 'reevaluation_id')
    reevaluation_cash_account_line_ids = fields.One2many('reevaluation_cash_account_line', 'reevaluation_id')
    reevaluation_partner_line_ids = fields.One2many('reevaluation_partner_line', 'reevaluation_id')
    account_move_id = fields.Many2one('account.move', string="Journal Entry")
    line_ids=fields.One2many('reevaluationline', 'reevaluation_id')
    reevaluation_type= fields.Selection([('all', 'Since the beginning'), ('current', 'Since the Last One')],string='revaluation type' ,default='all')

    currency_rate_ids = fields.One2many('currency_rate', 'reevaluation_id')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')

    def action_get_all_account_moves(self):
        self.ensure_one()
        action_ref = self.env.ref('account.action_move_journal_line')
        if not action_ref:
            return False
        action_data = action_ref.read()[0]

        action_data['domain'] = [('id', '=', self.account_move_id.id)]
        return action_data


class CurrencyRate(models.Model):
    _name = "currency_rate"

    def _get_reevaluation_rates(self):
        reevaluation_rates = []
        lines = self.env['account.move.line'].search(
            [('currency_id', '!=', False), ('move_id.state', '=', 'posted')])
        currencies = set(lines.mapped('currency_id'))
        return currencies

    def _get_default_currency_rate(self):
        self.ensure_one()
        from_currency = self.currency_id
        to_currency = self.env.company.currency_id
        company = self.env.company
        return self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company,
                                                             datetime.datetime.now())

    rate= fields.Float(string='Currency Rate', digits=(6, 2),default=_get_default_currency_rate)
    currency_id = fields.Many2one('res.currency',  string="Currency",default=_get_reevaluation_rates)
    reevaluation_id = fields.Many2one('reevaluation','reevaluation id')
class ReevaluationAccountLine(models.Model):
    _name = "reevaluation_account_line"

    adjustment_value= fields.Float(string='adjustment value', digits=(12, 2))
    new_main_currency_balance = fields.Float(string='balance by new rate', digits=(12, 2))
    main_currency_balance = fields.Float(string='balance by transaction rate', digits=(12, 2))
    foreign_currency_balance = fields.Float(string='foreign currency balance', digits=(12, 2))
    currency_id = fields.Many2one('res.currency',  string="Currency")
    reevaluation_id = fields.Many2one('reevaluation','reevaluation id')
    account_id = fields.Many2one('account.account', string='Account', index=True)
class ReevaluationCashAccountLine(models.Model):
    _name = "reevaluation_cash_account_line"

    adjustment_value= fields.Float(string='adjustment value', digits=(12, 2))
    new_main_currency_balance = fields.Float(string='balance by new rate', digits=(12, 2))
    main_currency_balance = fields.Float(string='balance by transaction rate', digits=(12, 2))
    foreign_currency_balance = fields.Float(string='foreign currency balance', digits=(12, 2))
    currency_id = fields.Many2one('res.currency',  string="Currency")
    reevaluation_id = fields.Many2one('reevaluation','reevaluation id')
    account_id = fields.Many2one('account.account', string='Account', index=True)
class ReevaluationPartnerLine(models.Model):
    _name = "reevaluation_partner_line"

    adjustment_value = fields.Float(string='adjustment value', digits=(12, 2))
    new_main_currency_balance = fields.Float(string='balance by new rate', digits=(12, 2))
    main_currency_balance = fields.Float(string='balance by transaction rate', digits=(12, 2))
    foreign_currency_balance = fields.Float(string='foreign currency balance', digits=(12, 2))
    currency_id = fields.Many2one('res.currency', string="Currency")
    reevaluation_id = fields.Many2one('reevaluation', 'reevaluation id')
    account_id = fields.Many2one('account.account', string='Account', index=True)
    partner_id = fields.Many2one('res.partner', string="Partner")
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def check_full_reconcile(self):
        """
        This method check if a move is totally reconciled and if we need to create exchange rate entries for the move.
        In case exchange rate entries needs to be created, one will be created per currency present.
        In case of full reconciliation, all moves belonging to the reconciliation will belong to the same account_full_reconcile object.
        """
        # Get first all aml involved
        todo = self.env['account.partial.reconcile'].search_read(['|', ('debit_move_id', 'in', self.ids), ('credit_move_id', 'in', self.ids)], ['debit_move_id', 'credit_move_id'])
        amls = set(self.ids)
        seen = set()
        while todo:
            aml_ids = [rec['debit_move_id'][0] for rec in todo if rec['debit_move_id']] + [rec['credit_move_id'][0] for rec in todo if rec['credit_move_id']]
            amls |= set(aml_ids)
            seen |= set([rec['id'] for rec in todo])
            todo = self.env['account.partial.reconcile'].search_read(['&', '|', ('credit_move_id', 'in', aml_ids), ('debit_move_id', 'in', aml_ids), '!', ('id', 'in', list(seen))], ['debit_move_id', 'credit_move_id'])

        partial_rec_ids = list(seen)
        if not amls:
            return
        else:
            amls = self.browse(list(amls))

        # If we have multiple currency, we can only base ourselves on debit-credit to see if it is fully reconciled
        currency = set([a.currency_id for a in amls if a.currency_id.id != False])
        multiple_currency = False
        if len(currency) != 1:
            currency = False
            multiple_currency = True
        else:
            currency = list(currency)[0]
        # Get the sum(debit, credit, amount_currency) of all amls involved
        total_debit = 0
        total_credit = 0
        total_amount_currency = 0
        maxdate = date.min
        to_balance = {}
        cash_basis_partial = self.env['account.partial.reconcile']
        for aml in amls:
            cash_basis_partial |= aml.move_id.tax_cash_basis_rec_id
            total_debit += aml.debit
            total_credit += aml.credit
            maxdate = max(aml.date, maxdate)
            total_amount_currency += aml.amount_currency
            # Convert in currency if we only have one currency and no amount_currency
            if not aml.amount_currency and currency:
                multiple_currency = True
                total_amount_currency += aml.company_id.currency_id._convert(aml.balance, currency, aml.company_id, aml.date)
            # If we still have residual value, it means that this move might need to be balanced using an exchange rate entry
            if aml.amount_residual != 0 or aml.amount_residual_currency != 0:
                if not to_balance.get(aml.currency_id):
                    to_balance[aml.currency_id] = [self.env['account.move.line'], 0]
                to_balance[aml.currency_id][0] += aml
                to_balance[aml.currency_id][1] += aml.amount_residual != 0 and aml.amount_residual or aml.amount_residual_currency

        # Check if reconciliation is total
        # To check if reconciliation is total we have 3 different use case:
        # 1) There are multiple currency different than company currency, in that case we check using debit-credit
        # 2) We only have one currency which is different than company currency, in that case we check using amount_currency
        # 3) We have only one currency and some entries that don't have a secundary currency, in that case we check debit-credit
        #   or amount_currency.
        # 4) Cash basis full reconciliation
        #     - either none of the moves are cash basis reconciled, and we proceed
        #     - or some moves are cash basis reconciled and we make sure they are all fully reconciled

        digits_rounding_precision = amls[0].company_id.currency_id.rounding
        if (
                (
                    not cash_basis_partial or (cash_basis_partial and all([p >= 1.0 for p in amls._get_matched_percentage().values()]))
                ) and
                (
                    currency and float_is_zero(total_amount_currency, precision_rounding=currency.rounding) or
                    multiple_currency and float_compare(total_debit, total_credit, precision_rounding=digits_rounding_precision) == 0
                )
        ):

            exchange_move_id = False
            missing_exchange_difference = False
            # Eventually create a journal entry to book the difference due to foreign currency's exchange rate that fluctuates
            # if to_balance and any([not float_is_zero(residual, precision_rounding=digits_rounding_precision) for aml, residual in to_balance.values()]):
            #     if not self.env.context.get('no_exchange_difference'):
            #         exchange_move = self.env['account.move'].with_context(default_type='entry').create(
            #             self.env['account.full.reconcile']._prepare_exchange_diff_move(move_date=maxdate, company=amls[0].company_id))
            #         part_reconcile = self.env['account.partial.reconcile']
            #         for aml_to_balance, total in to_balance.values():
            #             if total:
            #                 rate_diff_amls, rate_diff_partial_rec = part_reconcile.create_exchange_rate_entry(aml_to_balance, exchange_move)
            #                 amls += rate_diff_amls
            #                 partial_rec_ids += rate_diff_partial_rec.ids
            #             else:
            #                 aml_to_balance.reconcile()
            #         exchange_move.post()
            #         exchange_move_id = exchange_move.id
            #     else:
            #         missing_exchange_difference = True
            # if not missing_exchange_difference:
            #     #mark the reference of the full reconciliation on the exchange rate entries and on the entries
            #     self.env['account.full.reconcile'].create({
            #         'partial_reconcile_ids': [(6, 0, partial_rec_ids)],
            #         'reconciled_line_ids': [(6, 0, amls.ids)],
            #         'exchange_move_id': exchange_move_id,
            #     })
class AccountMove(models.Model):
    _inherit = "account.move"

    def _compute_payments_widget_to_reconcile_info(self):
        exchange_journal = self.env.company.currency_exchange_journal_id
        for move in self:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False

            if move.state != 'posted' or move.invoice_payment_state != 'not_paid' or not move.is_invoice(include_receipts=True):
                continue
            pay_term_lines = move.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            if move.is_inbound():
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'move_id': move.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = move.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == move.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        currency = line.company_id.currency_id
                        amount_to_show = currency._convert(abs(line.amount_residual), move.currency_id, move.company_id,
                                                           line.date or fields.Date.today())
                    if float_is_zero(amount_to_show, precision_rounding=move.currency_id.rounding):
                        continue
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, move.currency_id.decimal_places],
                        'payment_date': fields.Date.to_string(line.date),
                    })
                info['title'] = type_payment
                move.invoice_outstanding_credits_debits_widget = json.dumps(info)
                move.invoice_has_outstanding = True



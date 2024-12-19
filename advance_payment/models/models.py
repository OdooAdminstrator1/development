
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools, _lt
from odoo.tools import float_is_zero, format_date
from datetime import timedelta, datetime, date
from json import dumps

import json

class Advance_payment(models.Model):

    _inherit = ["res.partner"]


    advance_account_payable_id = fields.Many2one("account.account", company_dependent=True,
                                                  string="Vendor Advanced Account",
                                                  domain="[('user_type_id', '=', 'Current Assets'), ('deprecated', '=', False),('advanced','=',True)]",
                                                  help="This account will be used instead of the default one as the payable account for the current partner"
                                                  )
    advance_account_receivable_id = fields.Many2one("account.account", company_dependent=True,
                                                     string="Customer Advanced Account",
                                                     domain="[('user_type_id', '=', 'Current Liabilities'), ('deprecated', '=', False) ,('advanced','=',True)]",
                                                     help="This account will be used instead of the default one as the advance receivable account for the current partner"
                                                    )
class AccountAccount(models.Model):
    _inherit = 'account.account'

    advanced = fields.Boolean(index=True, default=False , string="Advanced Account")

    @api.constrains('user_type_id')
    def _check_user_type_id(self):
        data_unaffected_earnings = self.env.ref('account.data_unaffected_earnings')
        data_account_type_current_liabilities= self.env.ref('account.data_account_type_current_liabilities')
        data_account_type_current_assets= self.env.ref('account.data_account_type_current_assets')
        result = self.read_group([('user_type_id', '=', data_unaffected_earnings.id)], ['company_id'], ['company_id'])
        for res in result:
            if res.get('company_id_count', 0) >= 2:
                account_unaffected_earnings = self.search([('company_id', '=', res['company_id'][0]),
                                                           ('user_type_id', '=', data_unaffected_earnings.id)])
                raise ValidationError(_('You cannot have more than one account with "Current Year Earnings" as type. (accounts: %s)') % [a.code for a in account_unaffected_earnings])
        if self.user_type_id not in (data_account_type_current_liabilities,data_account_type_current_assets) and self.advanced:
            raise ValidationError('Avanced Account must be current_liabilities or current_assets')
class AccountPaymentJournalReturned(models.Model):
    _name = "account.payment.journal.returned"
    returned_journal_id = fields.Many2one('account.journal', string='Returned Journal',

                                          domain="[('type', 'in', ('bank', 'cash'))]")
    payment_id=fields.Many2one('account.payment',readonly=True)

    @api.model
    def create(self, vals_list):
        res=super(AccountPaymentJournalReturned, self).create(vals_list)
        res.payment_id.close_payment(res.returned_journal_id)
        return  res


    def closeEitDialog(self):
        self.ensure_one()
        # close popup
        return {'type': 'ir.actions.act_window_close'}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _synchronize_from_moves(self, changed_fields):
        not_advance_count = self.with_context(skip_account_move_synchronization=True).filtered(lambda v: v.advance_ok != True)
        if len(not_advance_count) > 0:
            return super(AccountPayment, self)._synchronize_from_moves(changed_fields)
        else:
            return

    @api.depends('move_line_ids.matched_debit_ids', 'move_line_ids.matched_credit_ids')
    def _compute_reconciled_invoice_ids(self):
        for record in self:
            if not self.advance_ok:
                reconciled_moves = record.move_line_ids.mapped('matched_debit_ids.debit_move_id.move_id') \
                                   + record.move_line_ids.mapped('matched_credit_ids.credit_move_id.move_id')
                record.reconciled_invoice_ids = reconciled_moves.filtered(lambda move: move.is_invoice())
                record.has_invoices = bool(record.reconciled_invoice_ids)
                record.reconciled_invoices_count = len(record.reconciled_invoice_ids)
            else:
                reconciles_moves= self.env['account.move'].search([('advanced_payment','=',record.id)])
                if reconciles_moves:
                    for move in reconciles_moves:
                        reconciled_moves = move.line_ids.mapped('matched_debit_ids.debit_move_id.move_id') \
                                           + move.line_ids.mapped('matched_credit_ids.credit_move_id.move_id')
                        record.reconciled_invoice_ids += reconciled_moves.filtered(lambda move: move.is_invoice())
                    record.has_invoices = bool(record.reconciled_invoice_ids)
                    record.reconciled_invoices_count = len(record.reconciled_invoice_ids)
                else:
                    reconciled_moves = record.move_line_ids.mapped('matched_debit_ids.debit_move_id.move_id') \
                                       + record.move_line_ids.mapped('matched_credit_ids.credit_move_id.move_id')
                    record.reconciled_invoice_ids = reconciled_moves.filtered(lambda move: move.is_invoice())
                    record.has_invoices = bool(record.reconciled_invoice_ids)
                    record.reconciled_invoices_count = len(record.reconciled_invoice_ids)


    def Show_close_payment(self):
        self.ensure_one()

        return {
                'type': 'ir.actions.act_window',
                'name': 'Close Payment',
                'view_type': 'form',
                'view_mode': 'form',
                'nodestroy': True,
                'flags': {'action_buttons': True},
                'res_model': 'account.payment.journal.returned',
                'target': 'new',
                'domain': [('payment_id', '=', self.id)],
                'context': { 'default_payment_id': self.id }
        }

    def _can_close(self):
        lines = self.move_id.line_ids.filtered(lambda line: not line.reconciled and line.account_id.advanced)


        if lines and self.advance_ok and lines[0].amount_residual>0.0  :
            self.can_close=True
        else:
            self.can_close=False
        return  self.can_close

    can_close=fields.Boolean(string='advanced Payment',compute="_can_close")
    advance_ok = fields.Boolean(
        string='advanced Payment',
        help="Select if you want to establish a features of advance")


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

    def close_payment(self,journalId):

        new_line_ids = []
        credit_value = {}
        debit_value = {}
        value = 0
        recoceled = False

        company = self.env.company

        if journalId:
            returned_account= journalId.default_credit_account_id.id

        # lines=self.move_line_ids.filtered(lambda line: not line.reconciled and line.credit > 0.0)
        lines = self.move_line_ids.filtered(lambda line: not line.reconciled and line.account_id.advanced)


        if lines[0].account_id.advanced:
            value = lines[0].amount_residual
            if 'manual_payment_rate' in self.fields_get():
                if self.apply_manual_currency_exchange:
                    self = self.with_context(manual_rate=self.manual_payment_rate,
                                             active_manutal_currency=self.apply_manual_currency_exchange,
                                             )

            lines[0].write({'amount_residual': 0})
            lines[0].write({'reconciled': True})
            if 'report_credit' in lines[0].fields_get():
                credit_value['report_credit'] = abs(value*lines[0].report_balance/lines[0].balance)
            if 'manual_payment_rate' in self.fields_get():
                if self.apply_manual_currency_exchange:
                    self = self.with_context(manual_rate=self.manual_payment_rate,
                                             active_manutal_currency=self.apply_manual_currency_exchange,
                                             )

            credit_value['credit'] = abs(value)
            credit_value['move_id'] = False
            credit_value['id'] = False
            if value>0:
                credit_value['account_id'] = lines[0].account_id.id
            else:
                credit_value['account_id'] = returned_account
            credit_value['company_id'] = lines[0].company_id.id
            credit_value['amount_residual'] = 0
            credit_value['currency_id'] = lines[0].currency_id.id
            credit_value['parent_state'] = 'posted'
            credit_value['partner_id'] = lines[0].partner_id.id
            credit_value['date'] = datetime.date(datetime.now())
            if lines[0].currency_id.rate:
                credit_value['amount_currency'] = lines[0].currency_id.round(-value * lines[0].currency_id.rate)

            debit_value['debit'] = abs(value)
            if 'report_debit' in lines[0].fields_get():
                debit_value['report_debit'] = abs(value)*lines[0].report_balance/lines[0].balance
            debit_value['move_id'] = False
            debit_value['id'] = False
            if value>0:
             debit_value['account_id'] = returned_account
            else:
                debit_value['account_id'] = lines[0].account_id.id
            debit_value['company_id'] = lines[0].company_id.id
            debit_value['amount_residual'] = 0
            debit_value['currency_id'] = lines[0].currency_id.id
            debit_value['parent_state'] = 'posted'
            debit_value['partner_id'] = lines[0].partner_id.id
            debit_value['date'] = datetime.date(datetime.now())
            if lines[0].currency_id.rate:
                debit_value['amount_currency'] = lines[0].currency_id.round(value * lines[0].currency_id.rate)

            # for line in self.line_ids:
            #     new_line_ids.append((0,0,line))

            new_line_ids.append((0, 0, credit_value))
            new_line_ids.append((0, 0, debit_value))
            cc = self.env['account.move'].create({

                'move_type': 'entry',
                'date': datetime.date(datetime.now()),
                'journal_id': journalId.id,
                'company_id': self.company_id.id,
                'line_ids': new_line_ids
            }).id
            move = self.env['account.move'].browse(cc)
            move.write({'name': cc})
            move.write({'state': 'posted'})
            for line in move.line_ids:
                line.write({'amount_residual': 0})
            return {'type': 'ir.actions.act_window_close'}
class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.partner.ledger"


    filter_date = {'mode': 'range', 'filter': 'this_year'}
    filter_all_entries = False
    filter_unfold_all = False
    filter_account_type = [
        {'id': 'receivable', 'name': _lt('Receivable'), 'selected': True},
        {'id': 'payable', 'name': _lt('Payable'), 'selected': True},
        {'id': 'other','name': _lt('Advanced'), 'selected': False},
    ]
    filter_unreconciled = False
    filter_partner = True

    @api.model
    def _get_templates(self):
        templates = super(ReportPartnerLedger, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template_partner_ledger_report'
        return templates

    ####################################################
    # OPTIONS
    ####################################################

    @api.model
    def _get_options_account_type(self, options):
        ''' Get select account type in the filter widget (see filter_account_type).
        :param options: The report options.
        :return:        Selected account types.
        '''
        all_account_types = []
        account_types = []
        for account_type_option in options.get('account_type', []):
            if account_type_option['selected']:
                account_types.append(account_type_option)
            all_account_types.append(account_type_option)
        return account_types or all_account_types

    @api.model
    def _get_options_domain(self, options):
        domain = super()._get_options_domain(options)
        if options.get('unreconciled'):
            domain.append(('full_reconcile_id', '=', False))

        domain.append('|')

        domain.append(('account_id.advanced', '=', True))
        domain.append(('account_id.internal_type', 'in', ('receivable', 'payable')))

        # Partner must be set.
        domain.append(('partner_id', '!=', False))

        return domain

    @api.model
    def _get_options_sum_balance(self, options):
        ''' Create options with the 'strict_range' enabled on the filter_date.
        The resulting dates domain will be:
        [
            ('date' <= options['date_to']),
            ('date' >= options['date_from'])
        ]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options['date'] = new_options['date'].copy()
        new_options['date']['strict_range'] = True
        return new_options

    @api.model
    def _get_options_initial_balance(self, options):
        ''' Create options used to compute the initial balances for each partner.
        The resulting dates domain will be:
        [('date' <= options['date_from'] - 1)]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options['date'] = new_options['date'].copy()
        new_date_to = fields.Date.from_string(new_options['date']['date_from']) - timedelta(days=1)
        new_options['date'].update({
            'date_from': False,
            'date_to': fields.Date.to_string(new_date_to),
        })
        return new_options

    ####################################################
    # QUERIES
    ####################################################

    @api.model
    def _get_query_sums(self, options, expanded_partner=None):
        ''' Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :param options:             The report options.
        :param expanded_partner:    An optional account.account record that must be specified when expanding a line
                                    with of without the load more.
        :return:                    (query, params)
        '''
        params = []
        queries = []

        if expanded_partner:
            domain = [('partner_id', '=', expanded_partner.id)]
        else:
            domain = []

        # Create the currency table.
        ct_query = self._get_query_currency_table(options)

        # Get sums for all partners.
        # period: [('date' <= options['date_to']), ('date' >= options['date_from'])]
        new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        params += where_params
        queries.append('''
            SELECT
                account_move_line.partner_id        AS groupby,
                'sum'                               AS key,
                SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
            FROM %s
            LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
            WHERE %s
            GROUP BY account_move_line.partner_id
        ''' % (tables, ct_query, where_clause))

        # Get sums for the initial balance.
        # period: [('date' <= options['date_from'] - 1)]
        new_options = self._get_options_initial_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        params += where_params
        queries.append('''
            SELECT
                account_move_line.partner_id        AS groupby,
                'initial_balance'                   AS key,
                SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
            FROM %s
            LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
            WHERE %s
            GROUP BY account_move_line.partner_id
        ''' % (tables, ct_query, where_clause))

        return ' UNION ALL '.join(queries), params

    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        ''' Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:             The report options.
        :param expanded_partner:    The res.partner record corresponding to the expanded line.
        :param offset:              The offset of the query (used by the load more).
        :param limit:               The limit of the query (used by the load more).
        :return:                    (query, params)
        '''
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        # Get sums for the account move lines.
        # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
        if expanded_partner:
            domain = [('partner_id', '=', expanded_partner.id)]
        elif unfold_all:
            domain = []
        elif options['unfolded_lines']:
            domain = [('partner_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]

        new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        ct_query = self._get_query_currency_table(options)

        query = '''
            SELECT
                account_move_line.id,
                account_move_line.date,
                account_move_line.date_maturity,
                account_move_line.name,
                account_move_line.ref,
                account_move_line.company_id,
                account_move_line.account_id,             
                account_move_line.payment_id,
                account_move_line.partner_id,
                account_move_line.currency_id,
                account_move_line.amount_currency,
                ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                account_move_line__move_id.name         AS move_name,
                company.currency_id                     AS company_currency_id,
                partner.name                            AS partner_name,
                account_move_line__move_id.type         AS move_type,
                account.code                            AS account_code,
                account.name                            AS account_name,
                journal.code                            AS journal_code,
                journal.name                            AS journal_name,
                full_rec.name                           AS full_rec_name
            FROM account_move_line
            LEFT JOIN account_move account_move_line__move_id ON account_move_line__move_id.id = account_move_line.move_id
            LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
            LEFT JOIN res_company company               ON company.id = account_move_line.company_id
            LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
            LEFT JOIN account_account account           ON account.id = account_move_line.account_id
            LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
            LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
            WHERE %s
            ORDER BY account_move_line.id
        ''' % (ct_query, where_clause)

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _do_query(self, options, expanded_partner=None):
        ''' Execute the queries, perform all the computation and return partners_results,
        a lists of tuple (partner, fetched_values) sorted by the table's model _order:
            - partner is a res.parter record.
            - fetched_values is a dictionary containing:
                - sum:                              {'debit': float, 'credit': float, 'balance': float}
                - (optional) initial_balance:       {'debit': float, 'credit': float, 'balance': float}
                - (optional) lines:                 [line_vals_1, line_vals_2, ...]
        :param options:             The report options.
        :param expanded_account:    An optional account.account record that must be specified when expanding a line
                                    with of without the load more.
        :param fetch_lines:         A flag to fetch the account.move.lines or not (the 'lines' key in accounts_values).
        :return:                    (accounts_values, taxes_results)
        '''
        company_currency = self.env.company.currency_id

        # Execute the queries and dispatch the results.
        query, params = self._get_query_sums(options, expanded_partner=expanded_partner)

        groupby_partners = {}

        self._cr.execute(query, params)
        for res in self._cr.dictfetchall():
            key = res['key']
            if key == 'sum':
                if not company_currency.is_zero(res['debit']) or not company_currency.is_zero(res['credit']):
                    groupby_partners.setdefault(res['groupby'], {})
                    groupby_partners[res['groupby']][key] = res
            elif key == 'initial_balance':
                if not company_currency.is_zero(res['balance']):
                    groupby_partners.setdefault(res['groupby'], {})
                    groupby_partners[res['groupby']][key] = res

        # Fetch the lines of unfolded accounts.
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])
        if expanded_partner or unfold_all or options['unfolded_lines']:
            query, params = self._get_query_amls(options, expanded_partner=expanded_partner)
            self._cr.execute(query, params)
            for res in self._cr.dictfetchall():
                if res['partner_id'] not in groupby_partners:
                    continue
                groupby_partners[res['partner_id']].setdefault('lines', [])
                groupby_partners[res['partner_id']]['lines'].append(res)

        # Retrieve the partners to browse.
        # groupby_partners.keys() contains all account ids affected by:
        # - the amls in the current period.
        # - the amls affecting the initial balance.
        # Note a search is done instead of a browse to preserve the table ordering.
        if expanded_partner:
            partners = expanded_partner
        elif groupby_partners:
            partners = self.env['res.partner'].with_context(active_test=False).search([('id', 'in', list(groupby_partners.keys()))])
        else:
            partners = []
        return [(partner, groupby_partners[partner.id]) for partner in partners]

    ####################################################
    # COLUMNS/LINES
    ####################################################

    @api.model
    def _get_report_line_partner(self, options, partner, initial_balance, debit, credit, balance):
        company_currency = self.env.company.currency_id
        unfold_all = self._context.get('print_mode') and not options.get('unfolded_lines')

        columns = [
            {'name': self.format_value(initial_balance), 'class': 'number'},
            {'name': self.format_value(debit), 'class': 'number'},
            {'name': self.format_value(credit), 'class': 'number'},
        ]
        if self.user_has_groups('base.group_multi_currency'):
            columns.append({'name': ''})
        columns.append({'name': self.format_value(balance), 'class': 'number'})

        return {
            'id': 'partner_%s' % partner.id,
            'name': partner.name[:128],
            'columns': columns,
            'level': 2,
            'trust': partner.trust,
            'unfoldable': not company_currency.is_zero(debit) or not company_currency.is_zero(credit),
            'unfolded': 'partner_%s' % partner.id in options['unfolded_lines'] or unfold_all,
            'colspan': 6,
        }

    @api.model
    def _get_report_line_move_line(self, options, partner, aml, cumulated_init_balance, cumulated_balance):
        if aml['payment_id']:
            caret_type = 'account.payment'
        elif aml['move_type'] in ('in_refund', 'in_invoice', 'in_receipt'):
            caret_type = 'account.invoice.in'
        elif aml['move_type'] in ('out_refund', 'out_invoice', 'out_receipt'):
            caret_type = 'account.invoice.out'
        else:
            caret_type = 'account.move'

        date_maturity = aml['date_maturity'] and format_date(self.env, fields.Date.from_string(aml['date_maturity']))
        columns = [
            {'name': aml['journal_code']},
            {'name': aml['account_code']},
            {'name': self._format_aml_name(aml['name'], aml['ref'], aml['move_name'])},
            {'name': date_maturity or '', 'class': 'date'},
            {'name': aml['full_rec_name'] or ''},
            {'name': self.format_value(cumulated_init_balance), 'class': 'number'},
            {'name': self.format_value(aml['debit'], blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value(aml['credit'], blank_if_zero=True), 'class': 'number'},
        ]
        if self.user_has_groups('base.group_multi_currency'):
            if aml['currency_id']:
                currency = self.env['res.currency'].browse(aml['currency_id'])
                formatted_amount = self.format_value(aml['amount_currency'], currency=currency, blank_if_zero=True)
                columns.append({'name': formatted_amount, 'class': 'number'})
            else:
                columns.append({'name': ''})
        columns.append({'name': self.format_value(cumulated_balance), 'class': 'number'})
        return {
            'id': aml['id'],
            'parent_id': 'partner_%s' % partner.id,
            'name': format_date(self.env, aml['date']),
            'class': 'date',
            'columns': columns,
            'caret_options': caret_type,
            'level': 4,
        }

    @api.model
    def _get_report_line_load_more(self, options, partner, offset, remaining, progress):
        return {
            'id': 'loadmore_%s' % partner.id,
            'offset': offset,
            'progress': progress,
            'remaining': remaining,
            'class': 'o_account_reports_load_more text-center',
            'parent_id': 'account_%s' % partner.id,
            'name': _('Load more... (%s remaining)' % remaining),
            'colspan': 10 if self.user_has_groups('base.group_multi_currency') else 9,
            'columns': [{}],
        }

    @api.model
    def _get_report_line_total(self, options, initial_balance, debit, credit, balance):
        columns = [
            {'name': self.format_value(initial_balance), 'class': 'number'},
            {'name': self.format_value(debit), 'class': 'number'},
            {'name': self.format_value(credit), 'class': 'number'},
        ]
        if self.user_has_groups('base.group_multi_currency'):
            columns.append({'name': ''})
        columns.append({'name': self.format_value(balance), 'class': 'number'})
        return {
            'id': 'partner_ledger_total_%s' % self.env.company.id,
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': columns,
            'colspan': 6,
        }

    @api.model
    def _get_partner_ledger_lines(self, options, line_id=None):
        ''' Get lines for the whole report or for a specific line.
        :param options: The report options.
        :return:        A list of lines, each one represented by a dictionary.
        '''
        lines = []
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        expanded_partner = line_id and self.env['res.partner'].browse(int(line_id[8:]))
        partners_results = self._do_query(options, expanded_partner=expanded_partner)

        total_initial_balance = total_debit = total_credit = total_balance = 0.0
        for partner, results in partners_results:
            is_unfolded = 'partner_%s' % partner.id in options['unfolded_lines']

            # res.partner record line.
            partner_sum = results.get('sum', {})
            partner_init_bal = results.get('initial_balance', {})

            initial_balance = partner_init_bal.get('balance', 0.0)
            debit = partner_sum.get('debit', 0.0)
            credit = partner_sum.get('credit', 0.0)
            balance = initial_balance + partner_sum.get('balance', 0.0)

            lines.append(self._get_report_line_partner(options, partner, initial_balance, debit, credit, balance))

            total_initial_balance += initial_balance
            total_debit += debit
            total_credit += credit
            total_balance += balance

            if unfold_all or is_unfolded:
                cumulated_balance = initial_balance

                # account.move.line record lines.
                amls = results.get('lines', [])

                load_more_remaining = len(amls)
                load_more_counter = self._context.get('print_mode') and load_more_remaining or self.MAX_LINES

                for aml in amls:
                    # Don't show more line than load_more_counter.
                    if load_more_counter == 0:
                        break

                    cumulated_init_balance = cumulated_balance
                    cumulated_balance += aml['balance']
                    lines.append(self._get_report_line_move_line(options, partner, aml, cumulated_init_balance, cumulated_balance))

                    load_more_remaining -= 1
                    load_more_counter -= 1

                if load_more_remaining > 0:
                    # Load more line.
                    lines.append(self._get_report_line_load_more(
                        options,
                        partner,
                        self.MAX_LINES,
                        load_more_remaining,
                        cumulated_balance,
                    ))

        if not line_id:
            # Report total line.
            lines.append(self._get_report_line_total(
                options,
                total_initial_balance,
                total_debit,
                total_credit,
                total_balance
            ))
        return lines

    @api.model
    def _load_more_lines(self, options, line_id, offset, load_more_remaining, progress):
        ''' Get lines for an expanded line using the load more.
        :param options: The report options.
        :return:        A list of lines, each one represented by a dictionary.
        '''
        lines = []

        expanded_partner = line_id and self.env['res.partner'].browse(int(line_id[9:]))

        load_more_counter = self.MAX_LINES

        # Fetch the next batch of lines.
        amls_query, amls_params = self._get_query_amls(options, expanded_partner=expanded_partner, offset=offset, limit=load_more_counter)
        self._cr.execute(amls_query, amls_params)
        for aml in self._cr.dictfetchall():
            # Don't show more line than load_more_counter.
            if load_more_counter == 0:
                break

            cumulated_init_balance = progress
            progress += aml['balance']

            # account.move.line record line.
            lines.append(self._get_report_line_move_line(options, expanded_partner, aml, cumulated_init_balance, progress))

            offset += 1
            load_more_remaining -= 1
            load_more_counter -= 1

        if load_more_remaining > 0:
            # Load more line.
            lines.append(self._get_report_line_load_more(
                options,
                expanded_partner,
                offset,
                load_more_remaining,
                progress,
            ))
        return lines

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('JRNL')},
            {'name': _('Account')},
            {'name': _('Ref')},
            {'name': _('Due Date'), 'class': 'date'},
            {'name': _('Matching Number')},
            {'name': _('Initial Balance'), 'class': 'number'},
            {'name': _('Debit'), 'class': 'number'},
            {'name': _('Credit'), 'class': 'number'}]

        if self.user_has_groups('base.group_multi_currency'):
            columns.append({'name': _('Amount Currency'), 'class': 'number'})

        columns.append({'name': _('Balance'), 'class': 'number'})

        return columns

    @api.model
    def _get_lines(self, options, line_id=None):
        offset = int(options.get('lines_offset', 0))
        remaining = int(options.get('lines_remaining', 0))
        balance_progress = float(options.get('lines_progress', 0))

        if offset > 0:
            # Case a line is expanded using the load more.
            return self._load_more_lines(options, line_id, offset, remaining, balance_progress)
        else:
            # Case the whole report is loaded or a line is expanded for the first time.
            return self._get_partner_ledger_lines(options, line_id=line_id)

    @api.model
    def _get_report_name(self):
        return _('Partner Ledger')
class AccountmoveAdvance(models.AbstractModel):
    _inherit ="account.move"

    advanced_payment=fields.Many2one('account.payment','Advanced Payment')

    def _compute_payments_widget_to_reconcile_info(self):
        super(AccountmoveAdvance, self)._compute_payments_widget_to_reconcile_info()
        for move in self:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

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

            # domain = ['|', ('account_id', 'in', pay_term_lines.mapped('account_id').ids), ('account_id', 'in', (
            # move.commercial_partner_id.advance_account_payable_id.id,
            # move.commercial_partner_id.advance_account_receivable_id.id)),
            #           '|', ('move_id.state', '=', 'posted'), '&', ('move_id.state', '=', 'draft'),
            #           # ('journal_id.post_at', '=', 'bank_rec'),
            #           ('partner_id', '=', move.commercial_partner_id.id), ('move_name', 'like', '/'),
            #           ('move_id.move_type', '!=', 'in_invoice'),
            #           ('reconciled', '=', False), '|', ('amount_residual', '!=', 0.0),
            #           ('amount_residual_currency', '!=', 0.0)]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):

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
                    'is_advance': line.account_id.advanced
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
        debit_value={}
        value = 0
        recoceled = False

        company = self.env.company
        if lines[0].account_id.advanced:
            if 'manual_payment_rate' in lines[0].payment_id.fields_get():
                if self.apply_manual_currency_exchange:
                    self = self.with_context(manual_rate=lines[0].payment_id.manual_payment_rate_hidden,
                                             active_manutal_currency=lines[0].payment_id.apply_manual_currency_exchange,
                                             )

            if  self.move_type=='in_invoice':
             account=lines[0].partner_id.property_account_payable_id.id
            if  self.move_type == 'out_invoice':
             account = lines[0].partner_id.property_account_receivable_id.id
            other=False


            if lines[0].currency_id and lines[0].currency_id != self.company_id.currency_id and self.currency_id != self.company_id.currency_id:
                other= True
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

                if abs(self.amount_residual) < abs(lines[0].amount_residual) :
                    value=self.amount_residual
                    amount = abs(lines[0].amount_residual) - (self.amount_residual)


                    for l in lines[0].move_id.line_ids:
                        if l.amount_residual_currency:
                            l.write({'amount_residual_currency': (abs(l.amount_residual) / l.amount_residual) * (
                                        l.amount_residual_currency * amount / abs(lines[0].amount_residual))})
                        if l.amount_residual!=0:
                            l.write({'amount_residual': (abs(l.amount_residual) / l.amount_residual) * amount})


                else:
                    value=lines[0].amount_residual
                    lines[0].write({'amount_residual':0})
                    if lines[0].amount_residual_currency:
                        lines[0].write({'amount_residual_currency': 0})

                    lines[0].write({'reconciled':True})


            if other:

                credit_value['amount_currency'] = -value
                credit_value['currency_id'] = self.currency_id.id
                credit_value['credit'] = self.currency_id._convert(abs(value), company.currency_id, company, self.date)
            else:
                credit_value['credit'] = abs(value)
            credit_value['move_id'] = False
            credit_value['id'] = False
            if self.move_type == 'in_invoice':

             credit_value['account_id'] = lines[0].account_id.id
            if self.move_type == 'out_invoice':
             credit_value['account_id'] = lines[0].partner_id.property_account_receivable_id.id

            credit_value['company_id']=lines[0].company_id.id
            credit_value['amount_residual'] = 0
            credit_value['currency_id'] =lines[0].currency_id.id
            credit_value['parent_state'] = 'posted'
            credit_value['partner_id'] = lines[0].partner_id.id
            credit_value['date'] =datetime.date(datetime.now())



            if other:
                debit_value['amount_currency'] = value
                debit_value['currency_id'] = self.currency_id.id
                debit_value['debit'] =self.currency_id._convert(abs(value), company.currency_id, company, self.date)
            else:
                debit_value['debit'] = abs(value)

            debit_value['move_id'] = False
            debit_value['id'] = False

            if self.move_type == 'out_invoice':
                debit_value['account_id'] = lines[0].account_id.id
            if self.move_type == 'in_invoice':
                debit_value['account_id'] = lines[0].partner_id.property_account_payable_id.id
            debit_value['company_id'] = lines[0].company_id.id
            debit_value['amount_residual'] = 0
            debit_value['currency_id'] = lines[0].currency_id.id
            debit_value['parent_state'] = 'posted'
            debit_value['partner_id'] =lines[0].partner_id.id
            debit_value['date'] = datetime.date(datetime.now())

            # for line in self.line_ids:
            #     new_line_ids.append((0,0,line))



            new_line_ids.append((0, 0, credit_value))
            new_line_ids.append((0, 0, debit_value))

            if 'report_credit' in lines[0].fields_get() and lines[0].move_id.report_currency_exchange_rate:
                cc = self.env['account.move'].create({

                    'move_type': 'entry',
                    'date': datetime.date(datetime.now()),
                    'journal_id': self.journal_id.id,
                    'company_id': self.company_id.id,
                    'line_ids': new_line_ids,
                    'report_currency_exchange_rate':lines[0].move_id.report_currency_exchange_rate
                }).id

            else:

                cc= self.env['account.move'].create({



                        'move_type': 'entry',
                        'date': datetime.date(datetime.now()),
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
class res_partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'


    def _compute_advanced_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])
        advance_domain = [('partner_id', 'in', all_partners.ids),
                  ('advance_ok', '=', True)]
        advanced_payment=self.env['account.payment'].search(advance_domain)

        supplier_advance_groups = self.env['account.payment'].read_group(
            domain=[('partner_id', 'in', all_partners.ids),
                  ('advance_ok', '=', True)],
            fields=['partner_id'], groupby=['partner_id']
        )
        partners = self.browse()
        for group in supplier_advance_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.supplier_advanced_count += group['partner_id_count']
                    partners |= partner
                partner = partner.parent_id
        (self - partners).supplier_advanced_count = 0


    supplier_advanced_count = fields.Integer(compute='_compute_advanced_count', string='# Advanced Payments')





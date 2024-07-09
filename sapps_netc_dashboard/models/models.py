# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.osv import expression
from odoo import api, fields, models, _, tools, _lt
import datetime


class SappsNetcDashboardAccountAccount(models.Model):
    _inherit = 'account.account'

    def get_base_currency(self):
        return 'Basic Currency is: ' + self.env.company.currency_id.symbol

    # ==================cash flow=====================
    def get_cash_ending_balance(self, fromDate=None, toDate=None):
        if not fromDate:
            fromDate = datetime.date(fields.Datetime.now().year, 1, 1)
        if not toDate:
            toDate = fields.Datetime.now()

        options = {
            'unfolded_lines': [],
            'date': {'mode': 'range', 'period_type': 'custom', 'date_from': fromDate,
                     'date_to': toDate, 'filter': 'custom'},
            'all_entries': False,
            'unfold_all': False,
            'unposted_in_period': True
        }

        payment_move_ids, payment_account_ids = self._get_liquidity_move_ids(options=options)
        currency_table_query = self._get_query_currency_table()
        beginning_period_options = self._get_options_beginning_period(options)
        begin_period_res = self._compute_liquidity_balance(beginning_period_options, currency_table_query,
                                                           payment_account_ids)
        period_res = self._compute_liquidity_balance(options, currency_table_query, payment_account_ids)
        result = []
        for item in period_res:
            try:
                account_journals = self.env['account.journal'].search([('inbound_payment_method_line_ids.payment_account_id', '=', item[0])
                                                                   ])
                types = set([item.type for item in account_journals])
                if len(types) != 1:
                    group_name = 'UNKNOWN'
                else:
                    group_name = types.pop()

                current_elem = next(elem for elem in result if elem["group_name"] == group_name)
            except StopIteration:
                result.append({'group_name': group_name, 'total': 0, 'total_currency': 0, 'items': []})
                current_elem = next(elem for elem in result if elem["group_name"] == group_name)
            if item[5] != self.env.company.currency_id.symbol and item[5]:
                current_elem['items'].append({'code': item[1],
                                              'name': item[2],
                                              'balance': item[3],
                                              'currecny': item[4],
                                              'init': 0,
                                              'init_currency': 0,
                                              'symbol': item[5],
                                              'id': item[0]})
            else:
                current_elem['items'].append({'code': item[1],
                                              'name': item[2],
                                              'balance': item[3],
                                              'currecny': 0,
                                              'init': 0,
                                              'init_currency': 0,
                                              'symbol': ' ',
                                              'id': item[0]})

            current_elem['total'] = current_elem['total'] + item[3]
            current_elem['init_total'] = 0
            current_elem['total_currency'] = current_elem['total_currency'] + item[4]
            current_elem['init_total_currency'] = 0
        intials_only = []
        for b in begin_period_res:
            account_journals = self.env['account.journal'].search([('inbound_payment_method_line_ids.payment_account_id', '=', b[0])
                                                                   ])
            types = set([item.type for item in account_journals])
            if len(types) != 1:
                group_name = 'UNKNOWN'
            else:
                group_name = types.pop()
            for e in result:
                try:
                    if e['group_name'] == group_name:
                        el = next(end for end in e['items'] if end['id'] == b[0])
                        el['balance'] = el['balance'] + b[3]
                        el['currecny'] = el['currecny'] + b[4]
                        el['init'] = b[3]
                        el['init_currency'] = b[4]
                        e['init_total'] = e['init_total'] + b[3]
                        e['init_total_currency'] = e['init_total_currency'] + b[4]
                except StopIteration:
                    intials_only.append({
                        'group': group_name,
                        'item':
                            {'code':b[1],
                             'name':b[2],
                             'balance': b[3],
                             'init': b[3],
                             'currecny': b[4],
                             'init_currency': b[4],
                             'symbol': b[5] if b[5] and b[5] != self.env.company.currency_id.symbol else ' ',
                             'id': b[0]}})
        for item in intials_only:
            result_group = next(e for e in result if item['group'] == e['group_name'])
            result_group['items'].append(item['item'])
            result_group['total'] = result_group['total'] + item['item']['balance']
            result_group['init_total'] = result_group['init_total'] + item['item']['balance']
            result_group['total_currency'] = result_group['total_currency'] + item['item']['currecny']
            result_group['init_total_currency'] = result_group['init_total_currency'] + item['item']['init_currency']
        for item in result:
            # if item['group_name'] == 'general':
            #     item['group_name'] = 'Miscellaneous'
            item['total'] = '{:20,.0f}'.format(item['total'])
            item['init_total'] = '{:20,.0f}'.format(item['init_total'])
            item['total_currency'] = '{:20,.0f}'.format(item['total_currency'])
            item['init_total_currency'] = '{:20,.0f}'.format(item['init_total_currency'])
            for elem in item['items']:
                elem['balance'] = '{:20,.0f}'.format(elem['balance'])
                elem['currecny'] = '{:20,.0f}'.format(elem['currecny'])
                elem['init'] = '{:20,.0f}'.format(elem['init'])
                elem['init_currency'] = '{:20,.0f}'.format(elem['init_currency'])

        return result

    @api.model
    def _get_query_currency_table(self):
        user_company = self.env.company
        user_currency = user_company.currency_id
        # if options.get('multi_company'):
        #     company_ids = [c['id'] for c in self._get_options_companies(options) if c['id'] != user_company.id and c['selected']]
        #     company_ids.append(self.env.company.id)
        #     companies = self.env['res.company'].browse(company_ids)
        #     conversion_date = options['date']['date_to']
        #     currency_rates = companies.mapped('currency_id')._get_rates(user_company, conversion_date)
        # else:
        companies = user_company
        currency_rates = {user_currency.id: 1.0}

        conversion_rates = []
        for company in companies:
            conversion_rates.append((
                company.id,
                currency_rates[user_company.currency_id.id] / currency_rates[company.currency_id.id],
                user_currency.decimal_places,
            ))

        currency_table = ','.join('(%s, %s, %s)' % args for args in conversion_rates)
        return '(VALUES %s) AS currency_table(company_id, rate, precision)' % currency_table

    @api.model
    def _get_options_journals(self, options):
        journals = []
        for journal_option in options.get('journals', []):
            if journal_option['id'] in ('divider', 'group'):
                continue
            if journal_option['selected']:
                journals.append(journal_option)
        return journals

    @api.model
    def _get_liquidity_move_ids(self, options):
        new_options = self._get_options_cash_current_period(options)
        payment_account_ids = set()
        self._cr.execute('''
                    SELECT aa.id
                    FROM account_account aa
                    join account_account_type aat on aa.user_type_id = aat.id
                    WHERE aat.name = 'Bank and Cash' '''
                         )
        for aId in self._cr.fetchall():
            payment_account_ids.add(aId)

        if not payment_account_ids:
            return (), ()

        # Fetch journal entries:
        # account.move having at least one line using a liquidity account.
        payment_move_ids = set()
        tables, where_clause, where_params = self._partner_query_get(new_options,
                                                                     [('account_id', 'in', list(payment_account_ids))])

        query = '''
                    SELECT DISTINCT account_move_line.move_id
                    FROM ''' + tables + '''
                    WHERE ''' + where_clause + '''
                    GROUP BY account_move_line.move_id
                '''
        self._cr.execute(query, where_params)
        for res in self._cr.fetchall():
            payment_move_ids.add(res[0])
        return tuple(payment_move_ids), tuple(payment_account_ids)

    @api.model
    def _get_options_current_period(self, options):
        ''' Create options with the 'strict_range' enabled on the filter_date / filter_comparison.
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options['date'] = {
            'mode': 'range',
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'strict_range': options['date']['date_from'] is not False,
        }
        new_options['journals'] = []
        return new_options

    @api.model
    def _get_options_beginning_period(self, options):
        ''' Create options with the 'strict_range' enabled on the filter_date.
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        date_tmp = fields.Date.from_string(options['date']['date_from']) - relativedelta(days=1)
        new_options['date'] = {
            'mode': 'single',
            'date_from': False,
            'date_to': fields.Date.to_string(date_tmp),
        }
        return new_options

    @api.model
    def _get_options_cash_current_period(self, options):
        ''' Create options with the 'strict_range' enabled on the filter_date / filter_comparison.
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options['date'] = {
            'mode': 'range',
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'strict_range': options['date']['date_from'] is not False,
        }
        new_options['journals'] = []
        return new_options

    @api.model
    def _compute_liquidity_balance(self, options, currency_table_query, payment_account_ids):
        new_options = self._get_options_cash_current_period(options)
        tables, where_clause, where_params = self._query_get(new_options,
                                                             domain=[('account_id', 'in', payment_account_ids)])
        query = '''
                    SELECT
                        account_move_line.account_id,
                        account.code AS account_code,
                        account.name AS account_name,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)),
                        SUM(ROUND(account_move_line.amount_currency, currency_table.precision)),
                        res_currency.symbol
                    FROM ''' + tables + '''
                    JOIN account_account account ON account.id = account_move_line.account_id
                    LEFT JOIN res_currency on res_currency.id = account.currency_id
                    LEFT JOIN ''' + currency_table_query + ''' ON currency_table.company_id = account_move_line.company_id
                    WHERE ''' + where_clause + '''
                    GROUP BY account_move_line.account_id, account.code, account.name, res_currency.symbol
                '''
        self._cr.execute(query, where_params)
        res = self._cr.fetchall()
        return res

    # ==================partner ledger=====================

    def get_partner_query_sums(self, fromDate=None, toDate=None, expanded_partner=None):
        if not fromDate:
            fromDate = datetime.date(fields.Datetime.now().year, 1, 1)
        if not toDate:
            toDate = fields.Datetime.now()
        params = []
        queries = []
        options = {
            'unfolded_lines': [],
            'date': {'mode': 'range', 'date_from': fromDate,
                     'date_to': toDate},
            'account_type': [
                {'id': 'receivable', 'name': _lt('Receivable'), 'selected': True},
                {'id': 'payable', 'name': _lt('Payable'), 'selected': True},
            ], 'all_entries': False, 'partner': True, 'partner_ids': [],
            'partner_categories': [],
            'selected_partner_ids': [],
            'selected_partner_categories': [],
            'unfold_all': False,
            'unreconciled': False,
            'unposted_in_period': True
        }

        if expanded_partner:
            domain = [('partner_id', '=', expanded_partner.id)]
        else:
            domain = []

        # Create the currency table.
        ct_query = self._get_query_currency_table()

        # Get sums for all partners.
        # period: [('date' <= options['date_to']), ('date' >= options['date_from'])]
        new_options = self._get_partner_options_sum_balance(options)
        tables, where_clause, where_params = self._partner_query_get(new_options, domain=domain)
        params += where_params
        queries.append('''
                SELECT
                    res_partner_category.name        AS groupby,
                    'sum'                               AS key,
                    SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                    SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                    SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                FROM %s
                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                JOIN res_partner_res_partner_category_rel on res_partner_res_partner_category_rel.partner_id = account_move_line.partner_id
                JOIN res_partner_category on res_partner_category.id = res_partner_res_partner_category_rel.category_id
                WHERE %s
                GROUP BY  res_partner_category.name
            ''' % (tables, ct_query, where_clause))

        # Get sums for the initial balance.
        # period: [('date' <= options['date_from'] - 1)]
        new_options = self.env['account.partner.ledger']._get_options_initial_balance(options)
        tables, where_clause, where_params = self._partner_query_get(new_options, domain=domain)
        params += where_params
        queries.append('''
                SELECT
                    res_partner_category.name        AS groupby,
                    'initial_balance'                   AS key,
                    SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                    SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                    SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                FROM %s
                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                JOIN res_partner_res_partner_category_rel on res_partner_res_partner_category_rel.partner_id = account_move_line.partner_id
                JOIN res_partner_category on res_partner_category.id = res_partner_res_partner_category_rel.category_id
                WHERE %s
                GROUP BY res_partner_category.name
            ''' % (tables, ct_query, where_clause))

        self._cr.execute(' UNION ALL '.join(queries), params)
        res = self._cr.fetchall()
        result = []
        for item in res:
            init_b = [i for i in res if i[1] == 'initial_balance' and i[0] == item[0]]
            if len(init_b) > 0:
                init_b = init_b[0]
            if init_b and init_b[2] > 0 and item[1] == 'sum':
                result.append({'name': item[0], 'initial_balance': '{:20,.0f}'.format(init_b[4]),
                               'sum': '{:20,.0f}'.format(item[4] + init_b[4])})
            elif item[1] == 'sum':
                result.append({'name': item[0], 'initial_balance': 0,
                               'sum': '{:20,.0f}'.format(item[4])})
        tmp = [el['name'] for el in result]
        init_balance_without_sum = [i for i in res if i[1] == 'initial_balance' if i[0] not in tmp]
        for item in init_balance_without_sum:
            result.append({'name': item[0], 'initial_balance': '{:20,.0f}'.format(item[4]),
                           'sum': '{:20,.0f}'.format(item[4])})

        return result

    @api.model
    def _get_partner_options_sum_balance(self, options):
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
    def _query_get(self, options, domain=None):
        domain = self.env['account.report']._get_options_domain(options) + (domain or [])
        self.env['account.move.line'].check_access_rights('read')

        query = self.env['account.move.line']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        self.env['account.move.line']._apply_ir_rules(query)

        return query.get_sql()

    @api.model
    def _partner_query_get(self, options, domain=None):
        domain = self.env['account.partner.ledger']._get_options_domain(options) + (domain or [])
        self.env['account.move.line'].check_access_rights('read')

        query = self.env['account.move.line']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        self.env['account.move.line']._apply_ir_rules(query)

        return query.get_sql()

    # =============== production report =======================
    def get_finished_product_report(self, fromDate=None, toDate=None):
        if not fromDate:
            fromDate = datetime.date(fields.Datetime.now().year, 1, 1)
        if not toDate:
            toDate = fields.Datetime.now()

        query = """
                SELECT 
                product_template."name",product_product.id, sum(stock_move_line.qty_done) 
                FROM PUBLIC.mrp_production
				join public.stock_move on mrp_production.id = stock_move.production_id
				join public.stock_move_line on stock_move.id = stock_move_line.move_id
				join public.mrp_bom on mrp_bom.id = mrp_production.bom_id
				join public.product_product on mrp_production.product_id = product_product.id
				join public.product_template on product_template.id = product_product.product_tmpl_id
				where 1=1
				and stock_move.state = 'done'
 				and stock_move_line.cost_date between '%s' and '%s'
                group by product_template."name", product_product.id
        """ % (fromDate, toDate)

        finished_products = self.env['mrp.bom'].search([
                                                        ('active', '=', True)
                                                        ]).product_tmpl_id.product_variant_ids

        locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        inits = []
        for p in finished_products:
            item = {'product': p.display_name,
                    'id': p.id
                    }

            dest_quant = sum(des_m.quantity_done for des_m in
                             self.env['stock.move'].search([('product_id', '=', p.id),
                                                            ('location_dest_id', 'in', locations.ids),
                                                            ('state', '=', 'done'),
                                                            ('date', '<', fromDate)
                                                            ])
                             )
            source_quant = sum(sour_m.quantity_done for sour_m in
                               self.env['stock.move'].search([('product_id', '=', p.id),
                                                              ('location_id', 'in', locations.ids),
                                                              ('state', '=', 'done'),
                                                              ('date', '<', fromDate)
                                                              ])
                               )
            item['quant'] = dest_quant - source_quant
            if item['quant'] > 0:
                inits.append(item)

        self._cr.execute(query)
        res = self._cr.fetchall()

        result = []
        for f in finished_products:

            if f.id not in [i[1] for i in res]:
                elem = [f.display_name, f.id, 0]
            else:
                production = [i[2] for i in res if i[1] == f.id][0]
                elem = [f.display_name, f.id, production]

            try:
                initial_value = next(init for init in inits if init['id'] == elem[1])['quant']
            except StopIteration:
                initial_value = 0
            elem.append(initial_value)
            result.append(elem)
        result.append(['Total', 0, sum(c[2] for c in result), sum(c[3] for c in result)])

        return result

    def get_onhand_quantity_group_by_location(self, filterDate=fields.Datetime.now()):
        if not filterDate:
            filterDate = fields.Datetime.now()
        internal_location = self.env['stock.location'].search([('usage', '=', 'internal'),
                                                               ('sapps_finished_location', '=', True)
                                                               ])

        inventory_ajust_loc = self.env['stock.location'].search([('name', 'like', 'Inventory adjustment')]).id
        finished_products = self.env['mrp.bom'].search([
                                                        ('active', '=', True)
                                                        ]).product_tmpl_id.product_variant_ids
        res = []
        for p in finished_products:
            item = {'product': p.display_name,
                    'product_id': p.product_tmpl_id.id
                    }
            location_quants = []

            internal_location_extended = self.env['stock.location'].search([('usage', '=', 'internal')])
            locs = internal_location_extended.mapped("id")
            stock_out = self.env['stock.move.line'].search([('product_id', '=', p.id),
                                                            ('location_dest_id', 'not in', locs),
                                                            ('location_id', 'in', locs),
                                                            ('state', '=', 'done'),
                                                            ('date', '<=', filterDate)
                                                            ])
            stock_in = self.env['stock.move.line'].search([('product_id', '=', p.id),
                                                           ('location_dest_id', 'in', locs),
                                                           ('location_id', 'not in', locs),
                                                           ('state', '=', 'done'),
                                                           ('date', '<=', filterDate)
                                                           ])
            df = [i for i in stock_in.lot_id.ids if i not in stock_out.lot_id.ids]
            item['production_lot'] = df

            for loc in internal_location:
                dest_quant = sum(des_m.quantity_done for des_m in
                                 self.env['stock.move'].search([('product_id', '=', p.id),
                                                                ('location_dest_id', '=', loc.id),
                                                                ('state', '=', 'done'),
                                                                ('date', '<=', filterDate)
                                                                ])
                                 )
                source_quant = sum(sour_m.quantity_done for sour_m in
                                   self.env['stock.move'].search([('product_id', '=', p.id),
                                                                  ('location_id', '=', loc.id),
                                                                  ('state', '=', 'done'),
                                                                  ('date', '<=', filterDate)
                                                                  ])
                                   )

                location_quants.append({'name': loc.name,
                                        'quant': dest_quant - source_quant,
                                        'is_finish': loc.sapps_finished_location
                                        })

            item['location_quants'] = location_quants
            res.append(item)
        tot = {'product': 'Total', 'location_quants': [a.copy() for a in location_quants]}
        expanded_locations = sum([c['location_quants'] for c in res], [])
        for loc in tot['location_quants']:
            loc['quant'] = sum([x['quant'] for x in expanded_locations if x['name'] == loc['name']])
        res.append(tot)
        a = {'result': res, 'products': [p.display_name for p in finished_products],
                'locations': [[l.name, l.sapps_finished_location] for l in internal_location]}
        return a

    def get_query_sold_quantity_price_cogs(self, fromDate=None, toDate=None):
        if not fromDate:
            fromDate = datetime.date(fields.Datetime.now().year, 1, 1)
        if not toDate:
            toDate = fields.Datetime.now()
        finished_products = self.env['mrp.bom'].search([
                                                        ('active', '=', True)
                                                        ]).product_tmpl_id.product_variant_ids

        res = []
        for p in finished_products:
            item = {'product': p.display_name}
            domain_move_out = [('state', '=', 'done'),
                               ('product_id', '=', p.id),
                               ('move_id.picking_id', '!=', False),
                               ('move_id.picking_id.sale_id', '!=', False),
                               ('move_id.picking_id.date', '>=', fromDate),
                               ('move_id.picking_id.date', '<=', toDate)
                               ]
            moves = self.env['stock.move.line'].search(domain_move_out)
            out_lots = moves.lot_id.ids
            out_qty = 0
            for move in moves:
                quantity = move.qty_done
                out_qty = out_qty + quantity
            parent_move_ids = [i.move_id for i in moves]
            return_lots = moves.move_id.returned_move_ids.move_line_ids.lot_id.ids
            for parent_move in parent_move_ids:
                out_qty = out_qty - (sum(m.quantity_done for m in parent_move.returned_move_ids)*2)

            sold_lots = [i for i in out_lots if i not in return_lots]
            item['sold_quantity'] = out_qty
            item['sold_lots'] = sold_lots

            categ_ids = self.env['mrp.bom'].search([('active', '=', True)
                                                    ]).product_tmpl_id.product_variant_ids.categ_id
            expense_accounts = [item.property_account_expense_categ_id.id for item in categ_ids]
            income_accounts = [item.property_account_income_categ_id.id for item in categ_ids]

            if len(expense_accounts) > 1:
                query = """
                    SELECT SUM(BALANCE) FROM ACCOUNT_MOVE_LINE
                    WHERE ACCOUNT_ID IN %%s
                    AND DATE >= '%%s'
                    AND DATE <= '%%s'
                    AND product_id = %%s
                """
                self._cr.execute(query, (tuple(expense_accounts), fromDate, toDate, p.id,))
            else:
                expId = expense_accounts[0]
                query = """
                                    SELECT SUM(BALANCE) FROM ACCOUNT_MOVE_LINE
                                    WHERE ACCOUNT_ID = """ + str(expId) + """
                                    AND DATE >= %s
                                    AND DATE <= %s
                                    AND product_id = %s
                                """
                self._cr.execute(query, (fromDate, toDate, p.id))
            expense_res = self._cr.fetchall()
            c_res = False
            if len(income_accounts) > 1:
                query = """
                                SELECT SUM(BALANCE) FROM ACCOUNT_MOVE_LINE
                                WHERE ACCOUNT_ID IN %s 
                                AND DATE >= '%s'
                                AND DATE <= '%s'
                                AND product_id = %s
                            """ % (tuple(income_accounts), fromDate, toDate, p.id)

                self._cr.execute(query)
            else:
                query = """
                            SELECT SUM(BALANCE) FROM ACCOUNT_MOVE_LINE
                            WHERE ACCOUNT_ID = %s 
                            AND DATE >= '%s'
                            AND DATE <= '%s'
                            AND product_id = %s
                        """ % (income_accounts[0], fromDate, toDate, p.id)

                self._cr.execute(query)
            income_res = self._cr.fetchall()

            income = income_res[0][0]
            if c_res and c_res[0][0] is not None:
                correct = c_res[0][0]
            else:
                correct = 0
            if expense_res and expense_res[0][0] is not None:
                expense_result = expense_res[0][0]
            else:
                expense_result = 0

            expense = expense_result + correct
            if not income:
                income = 0
            if not expense:
                expense = 0
            item['total_invoiced'] = '{:20,.0f}'.format(income)
            item['cogs'] = '{:20,.0f}'.format(expense)

            res.append(item)

        res.append({'product': 'Total', 'sold_quantity': sum([x['sold_quantity'] for x in res]),
                    'total_invoiced': '{:20,.0f}'.format(sum([int(x['total_invoiced'].replace(',', '')) for x in res])),
                    'cogs': '{:20,.0f}'.format(sum([int(x['cogs'].replace(',', '')) for x in res]))})

        return {'res': res, 'total_sold': 0, 'total_cogs': 0, 'total_invoiced': 0}

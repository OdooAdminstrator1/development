# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ast import literal_eval
import calendar
from odoo.tools import float_is_zero
import datetime
from dateutil.relativedelta import relativedelta
from babel.dates import format_date
from odoo.tools import float_round

# end_date must be lowest that run date first issue, the procedure will not recognize any bill entered after running
# procedure and have accounting date previous to end_date
# If the accountant know that there's a bill will be become, then he must treat it by inserting accrual one


class OverheadProcedureLog(models.Model):
    _name = 'ict_overhead_expenses.procedure.log'
    _description = 'Running log for procedure'

    run_date = fields.Datetime(string='Run Time', required=True,  default=fields.datetime.now())
    start_date = fields.Date(string='Start Date', tracking=True, index=True, store=True, readonly=1)
    end_date = fields.Date(string='End Date', tracking=True, index=True, store=True, readonly=1)
    previous_processed_balance = fields.Float("Previous Processed Balance", help="Unprocessed balance migrated from previous period",
                                              default=0)
    processed_balance = fields.Float('Computed Processed Balance',
                                     help='this field represent the actual balance of Stock IN/OUT' +
                                          ' = current balance minus (all done MO overhead' +
                                          ' after end date with actual bill', default=0)
    actual_processed_balance = fields.Float("Actual Processed Balance",
                                            help="Actual processed balance in this period. max = copmuted processed balance + previous processed balance",
                                            default=0)
    processed_balance_to_next_period = fields.Float(string="Amount to migrate to next period")
    processed_balance_to_expense_account = fields.Float(string="Amount to post on expense account")
    processed_balance_expense_account = fields.Many2one('account.account',
                                                        string='Expense Account',
                                                        digits=(12, 2),
                                                        domain=[('user_type_id.internal_group', '=', 'expense')])

    state = fields.Selection(selection=[
            ('draft_with_issue', 'Draft With Issue'),
            ('draft', 'Draft'),
            ('done', 'done'),
            ('cancel', 'Cancelled')
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft'
    )
    done_move_ids = fields.One2many('stock.move', 'ict_proc_id', string='Done Moves')
    product_costs = fields.One2many('ict_overhead_expenses.product.cost', 'proc_id' ,string='Costs of Products')
    sold_products = fields.One2many('ict_overhead_expenses.sold.items', 'proc_id' ,string='Sold Products')
    generated_GVs = fields.One2many('ict_overhead_expenses.gv.account.move.line', 'proc_id' ,string='Sold Items GVs')
    moves_count = fields.Integer('Move Counts', compute='_compute_counts')
    product_costs_count = fields.Integer('Product Cost Counts', compute='_compute_counts')
    # replica of settings
    ict_cogs_journal = fields.Many2one('account.journal', 'COGS journal type')
    ict_rest_account_id = fields.Many2one('account.account', 'Rest Account')
    ict_analytic_account = fields.Many2one('account.analytic.account', 'Analytic Account')
    actual_cost = fields.Float(string='Actual Cost')
    standard_cost = fields.Float(string='Standard Cost')

    def preview_uncosted_journals(self):
        res = self.env['ict_overhead.uncosted_journals'].create({'start_date': self.start_date,
                                                                 'end_date': self.end_date,
                                                                 'res_account_id': int(self.ict_rest_account_id.id)
                                                                 })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ict_overhead.uncosted_journals',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': self.env.ref(
                'ict_overhead_expenses.ict_overhead_expenses_uncosted_journal_confirmation').id,
            'res_id': res.id,
            'target': 'new',
        }

    # @api.onchange('actual_processed_balance')
    # def _onchange_actual_processed_balance(self):
    #     # if self.actual_processed_balance != self.processed_balance + self.previous_processed_balance:
    #
    @api.onchange('actual_processed_balance', 'processed_balance_to_next_period')
    def _onchange_actual_processed_balance(self):
        self.processed_balance_to_expense_account = ((self.processed_balance + self.previous_processed_balance) - self.actual_processed_balance) - self.processed_balance_to_next_period

    @api.constrains('processed_balance_to_next_period', 'actual_processed_balance', 'processed_balance_expense_account')
    def _check_actual_processing_balance(self):
        if self.processed_balance_to_next_period == 0 and self.processed_balance_to_expense_account == 0:
            if float_round(self.actual_processed_balance,self.env.company.currency_id.rounding) != float_round(self.previous_processed_balance + self.processed_balance,self.env.company.currency_id.rounding):
                raise UserError(_("Actual Processed balance should equal to (previous + computed) processed balance"))
        else:
            if float_round(self.processed_balance_to_next_period +
                 self.processed_balance_to_expense_account, self.env.company.currency_id.rounding) \
                    != float_round((self.processed_balance + self.previous_processed_balance) - self.actual_processed_balance, self.env.company.currency_id.rounding):
                raise UserError('Actual Processed Balance should equal to next period amount + expense amount')

        finsihed_mo_in_finshing_routing = self._get_done_manufactured()
        self._compute_product_costs(finsihed_mo_in_finshing_routing)
        # check if there is sold products from manufactured products in the specified period and return them
        self._prepare_sold_items(finsihed_mo_in_finshing_routing)
        self._prepare_change_price_jvs()
        # prepare Journal Vouchers
        self._prepare_demo_gvs()

    def process_anyway_confirmed(self):
        res = self
        # get moves
        done_moves_res = []
        finsihed_mo_in_finshing_routing = res._get_done_manufactured()
        # loop and get finished moves
        for mo in finsihed_mo_in_finshing_routing:
            for elem in mo.move_finished_ids.filtered(lambda v: v.state == 'done'):
                done_moves_res.append(elem)

        res.done_move_ids = [(4, item.id) for item in done_moves_res]

        # compute processed balance = standard overhead - actual cost
        res._compute_processed_balance(finsihed_mo_in_finshing_routing)
        # compute the processed balance'percentage which will be applied on each product
        res._compute_product_costs(finsihed_mo_in_finshing_routing)
        # check if there is sold products from manufactured products in the specified period and return them
        res._prepare_sold_items(finsihed_mo_in_finshing_routing)
        res._prepare_change_price_jvs()
        # prepare Journal Vouchers
        res._prepare_demo_gvs()
        res.state = 'draft'

    #old
    def get_date_range(self):
        period_setting = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_period')
        last_run = self.env['ict_overhead_expenses.procedure.log'].search([('state', '!=', 'cancel')],
                                                                          order='end_date desc', limit=1)
        if last_run:
            d = self.add_months(last_run.end_date, 1)
            start_date = datetime.date(d.year, d.month, 1)
        else:
            start_date = fields.Date.from_string(
                self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_initial_start_date')
            )
        all_opend_period = self.env['ict_overhead_expenses.period'].search(
            [('date_start', '=', start_date), ('state', '=', 'open')])
        opend_period = all_opend_period[0]

        end_date = opend_period.date_stop

        return start_date, end_date

    def _compute_counts(self):
        for rec in self:
            rec.moves_count = self.env['stock.move'].search_count([('ict_proc_id', '=', rec.id)])
            rec.product_costs_count = self.env['ict_overhead_expenses.product.cost'].search_count([('proc_id', '=', rec.id)])

    def write(self, vals):
        super(OverheadProcedureLog, self).write(vals)
        if not float_is_zero(self.processed_balance_to_expense_account, precision_rounding=self.env.company.currency_id.rounding):
            if not self.processed_balance_expense_account:
                raise UserError("Expense Account Required")
            self.generated_GVs.filtered(lambda p: p.type == 'CARRIED_BY_EXPENSE').unlink()
            plus_minus = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id'))
            credit_account_id = plus_minus if self.processed_balance_to_expense_account > 0 else self.processed_balance_expense_account.id
            debit_account_id = plus_minus if self.processed_balance_to_expense_account < 0 else self.processed_balance_expense_account.id
            super(OverheadProcedureLog, self).write({'generated_GVs': [(0, 0, {
                    'ref': _('overhead carried by expense account') ,
                    'account_id': debit_account_id,
                    'debit': abs(self.processed_balance_to_expense_account),
                    'credit': 0,
                    'date': self.end_date,
                    'type': 'CARRIED_BY_EXPENSE'
                }),
                                  (0, 0, {
                    'ref': _('overhead carried by expense account'),
                    'account_id': credit_account_id,
                    'debit': 0,
                    'credit': abs(self.processed_balance_to_expense_account),
                    'date': self.end_date,
                    'type': 'CARRIED_BY_EXPENSE'
                })
          ]})


    @api.model
    def create(self, vals_list):
        # replicate settings
        self = self.sudo()

        draft_count = self.env['ict_overhead_expenses.procedure.log'].search_count([('state', 'in', ['draft','draft_with_issue'])])
        if draft_count > 0:
            raise UserError('please close all opened period')

        res = self.env['mrp.production'].search([('bom_id.finishing_product_ok', '=', True),
                                                 ])
        unallocated_done_mo = []
        for item in res:
            done_moves = item.move_finished_ids.filtered(
                lambda x: x.state == 'done' and x.product_id.id == item.product_id.id)
            qty_produced = sum(done_moves.mapped('quantity_done'))
            if qty_produced > 0:
                if len(item.finished_move_line_ids.filtered(lambda d: d.state == 'done' and not d.cost_date)) > 0:
                    unallocated_done_mo.append(item)

        if len(unallocated_done_mo) > 0:
            raise UserError('please add costing date to all done MO''s')
        landed_cost_product = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_standard_cost_product_ids')
        vals_list['ict_rest_account_id'] = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id')
        vals_list['ict_analytic_account'] = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_account')
        vals_list['run_date'] = fields.Date.today()
        vals_list['start_date'], vals_list['end_date'] = self.get_date_range()
        # check if there's res account debited but it is not a costing jv
        count = self.env['account.move.line'].search_count([('company_id', '=', self.env.company.id),
                                                            ('move_id.state', '!=', 'cancel'),
                                                            ('move_id.move_type', '=', 'entry'),
                                                            ('account_id', '=', int(vals_list['ict_rest_account_id'])),
                                                            ('debit', '>', 0),
                                                            ('is_costing_jv', '=', False),
                                                            ('created_by_user', '=', True),
                                                            ])
        res = super(OverheadProcedureLog, self).create(vals_list)
        if count > 0 :
            res.state = 'draft_with_issue'
        else:
            res.process_anyway_confirmed()
        return res

    def _prepare_change_price_jvs(self):
        res = []
        for item in self.product_costs:
            counterpart_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_rest_account_id'))
            # manufactured_product = self.env['product.product'].search([('id', '=', item['manufactured_product'])])
            product_tot_qty_available = item.manufactured_product.with_context(force_company=self.env.company.id).quantity_svl
            amount_unit = item.manufactured_product.with_context(force_company=self.env.company.id).standard_price

            if self.sold_products:
                if item.manufactured_product.categ_id.property_cost_method == 'average':
                    sold_product_count = self.sold_products.filtered(lambda v: v.product_id.id == item.manufactured_product.id)
                if item.manufactured_product.categ_id.property_cost_method == 'fifo':
                    sold_product_count = self.sold_products.filtered(lambda v: v.manufacturing_order.id == item.mo_id.id)
                if sold_product_count:
                    sold_count = sold_product_count.processed_count
                else:
                    sold_count = 0
            else:
                sold_count = 0
            if product_tot_qty_available != 0:
                if item.manufactured_product.categ_id.property_cost_method == 'average':
                    if sold_count > 0:
                        pdu = abs(item.cost/(sold_product_count.previous_initial_stock + item.qty_produced))
                        # if abs(sold_product_count.processed_count*pdu) > abs(item.cost):
                        #     raise UserError(_('CoGS amount (%s) is greater than the total difference (%s) for %s')%(sold_product_count.processed_count*pdu,item.cost, item.manufactured_product.name))
                        # else:
                        if item.cost > 0:
                            current_stock_percentage = item.cost - pdu*sold_count
                        else:
                            current_stock_percentage = -1*(abs(item.cost) - abs(pdu*sold_count))

                    else:
                        current_stock_percentage = item.cost
                    new_std_price = ((amount_unit * (product_tot_qty_available)) + current_stock_percentage) / (
                        (product_tot_qty_available))
                    self.create_demo_jvs_for_changing_price(item.manufactured_product,
                                                            new_std_price,
                                                            counterpart_account_id=counterpart_account_id)
                    item.new_std_price = new_std_price
                    item.costing_method = 'AVCO'
                if item.manufactured_product.categ_id.property_cost_method == 'fifo':
                    additional_cost = item.cost - (item.cost / item.qty_produced) * sold_count
                    self.create_demo_jvs_for_fifo(item.manufactured_product, additional_cost,
                                                  counterpart_account_id, item.mo_id.id)
                    item.new_std_price = item.manufactured_product.standard_price
                    item.costing_method = 'FIFO'
                if item.manufactured_product.categ_id.property_cost_method not in ['fifo', 'average']:
                    raise UserError('you have been set a productivity date to manufactured '
                                    'product with standard costing method')
        return

    def create_demo_jvs_for_fifo(self, product, additional_cost, counterpart_account_id, mo_id):
        product_accounts = {product.id: product.product_tmpl_id.get_product_accounts()}
        if additional_cost < 0:
            debit_account_id = counterpart_account_id
            credit_account_id = product_accounts[product.id]['stock_valuation'].id
        else:
            debit_account_id = product_accounts[product.id]['stock_valuation'].id
            credit_account_id = counterpart_account_id

        self.generated_GVs += self.generated_GVs.new(
            {
                'ref': _('addition cost %s added to %s by %s') % (
                    additional_cost, product.display_name, self.env.user.name),
                'account_id': debit_account_id,
                'debit': abs(additional_cost),
                'credit': 0,
                'date': self.end_date,
                'type': 'CHANGE_PRICE',
                'product_id': product.id,
                'mo_id': mo_id
            }
        )
        self.generated_GVs += self.generated_GVs.new(
            {
                'ref': _('addition cost (%s) added to %s by %s') % (
                    additional_cost, product.display_name, self.env.user.name),
                'account_id': credit_account_id,
                'debit': 0,
                'credit': abs(additional_cost),
                'date': self.end_date,
                'type': 'CHANGE_PRICE',
                'product_id': product.id,
                'mo_id': mo_id
            }
        )

        return

    def create_demo_jvs_for_changing_price(self, product, new_price, counterpart_account_id):
        company_id = self.env.company
        if product.cost_method not in ('standard', 'average'):
            return []
        quantity_svl = product.sudo().quantity_svl
        if float_is_zero(quantity_svl, precision_rounding=product.uom_id.rounding):
            return []
        diff = new_price - product.standard_price
        value = company_id.currency_id.round(quantity_svl * diff)
        if company_id.currency_id.is_zero(value):
            return []

        # Handle account moves.
        product_accounts = {product.id: product.product_tmpl_id.get_product_accounts()}

        value = value
        if product.valuation != 'real_time':
            return []
        if counterpart_account_id is False:
            raise UserError(_('You must set a counterpart account.'))
        if not product_accounts[product.id].get('stock_valuation'):
            raise UserError(_(
                'You don\'t have any stock valuation account defined on your product category. '
                'You must define one before processing this operation.'))

        if value < 0:
            debit_account_id = counterpart_account_id
            credit_account_id = product_accounts[product.id]['stock_valuation'].id
        else:
            debit_account_id = product_accounts[product.id]['stock_valuation'].id
            credit_account_id = counterpart_account_id

        self.generated_GVs += self.generated_GVs.new(
            {
                'ref': _('%s changed cost from %s to %s - %s') % (
                    self.env.user.name, product.standard_price, new_price, product.display_name),
                'account_id': debit_account_id,
                'debit': abs(value),
                'credit': 0,
                'date': self.end_date,
                'type': 'CHANGE_PRICE',
                'product_id': product.id,
                'mo_id': False
            }
        )
        self.generated_GVs += self.generated_GVs.new(
            {
                'ref': _('%s changed cost from %s to %s - %s') % (
                    self.env.user.name, product.standard_price, new_price, product.display_name),
                'account_id': credit_account_id,
                'debit': 0,
                'credit': abs(value),
                'date': self.end_date,
                'type': 'CHANGE_PRICE',
                'product_id': product.id,
                'mo_id': False
            }
        )
        return

    def _get_done_manufactured(self):
        finsihed_mo_in_finshing_routing = self.env['mrp.production']. search([
            ('move_finished_ids.move_line_ids.cost_date', '>=', self.start_date),
            ('move_finished_ids.move_line_ids.cost_date', '<=', self.end_date),
            ('bom_id.finishing_product_ok', '=', True)
        ])
        actual_finish = []
        for item in finsihed_mo_in_finshing_routing:
            done_moves = item.move_finished_ids.filtered(
                lambda x: x.state == 'done' and x.product_id.id == item.product_id.id)
            qty_produced = sum(done_moves.mapped('quantity_done'))
            if qty_produced > 0:
                actual_finish.append(item)
        for item in actual_finish:
            # for line in item.finished_move_line_ids.filtered(lambda v: self.start_date <= v.cost_date <= self.end_date):
            #     line.ict_is_processed_line = True
            if item.bom_id.finishing_product_ok and len(item.finished_move_line_ids.filtered(lambda i: i.state == 'done' and i.cost_date is False)) > 0:
                raise UserError('there is Manufacturing orders in this period '
                                'that have no costing date, please fill it before')
        return actual_finish

    def _prepare_sold_items(self, manufactured_orders):
        # get sold product in the run period
        customer_location_ids = self.env['stock.location'].search([('usage', '=', 'customer')]).ids

        res = []
        self.sold_products = False
        self.generated_GVs = False
        for m_order in manufactured_orders:
            if m_order.product_id.categ_id.property_cost_method == 'average':
                domain_move_out = [('state', '=', 'done'),
                                   ('product_id', 'in', m_order.product_id.ids),
                                   ('move_id.picking_id', '!=', False),
                                   ('move_id.picking_id.sale_id', '!=', False),
                                   ('move_id.picking_id.ict_sales_costing_date', '>=', self.start_date),
                                   ('move_id.picking_id.ict_sales_costing_date', '<=', self.end_date)
                                  ]
                moves = self.env['stock.move.line'].search(domain_move_out)
                out_qty = 0
                for move in moves:
                    quantity = move.product_uom_id._compute_quantity(move.qty_done, move.product_id.uom_id)
                    out_qty = out_qty + quantity
                parent_move_ids = [i.move_id for i in moves]
                for parent_move in parent_move_ids:
                    out_qty = out_qty - sum(m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)*2
                                            if (m.picking_id and m.picking_id.ict_sales_costing_date)
                                            else m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)
                                            for m in parent_move.returned_move_ids)
                if out_qty > 0:
                    # check if exists
                    item = self.sold_products.filtered(lambda i: i.product_id.id == m_order.product_id.id)
                    if item:
                        continue
                    else:
                        self.sold_products += self.sold_products.new({'manufacturing_order': False,
                                                                      'product_id': move.product_id,
                                                                      'actual_count': out_qty,
                                                                      'sold_move_line_ids': [(4, m.id) for m in moves]
                                                                      })

            if m_order.product_id.categ_id.property_cost_method == 'fifo':
                svl = self.env['stock.valuation.layer'].search([('stock_move_id', '=', m_order.move_finished_ids.id)], limit=1)

                costed_qty_in_period = sum(e.qty_done for e in m_order.finished_move_line_ids.
                               filtered(lambda s: s.cost_date != False and s.cost_date >= self.start_date
                                                  and s.cost_date <= self.end_date))
                sold_qty = svl.quantity - svl.remaining_qty - svl.ict_overhead_processed_quantity
                if sold_qty < 0:
                    quantity = costed_qty_in_period
                else:
                    quantity = sold_qty

                if quantity > 0:
                    self.sold_products += self.sold_products.new({'manufacturing_order': m_order,
                                                                  'product_id': m_order.product_id,
                                                                  'actual_count': quantity
                                                                  })
                else:
                    self.sold_products += self.sold_products.new({'manufacturing_order': False,
                                                                  'product_id': m_order.product_id,
                                                                  'actual_count': 0
                                                                  })
        # add all finished products which are not manufactured in this period to store initial stock only
        if self.sold_products:
            self._cr.execute('''
                        SELECT
                            DISTINCT (product_tmpl_id)
                        FROM mrp_bom bm
                        where finishing_product_ok = TRUE
                        and product_tmpl_id not in %s
                    ''', [tuple(self.sold_products.product_id.product_tmpl_id.ids)])

        else:
            self._cr.execute('''
                            SELECT
                                DISTINCT (product_tmpl_id)
                            FROM mrp_bom bm
                            where finishing_product_ok = TRUE
                            ''')

        query_res = self._cr.dictfetchall()
        for rest_product in query_res:
            p_id = self.env['product.product'].search(
                [('product_tmpl_id', '=', rest_product['product_tmpl_id'])]).id

            domain_move_out = [('state', '=', 'done'),
                               ('product_id', '=', p_id),
                               ('move_id.picking_id', '!=', False),
                               ('move_id.picking_id.sale_id', '!=', False),
                               ('move_id.picking_id.ict_sales_costing_date', '>=', self.start_date),
                               ('move_id.picking_id.ict_sales_costing_date', '<=', self.end_date)
                               ]
            moves = self.env['stock.move.line'].search(domain_move_out)
            out_qty = 0
            for move in moves:
                quantity = move.product_uom_id._compute_quantity(move.qty_done, move.product_id.uom_id)
                out_qty = out_qty + quantity
            parent_move_ids = [i.move_id for i in moves]
            for parent_move in parent_move_ids:
                out_qty = out_qty - sum(m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)*2
                                            if (m.picking_id and m.picking_id.ict_sales_costing_date)
                                            else m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)
                                            for m in parent_move.returned_move_ids)
            if out_qty > 0:
                self.sold_products += self.sold_products.new({
                    'manufacturing_order': False,
                    'product_id': p_id,
                    'actual_count': out_qty,
                    'processed_count': out_qty
                })
            else:
                self.sold_products += self.sold_products.new({
                    'manufacturing_order': False,
                    'product_id': p_id,
                    'actual_count': 0,
                    'processed_count': 0
                })

        # get recycled finished products (bom have finished as input)
        lines = self.env['mrp.bom.line'].search([]).filtered(lambda bom_line: bom_line.product_id.id
                                                                   in self.sold_products.product_id.ids)
        bom_ids = lines.bom_id.ids
        recycled = self.env['mrp.production']. search([
            ('move_finished_ids.move_line_ids.cost_date', '>=', self.start_date),
            ('move_finished_ids.move_line_ids.cost_date', '<=', self.end_date),
            ('bom_id', 'in', bom_ids)
            # ('state', '!=', 'cancel'),
        ])

        for recycled_order in recycled:
            done_moves = recycled_order.move_finished_ids.filtered(
                lambda x: x.state == 'done' and x.product_id.id == recycled_order.product_id.id)
            recycled_p = lines.filtered(lambda l: l.bom_id.id == recycled_order.bom_id.id).product_id
            qty_produced = sum(
                m.product_uom._compute_quantity(m.quantity_done, recycled_p.uom_id) for m in done_moves)
            sold_product = self.sold_products.filtered(lambda v: v.product_id.id == recycled_p.id)
            if sold_product:
                sold_product.actual_count = sold_product.actual_count + qty_produced
                sold_product.processed_count = sold_product.processed_count + qty_produced
            else:
                self.sold_products += self.sold_products.new({
                    'manufacturing_order': False,
                    'product_id': recycled_p.id,
                    'actual_count': qty_produced,
                    'processed_count': qty_produced
                })

        last_run = self.env['ict_overhead_expenses.procedure.log'].search([('state', '!=', 'cancel'),
                                                                           ('id', '!=', self.ids[0] if len(self.ids)>0 else False)
                                                                           ],
                                                                          order='end_date desc', limit=1)
        customer_location = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        for sold_product in self.sold_products:
            if sold_product.product_id.categ_id.property_cost_method == 'average':
                if last_run:
                    previous_initial_stock = last_run.sold_products.filtered \
                        (lambda v: v.product_id.id == sold_product.product_id.id).initial_stock
                else:
                    # compute initial stock (Current Stock – Manufactured till now + Delivered (Validated) till now)
                    # current stock
                    qty_svl = sold_product.product_id.with_context(force_company=self.env.company.id).quantity_svl
                    # manufactured till now
                    all_mos = []
                    all_qty_manufactured = 0
                    ss = self.env['mrp.production']. search([
                                                    # ('state', '!=', 'cancel'),
                                                    ('product_id', '=', sold_product.product_id.id)
                                                ])
                    for el in ss:
                        done_moves = el.move_finished_ids.filtered(
                            lambda x: x.state == 'done' and x.product_id.id == el.product_id.id)
                        qty_uom_produced = sum( m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id) for m in  done_moves)
                        if qty_uom_produced > 0:
                            all_qty_manufactured = all_qty_manufactured + qty_uom_produced
                    # all_qty_manufactured = sum(item.qty_produced for item in  all_mos)
                    domain_all_move_out = [('state', '=', 'done'),
                                           ('product_id', '=', sold_product.product_id.id),
                                           ('location_dest_id', '=', customer_location.id)
                                         ]
                    moves = self.env['stock.move.line'].search(domain_all_move_out)
                    all_sold_qty = 0
                    for move in moves:
                        quantity = move.product_uom_id._compute_quantity(move.qty_done, move.product_id.uom_id)
                        all_sold_qty = all_sold_qty + quantity
                    all_parent_move_ids = [i.move_id for i in moves]
                    for parent_move in all_parent_move_ids:
                        all_sold_qty = all_sold_qty - sum(m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)*2
                                                          if (m.picking_id and m.picking_id.ict_sales_costing_date)
                                                          else m.product_uom._compute_quantity(m.quantity_done, m.product_id.uom_id)
                                                          for m in parent_move.returned_move_ids)

                    raw_sugar_product_id = self.env['product.product'].search([('default_code', '=', '0101001')])
                    if raw_sugar_product_id:
                        recycled_mo = sum(q.bom_id.product_uom_id._compute_quantity(q.qty_produced, sold_product.product_id.uom_id) for q in self.env['mrp.production'].search([
                                                                        ('product_id', '=', raw_sugar_product_id.id),
                                                                         ('state', '!=', 'cancel')
                                                                         ])
                                          )
                    else:
                        recycled_mo = 0

                    previous_initial_stock = qty_svl - all_qty_manufactured + all_sold_qty + recycled_mo

                sold_product.previous_initial_stock = previous_initial_stock

                p_cost = self.product_costs.filtered(
                    lambda v: v.manufactured_product.id == sold_product.product_id.id)
                # if there's no MO's for this product in this period
                costed_qty_in_period = p_cost.qty_produced if p_cost else 0

                if costed_qty_in_period > 0:
                    sold_product.initial_stock = previous_initial_stock + costed_qty_in_period - sold_product.actual_count
                    sold_product.processed_count = sold_product.actual_count
                else:
                    sold_product.initial_stock = previous_initial_stock - sold_product.actual_count

                sold_product.product_id.initial_stock = sold_product.initial_stock

        return

    def _prepare_demo_gvs(self):
        # prepare GVS from sold items (COGS gvs)
        res_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_rest_account_id'))
        for item in self.sold_products:
            credit_value = {}
            debit_value = {}
            if item.processed_count > 0:
                product_accounts = {item.product_id.id: item.product_id.product_tmpl_id.get_product_accounts()}
                if item.product_id.categ_id.property_cost_method == 'average':
                    elem = self.product_costs.filtered(lambda i: i.manufactured_product.id == item.product_id.id)
                if item.product_id.categ_id.property_cost_method == 'fifo':
                    elem = self.product_costs.filtered(lambda i: i.mo_id.id == item.manufacturing_order.id)
                if elem.cost != 0:
                    if elem.cost < 0:
                        credit_account_id = product_accounts[item.product_id.id]['expense'].id
                        debit_account_id = res_account_id
                    else:
                        credit_account_id = res_account_id
                        debit_account_id = product_accounts[item.product_id.id]['expense'].id
                    if item.product_id.categ_id.property_cost_method == 'average' :
                        if elem.new_std_price != 0:
                            pdu = elem.cost / (item.previous_initial_stock + elem.qty_produced)
                            debit_value['debit'] = abs(pdu * item.processed_count)
                            credit_value['credit'] = abs(pdu * item.processed_count)
                        else:
                            debit_value['debit'] = abs(elem.cost)
                            credit_value['credit'] = abs(elem.cost)

                    if item.product_id.categ_id.property_cost_method == 'fifo':
                        debit_value['debit'] = abs((elem.cost / elem.qty_produced) * item.count)
                        credit_value['credit'] = abs((elem.cost / elem.qty_produced) * item.count)

                    credit_value['debit'] = 0
                    credit_value['ref'] = _(str(item.processed_count) + ' items from ' + item.product_id.name + ' was sold')
                    credit_value['date'] = self.end_date
                    credit_value['account_id'] = credit_account_id
                    credit_value['type'] = 'SOLD_ITEMS'
                    credit_value['product_id'] = item.product_id.id
                    credit_value['mo_id'] = item.manufacturing_order.id

                    debit_value['credit'] = 0
                    debit_value['ref'] = _(str(item.processed_count) + ' items from ' + item.product_id.name + ' was sold')
                    debit_value['date'] = self.end_date
                    debit_value['account_id'] = debit_account_id
                    debit_value['type'] = 'SOLD_ITEMS'
                    debit_value['product_id'] = item.product_id.id
                    debit_value['mo_id'] = item.manufacturing_order.id

                    self.generated_GVs += self.generated_GVs.new(credit_value)
                    self.generated_GVs += self.generated_GVs.new(debit_value)
        return

    def _create_expense_journals_entry(self):
        journal_type = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_cogs_journal'))

        line_ids = []
        for item in self.generated_GVs.filtered(lambda i: i.type == 'CARRIED_BY_EXPENSE'):
            line = {}
            line['debit'] = item.debit
            line['credit'] = item.credit
            line['move_id'] = False
            line['id'] = False
            line['ref'] = item.ref
            line['date'] = self.end_date
            line['product_id'] = False
            line['exclude_from_invoice_tab'] = True
            line['amount_residual'] = 0
            line['account_id'] = item.account_id.id  # credit_account_id
            line_ids.append((0, 0, line))
        if len(line_ids) > 0:
            jv = self.env['account.move'].create({
                'move_type': 'entry',
                'ref': '',
                'date': self.end_date,
                'journal_id': journal_type,
                'company_id': self.env.company.id,
                'line_ids': line_ids
            })
            jv.action_post()

    def _create_cogs_for_sold_products_journals(self):
        # prepare GVS from sold items (COGS gvs)
        # cogs_account_id=int(self.env['ir.config_parameter'].get_param('ict_overhead_expenses.ict_cogs_account'))
        journal_type = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_cogs_journal'))
        res_account_id = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id'))

        line_ids = []
        for item in self.generated_GVs.filtered(lambda i: i.type == 'SOLD_ITEMS'):
            p = self.env['product.product'].search([('id', '=', item.product_id)])
            if p.categ_id.property_cost_method == 'average' :
                sold_count = self.sold_products.filtered(lambda v: v.product_id.id == item.product_id).processed_count
            if p.categ_id.property_cost_method == 'fifo':
                sold_count = self.sold_products.filtered(lambda v: v.manufacturing_order.id == item.mo_id).count

            line = {}
            line['debit'] = item.debit
            line['credit'] = item.credit
            line['move_id'] = False
            line['id'] = False
            line['ref'] = _(str(sold_count) + ' items from ' + p.name + ' was sold')
            line['date'] = self.end_date
            line['product_id'] = False
            line['exclude_from_invoice_tab'] = True
            line['amount_residual'] = 0
            line['account_id'] = item.account_id.id # credit_account_id
            line_ids.append((0, 0, line))
        if len(line_ids) > 0:
            jv = self.env['account.move'].create({
                'move_type': 'entry',
                'ref': '',
                'date': self.end_date,
                'journal_id': journal_type,
                'company_id': self.env.company.id,
                'line_ids': line_ids
            })
            jv.action_post()

    def reverse_operation(self, sold_products, product_costs):
        # prepare GVS from sold items (COGS gvs)
        # cogs_account_id=int(self.env['ir.config_parameter'].get_param('ict_overhead_expenses.ict_cogs_account'))
        journal_type = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_cogs_journal'))
        res_account_id = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id'))

        line_ids = []
        for item in sold_products:
            credit_value = {}
            debit_value = {}
            product_accounts = {item.product_id.id: item.product_id.product_tmpl_id.get_product_accounts()}
            if item.product_id.categ_id.property_cost_method == 'average':
                elem = product_costs.filtered(lambda i: i.manufactured_product.id == item.product_id.id)
            if item.product_id.categ_id.property_cost_method == 'fifo':
                elem = product_costs.filtered(lambda i: i.mo_id.id == item.manufacturing_order.id)
            if elem.cost > 0:
                credit_account_id = product_accounts[item.product_id.id]['expense'].id
                debit_account_id = res_account_id
            else:
                credit_account_id = res_account_id
                debit_account_id = product_accounts[item.product_id.id]['expense'].id

            if item.product_id.categ_id.property_cost_method == 'average':
                if elem.new_std_price != 0:
                    debit_value['debit'] = abs((elem.new_std_price - item.product_id.standard_price)*item['count'])
                    credit_value['credit'] = abs((elem.new_std_price - item.product_id.standard_price)*item['count'])
                else:
                    debit_value['debit'] = abs(elem.cost)
                    credit_value['credit'] = abs(elem.cost)

            if item.product_id.categ_id.property_cost_method == 'fifo':
                debit_value['debit'] = abs((elem.cost / elem['qty_produced']) * item['count'])
                credit_value['credit'] = abs((elem['cost'] / elem['qty_produced']) * item['count'])

            credit_value['debit'] = 0
            credit_value['move_id'] = False
            credit_value['id'] = False
            credit_value['ref'] = _(str(item.count) + 'Inverse - items from ' + item.product_id.name + ' was sold')
            credit_value['date'] = self.end_date
            credit_value['product_id'] = False
            credit_value['exclude_from_invoice_tab'] = True
            credit_value['amount_residual'] = 0
            credit_value['account_id'] = credit_account_id

            debit_value['credit'] = 0
            debit_value['move_id'] = False
            debit_value['id'] = False
            debit_value['ref'] = _(str(item.count) + 'Inverse - items from ' + item.product_id.name + ' was sold')
            debit_value['date'] = self.end_date
            debit_value['product_id'] = False
            debit_value['exclude_from_invoice_tab'] = True
            debit_value['amount_residual'] = 0
            debit_value['account_id'] = debit_account_id
            line_ids.append((0, 0, credit_value))
            line_ids.append((0, 0, debit_value))
        if len(line_ids) > 0:
            jv = self.env['account.move'].create({
                'move_type': 'entry',
                'ref': '',
                'date': self.end_date,
                'journal_id': journal_type,
                'company_id': self.env.company.id,
                'line_ids': line_ids
            })
            jv.action_post()

    def close_without_cost(self):
        self.process_action()

    def _compute_processed_balance(self, finished_mo):
        standard_cost = 0
        standard_cost_product_ids = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_standard_cost_product_ids')
        sscpids = literal_eval(standard_cost_product_ids)
        for mo in finished_mo:
            for standard_item in sscpids:
                standard_overhead_labor_product_id = self.env['product.product'].search([('id', '=', standard_item)])
                standard_qty_finished_in_period = sum (sc.product_uom_qty for sc in mo.move_raw_ids.
                                                        filtered(lambda v: v.product_id.id == standard_item)
                                                      )
                standard_unit_cost = standard_qty_finished_in_period/mo.product_qty
                finished_product_qty_in_period = sum(f.qty_done for f in mo.finished_move_line_ids.
                                             filtered(lambda item: item.cost_date != False and self.start_date <= item.cost_date <= self.end_date))
                standard_cost = standard_cost + finished_product_qty_in_period*standard_unit_cost*standard_overhead_labor_product_id.standard_price

        # if standard_cost == 0:
        #     return 0
        actual_cost = self.get_analytic_account_balance()
        self.actual_cost = actual_cost
        self.standard_cost = standard_cost
        res = actual_cost - standard_cost
        # Get previous processed balance
        last_run = self.env['ict_overhead_expenses.procedure.log'].search([('state', '!=', 'cancel'),
                                                                           ('id', '!=', self.ids[0])
                                                                           ],
                                                                          order='end_date desc', limit=1)
        if last_run:
            self.previous_processed_balance = last_run.processed_balance_to_next_period

        self.processed_balance = res
        self.actual_processed_balance = res + self.previous_processed_balance
        return

    def _compute_product_costs(self, mos):
        standard_cost_product_ids = self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_standard_cost_product_ids')
        sscpids = literal_eval(standard_cost_product_ids)
        self.product_costs = False
        if len(mos) == 0:
            return []
        # res = []
        for m in mos:
            if any(ser.product_id for ser in m.move_raw_ids.filtered(lambda mr: mr.product_id.id in sscpids)):
                costed_qty_in_period = sum(e.qty_done for e in m.finished_move_line_ids.filtered
                                            (lambda i: i.cost_date != False and i.cost_date >= self.start_date and i.cost_date <= self.end_date)
                                           )
                if costed_qty_in_period > 0:
                    if m.product_id.categ_id.property_cost_method == 'fifo':
                        self.product_costs += self.env['ict_overhead_expenses.product.cost'].new(
                            {
                                'manufactured_product': m.product_id.id,
                                'qty_produced': costed_qty_in_period,
                                'overhead_qty': self.env['ict_overhead_expenses.ict_standard_cost_per_product']
                                                .search([('product_id', '=', m.product_id.id)]).percentage,
                                'mo_id': m.id,
                            }
                        )
                    elif m.product_id.categ_id.property_cost_method == 'average':
                        item = self.product_costs.filtered(lambda i: i.manufactured_product.id == m.product_id.id)
                        # elem = list(elem for elem in res if elem['manufactured_product'] == m.product_id.id)
                        if item:
                            item.qty_produced = item.qty_produced + costed_qty_in_period
                        else:
                            self.product_costs += self.product_costs.new(
                                {'manufactured_product': m.product_id.id,
                                 'qty_produced': costed_qty_in_period,
                                 'overhead_qty': self.env['ict_overhead_expenses.ict_standard_cost_per_product']
                                     .search([('product_id', '=', m.product_id.id)]).percentage,
                                 'mo_id': False,
                                 # 'finished_move_id': False
                                 }
                            )
                    else:
                        raise UserError(_('you have costed a manufactured products that have standard costing method'))

        overall_overhead_qty = sum(p.overhead_qty*p.qty_produced for p in self.product_costs)

        # if overall_overhead_qty <= 0:
        #     raise UserError(_("Standard Cost table have percentages equal to zero, please setup a valid standard cost table"))
        processed_balance = self.actual_processed_balance
        for item in self.product_costs:
            item.cost = round(item.overhead_qty*item.qty_produced*processed_balance/overall_overhead_qty, 5)

        return

    def process_action(self):
        # update cost of products according
        self._create_cogs_for_sold_products_journals()
        self._create_expense_journals_entry()
        actual_finish = self._get_done_manufactured()
        for item in actual_finish:
            for line in item.finished_move_line_ids.filtered(lambda v: v.cost_date != False and self.start_date <= v.cost_date <= self.end_date):
                line.ict_is_processed_line = True
            if item.bom_id.finishing_product_ok and len(item.finished_move_line_ids.filtered(lambda i: i.state == 'done' and i.cost_date is False)) > 0:
                raise UserError('there is Manufacturing orders in this period '
                                'that have no costing date, please fill it before')
        for item in self.product_costs:
            if item.manufactured_product.categ_id.property_cost_method == 'average':
                counterpart_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'ict_overhead_expenses.ict_rest_account_id'))
                if item.new_std_price > 0:
                    if item.manufactured_product.qty_available > 0:
                        item.manufactured_product.sudo().change_std_price_enhanced(item.new_std_price,
                                                                                   counter_part_account_id=counterpart_account_id)
                if item.new_std_price == 0 and item.manufactured_product.qty_available == 0 and item.cost != 0:
                    self.clear_plus_minus_with_cogs(item)
                out_moves = self.sold_products.filtered(lambda v: v.product_id.id == item.manufactured_product.id).sold_move_line_ids
                for m in out_moves:
                    m.write({'ict_included_in_product_cost': True})

            if item.manufactured_product.categ_id.property_cost_method == 'fifo':
                candidates = item.mo_id.move_finished_ids
                for candidate in candidates:
                    linked_layer = candidate.stock_valuation_layer_ids[-1]
                    sold_count = self.sold_products.filtered(lambda v: v.manufacturing_order.id == item.mo_id.id).count
                    # Prorate the value at what's still in stock
                    cost_to_add = item.cost - (sold_count * item.unit_cost)
                    if cost_to_add != 0:
                        if linked_layer.remaining_value > 0 and (linked_layer.remaining_value + cost_to_add) > 0:
                            valuation_layer = self.env['stock.valuation.layer'].create({
                                'value': cost_to_add,
                                'unit_cost': 0,
                                'quantity': 0,
                                'remaining_qty': 0,
                                'stock_valuation_layer_id': linked_layer.id,
                                'description': 'Addition Overhead',
                                'stock_move_id': candidate.id,
                                'product_id': candidate.product_id.id,
                                'company_id': self.env.company.id,
                            })
                            ict_cogs_journal = self.env['ir.config_parameter'].sudo().get_param(
                                'ict_overhead_expenses.ict_cogs_journal')

                            move_vals = {
                                'journal_id': int(ict_cogs_journal),
                                'date': self.end_date,
                                'ref': 'Increase/decrease stock valuation for (%s)' % (item.manufactured_product.name),
                                'line_ids': [],
                                'move_type': 'entry',
                            }
                            linked_layer.remaining_value += cost_to_add
                            linked_layer.ict_overhead_processed_quantity += sold_count
                            res = self.generated_GVs.filtered(lambda v: v.type == 'CHANGE_PRICE' and v.mo_id == item.mo_id.id)
                            lines = []
                            for j in res:
                                lines.append((0, 0,
                                              {
                                               'name': j.ref,
                                               'product_id': j.product_id,
                                               'quantity': 0,
                                               'account_id': j.account_id.id,
                                               'debit': j.debit,
                                               'credit': j.credit
                                               }
                                              ))
                            move_vals['line_ids'] = lines
                            move_vals['stock_valuation_layer_ids'] = [(6, None, [valuation_layer.id])]
                            account_move = self.env['account.move'].create(move_vals)
                            account_move.sudo().post()

        self.env['ict_overhead_expenses.period'].create_periods(opened_periods=1)
        period = self.env['ict_overhead_expenses.period'].search([('date_start', '=', self.start_date),
                                                          ('date_stop', '=', self.end_date),
                                                          ('state', '=', 'open')
                                                          ])[0]
        period.state = 'close'
        self.write({'state': 'done'})

    def clear_plus_minus_with_cogs(self, item):
        res_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_rest_account_id'))
        product_accounts = {item.manufactured_product.id: item.manufactured_product.product_tmpl_id.get_product_accounts()}
        journal_type = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_cogs_journal'))
        if item.cost < 0:
            credit_account_id = product_accounts[item.manufactured_product.id]['expense'].id
            debit_account_id = res_account_id
        else:
            credit_account_id = res_account_id
            debit_account_id = product_accounts[item.manufactured_product.id]['expense'].id
        credit_value = {}
        debit_value = {}

        credit_value['debit'] = 0
        credit_value['credit'] = abs(item.cost)
        credit_value['move_id'] = False
        credit_value['id'] = False
        credit_value['ref'] = 'Clear PLUS/MINUS ACC With COGS'
        credit_value['date'] = self.end_date
        credit_value['product_id'] = False
        credit_value['exclude_from_invoice_tab'] = True
        credit_value['amount_residual'] = 0
        credit_value['account_id'] = credit_account_id

        debit_value['debit'] = abs(item.cost)
        debit_value['credit'] = 0
        debit_value['move_id'] = False
        debit_value['id'] = False
        debit_value['ref'] = 'Clear PLUS/MINUS ACC With COGS'
        debit_value['date'] = self.end_date
        debit_value['product_id'] = False
        debit_value['exclude_from_invoice_tab'] = True
        debit_value['amount_residual'] = 0
        debit_value['account_id'] = debit_account_id
        lines = [(0, 0, credit_value), (0, 0, debit_value)]

        jv = self.env['account.move'].create({
            'move_type': 'entry',
            'ref': '',
            'date': self.end_date,
            'journal_id': journal_type,
            'company_id': self.env.company.id,
            'line_ids': lines
        })
        jv.action_post()

    def cancel_button(self):
        self.ensure_one()
        if self.state in ['draft','draft_with_issue']:
            # change state
            self.write({'state': 'cancel'})
        else:
            raise UserError(_('You can only cancel a draft operation'))

    def get_analytic_account_balance(self):
        ict_analytic_account = int(self.env['ir.config_parameter'].sudo().\
            get_param('ict_overhead_expenses.ict_analytic_account'))

        AccountAnalyticLine = self.env['account.analytic.line']
        analytic_entries_domain = [('period_date', '>=', self.start_date),
                                   ('period_date', '<=', self.end_date),
                                   ('account_id', '=', ict_analytic_account)
                                   ]

        accounts = AccountAnalyticLine.search(analytic_entries_domain)

        actual_cost = sum(item.amount for item in accounts)
        return abs(actual_cost)

    def unlink(self):
        if self.state not in ['draft', 'draft_with_issue']:
            raise UserError(_('Only draft operations can be deleted'))
        self.product_costs.unlink()
        self.sold_products.unlink()
        self.generated_GVs.unlink()
        res = super(OverheadProcedureLog, self).unlink()
        return res
    #####--------------------Ui functions----------------#########

    def show_related_moves(self):
        self.ensure_one()
        view_xml_id = self.env.context.get('xml_id')
        if view_xml_id:
            v_id = self.env['ir.ui.view'].search([('name', '=', view_xml_id)], order='priority')[0].id
            return {
                'type': 'ir.actions.act_window',
                'name': 'Operation Moves',
                'view_mode': 'tree',
                'res_model': 'stock.move',
                'views': [(v_id, 'tree')],
                'context': {'default_ict_proc_id': self.id},
                'domain': [('ict_proc_id', '=', self.id)]
            }
        return False

    def show_related_product_costs(self):
        self.ensure_one()
        view_xml_id = self.env.context.get('xml_id')
        if view_xml_id:
            v_id = self.env['ir.ui.view'].search([('name', '=', view_xml_id)]).id
            return {
                'type': 'ir.actions.act_window',
                'name': 'Product Costs',
                'view_mode': 'tree',
                'res_model': 'ict_overhead_expenses.product.cost',
                'views': [(v_id, 'tree')],
                'context': {'default_proc_id': self.id},
                'domain': [('proc_id', '=', self.id)]
            }
        return False

    def show_sold_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sold Products',
            'view_mode': 'tree',
            'res_model': 'ict_overhead_expenses.sold.items',
            'context': {'default_proc_id': self.id},
            'domain': [('proc_id', '=', self.id)]
        }

    def show_sold_generated_gvs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sold Items Journals',
            'view_mode': 'tree',
            'res_model': 'ict_overhead_expenses.gv.account.move.line',
            'context': {'default_proc_id': self.id},
            'domain': [('proc_id', '=', self.id), ('type', '=', 'SOLD_ITEMS')]
        }

    def show_expense_account_move(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expense JV',
            'view_mode': 'tree',
            'res_model': 'ict_overhead_expenses.gv.account.move.line',
            'context': {'default_proc_id': self.id},
            'domain': [('proc_id', '=', self.id), ('type', '=', 'CARRIED_BY_EXPENSE')]
        }

    def show_change_price_generated_gvs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Changing Price Journals',
            'view_mode': 'tree',
            'res_model': 'ict_overhead_expenses.gv.account.move.line',
            'context': {'default_proc_id': self.id},
            'domain': [('proc_id', '=', self.id), ('type', '=', 'CHANGE_PRICE')]
        }

    def add_months(self, sourcedate, months):
        month = sourcedate.month - 1 + months
        year = sourcedate.year + month // 12
        month = month % 12 + 1
        day = min(sourcedate.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day)


class ICTOverheadProductCost(models.Model):
    _name = 'ict_overhead_expenses.product.cost'
    _description = 'the cost afforded by product in this overhead computation'

    proc_id = fields.Many2one('ict_overhead_expenses.procedure.log', string='Computation')
    manufactured_product = fields.Many2one('product.product', string='Product')
    qty_produced = fields.Float(string='quantity produced')
    overhead_qty = fields.Float(string='Percentage')
    cost = fields.Float(string='cost', default=0)
    unit_cost = fields.Float(string='unit cost', compute='_compute_unit_cost')
    new_std_price = fields.Float(string='New Cost')
    mo_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    costing_method = fields.Char(string='costing method')
    current_period_intial_stock = fields.Float('Period Initial Stock', compute='_compute_initial_stock')
    sold_quantity = fields.Float('processed sold quantity', compute='_compute_initial_stock')
    next_period_initial_stock = fields.Float('Next Period Initial Stock', compute='_compute_initial_stock')

    def _compute_initial_stock(self):
        for res in self:
            elem = res.proc_id.sold_products.filtered(
                lambda v: v.product_id.id == res.manufactured_product.id)
            res.current_period_intial_stock = elem.previous_initial_stock
            res.sold_quantity = elem.processed_count
            res.next_period_initial_stock = elem.initial_stock

    def _compute_unit_cost(self):
        for rec in self:
            rec.unit_cost = rec.cost/rec.qty_produced


class ICTOverheadSoldItems(models.Model):
    _name = 'ict_overhead_expenses.sold.items'

    proc_id = fields.Many2one('ict_overhead_expenses.procedure.log')
    product_id = fields.Many2one('product.product', string='Product')
    manufacturing_order = fields.Many2one('mrp.production', string='Manufacturing Order')
    sold_move_line_ids = fields.One2many('stock.move.line', 'ict_period_id', string='Out move line')
    actual_count = fields.Float('Actual Sold Count')
    processed_count = fields.Float('Processed Sold Count')
    initial_stock = fields.Float('Initial Stock')
    previous_initial_stock = fields.Float('Previous Initial Stock')


class ICTOverheadAccountMove(models.Model):
    _name = 'ict_overhead_expenses.gv.account.move.line'

    proc_id = fields.Many2one('ict_overhead_expenses.procedure.log')
    credit = fields.Float('credit')
    debit = fields.Float('debit')
    account_id = fields.Many2one('account.account', string='account')
    ref = fields.Char('Ref')
    date = fields.Date('Date')
    type = fields.Char('Type')
    product_id = fields.Integer(string='product')
    mo_id = fields.Integer(string='mo')


class ICTOverheadExpensesPeriods(models.Model):
    _name = 'ict_overhead_expenses.period'

    name = fields.Char(string='Name')
    state = fields.Selection([
        ('open', 'Opened'),
        ('close', 'Closed')
    ])
    date_start = fields.Date('From', required=True)
    date_stop = fields.Date('To', required=True)
    company_id = fields.Many2one('res.company', string='Company')

    def create_periods(self, opened_periods):
        # start_date = fields.Date.from_string(rec.date_start)
        # end_date = fields.Date.from_string(rec.date_stop)
        period_type = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_period')

        last_opened_period = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')], order='id desc', limit=1)
        if last_opened_period:
            start_date = last_opened_period.date_start + relativedelta(months=1)
        else:
            start_date = fields.Date.from_string(
                self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_initial_start_date')
            )

        index = 0
        while index < opened_periods:
            de = self.find_date_range(start_date, period_type)
            self.env['ict_overhead_expenses.period'].create({
                'name': self._get_code(start_date, period_type=period_type),
                'date_start': start_date.strftime('%Y-%m-%d'),
                'date_stop': de.strftime('%Y-%m-%d'),
                'state': 'open',
                'company_id': self.env.company.id
            })
            if period_type == 'month':
                start_date = start_date + relativedelta(months=1)
            if period_type == 'quarter':
                start_date = start_date + relativedelta(months=1 * 4)
            if period_type == 'half':
                start_date = start_date + relativedelta(months=1 * 6)
            index += 1

    def _get_code(self, date, period_type):
        if period_type == 'month':
            return format_date(date, locale='en', format="MMM") + '-' + str(date.year)
        if period_type == 'quarter':
            quarterNum = int((date.month + 1) / 4) + 1
            return quarterNum
        if period_type == 'half':
            halfNum = int((date.month) / 6) + 1
            return halfNum

    def find_date_range(self, start_date, period_type):

        if period_type == 'month':
            last_day = calendar.monthrange(start_date.year, start_date.month)[1]
            end_date = datetime.date(start_date.year, start_date.month, last_day)
        if period_type == 'quarter':
            d = self.add_months(start_date, 2)
            last_day = calendar.monthrange(d.year, d.month)[1]
            end_date = datetime.date(d.year, d.month, last_day)
        if period_type == 'semi':
            d = self.add_months(start_date, 5)
            last_day = calendar.monthrange(d.year, d.month)[1]
            end_date = datetime.date(d.year, d.month, last_day)
        return end_date
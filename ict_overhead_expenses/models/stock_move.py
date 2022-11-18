# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ICTSaleDeliveryModel(models.Model):
    _inherit = 'stock.picking'

    ict_sales_costing_date = fields.Date('Costing Date')
    sapps_is_real_time = fields.Boolean(string="Is Real Time", compute="_compute_is_real_time")

    def _compute_is_real_time(self):
        for res in self:
            res.sapps_is_real_time = bool(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))

    def action_done(self):
        res = super(ICTSaleDeliveryModel, self).action_done()
        self._compute_is_real_time()
        if self.sapps_is_real_time and self.sale_id:
            # check period is opened
            last_opened_period = self.env['ict_overhead_expenses.period'].search(
                [('state', '=', 'open')], order='date_start desc', limit=1)
            if last_opened_period and last_opened_period.date_stop < fields.date.today():
                raise UserError(_(
                    'You Cannot proceed with posting inventory, the last opened period is %s' % last_opened_period.name))
            self.ict_sales_costing_date = fields.date.today()
        return res


class ICTLoadingCostStockMove(models.Model):
    _inherit = 'stock.move'

    ict_proc_id = fields.Many2one(comodel_name='ict_overhead_expenses.procedure.log', string='Loading Cost Operation', store=True)

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        self.ensure_one()
        if self.state == 'done' and self.product_id.bom_ids and \
            len(self.move_line_ids.filtered(lambda v: v.cost_date)) > 0 and \
            len(self.product_id.bom_ids.filtered(lambda i: i.finishing_product_ok)) > 0:
            group_by_costing_date = []
            for item in self.move_line_ids.filtered(lambda v: v.cost_date):
                try:
                    element = next(i for i in group_by_costing_date if i["costing_date"] == item.cost_date)
                    element['count'] = element['count'] + 1
                except StopIteration:
                    group_by_costing_date.append({'costing_date': item.cost_date, 'count':1})

            total = sum (i['count'] for i in group_by_costing_date)
                # group_by_costing_date[item.cost_date] = group_by_costing_date[item.cost_date] + 1 if group_by_costing_date[item.cost_date] else 1
            for elem in group_by_costing_date:
                AccountMove = self.env['account.move'].with_context(default_journal_id=journal_id)

                move_lines = self._prepare_account_move_line(elem['count'], cost*elem['count']/total, credit_account_id, debit_account_id, description)
                if move_lines:
                    date = self._context.get('force_period_date', fields.Date.context_today(self))
                    new_account_move = AccountMove.sudo().create({
                        'journal_id': journal_id,
                        'line_ids': move_lines,
                        'date': elem['costing_date'],
                        'ref': description,
                        'stock_move_id': self.id,
                        'stock_valuation_layer_ids': [(6, None, [svl_id])],
                        'move_type': 'entry',
                    })
                    new_account_move.post()
        else:
            return super(ICTLoadingCostStockMove, self)._prepare_account_move_vals(credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost)


class ICTLoadingCostMrpProduction(models.Model):
    _inherit = 'mrp.production'

    unallocated_mo_count = fields.Integer('Unallocated MO Count', compute='_compute_unallocated_move_count', search='_search_unallocated_mo')

    def _search_unallocated_mo(self, operator, value):
        recs = self.search([])
        result = []
        if recs:
            for r in recs:
                if r.bom_id.finishing_product_ok and len(r.finished_move_line_ids.filtered(lambda a: a.cost_date is False)) > 0:
                    result.append(r.id)
        return [('id', 'in', result)]

    @api.depends('name')
    def _compute_unallocated_move_count(self):
        for res in self:
            if res.state == 'done':
                res.unallocated_mo_count = len(res.finished_move_line_ids.filtered(lambda item: False if item.cost_date else True))
            else:
                res.unallocated_mo_count = 0


class ICTOverheadStockMoveLine(models.Model):
    _inherit = "stock.move.line"

    cost_date = fields.Date('Costing Date')
    ict_included_in_product_cost = fields.Boolean('Overhead Processed', default=False)
    ict_period_id = fields.Many2one(comodel_name='ict_overhead_expenses.sold.items', string='period')
    ict_is_processed_line = fields.Boolean('Is Processed', default=False)

    @api.constrains('cost_date')
    def check_cost_date(self):
        if self.cost_date:
            if self.ict_is_processed_line:
                raise UserError(_('You cannot modify a processed line'))
            last_run = self.env['ict_overhead_expenses.procedure.log'].sudo().search([('state', '=', 'done')], order='id desc',
                                                                              limit=1)
            if last_run and last_run.end_date >= self.cost_date:
                raise UserError(_('You cannot assign a costing date of closed period'))
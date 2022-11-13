##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api
from odoo.exceptions import UserError


class StockPickingAnalyticTag(models.Model):
    _inherit = 'stock.picking'

    should_costing_be_visible = fields.Boolean(compute='_compute_should_costing_be_visible')
    should_period_be_visible = fields.Boolean(compute='_compute_should_costing_be_visible')

    @api.depends('name')
    def _compute_should_costing_be_visible(self):
        is_installed = self.env['ir.module.module'].sudo().search_count([('name', '=', 'ict_overhead_expenses'),
                                                                  ('state', '=', 'installed')])
        for res in self:
            if is_installed:
                res.should_costing_be_visible = True
                res.should_period_be_visible = False if res.sapps_is_real_time else True
            else:
                res.should_costing_be_visible = False
                res.should_period_be_visible = False


class StockMoveAnalyticTag(models.Model):
    _inherit = 'stock.move'

    analytic_tag_ids = fields.Many2many(
        'account.analytic.tag',
        states={'done': [('readonly', True)]},
    )
    analytic_account_id = fields.Many2one('account.analytic.account',  states={'done': [('readonly', True)]})
    is_costing = fields.Boolean('Is Costing', default=False)
    # should_costing_be_visible = fields.Boolean(compute='_compute_should_costing_be_visible')
    period = fields.Selection(selection=[
        ('oldest', 'Oldest Period Not Closed'),
        ('first_next', 'Next Period 1'),
        ('second_next', 'Next Period 2')
    ], string='period')
    period_opened = fields.Many2one('ict_overhead_expenses.period', string="Period",  domain=[('state', '=', 'open')])
    sapps_is_real_time = fields.Boolean(string="Is Real Time", compute="_compute_is_real_time")

    def _compute_is_real_time(self):
        for res in self:
            res.sapps_is_real_time = bool(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))

    @api.onchange('is_costing')
    def _onchange_is_costing(self):
        self._compute_is_real_time()
        ict_rest_account = int(
            self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_account'))

        if self.picking_id.should_costing_be_visible:
            if self.picking_id.location_dest_id.usage == 'inventory' and (self.picking_id.location_dest_id.valuation_in_account_id.id == ict_rest_account
                                                  or self.picking_id.location_dest_id.valuation_out_account_id.id == ict_rest_account):
                self.is_costing = True

        overhead_container_account = self.env['account.analytic.account'].sudo().search([('id', '=', ict_rest_account)], limit=1)
        if self.is_costing:
            self.analytic_account_id = overhead_container_account
            if not self.period_opened and not self.sapps_is_real_time:
                self.period_opened = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')],
                                    order='date_stop asc')[0] if not self.period_opened else self.period_opened
        else:
            if self.analytic_account_id.id == overhead_container_account.id:
                self.analytic_account_id = False

    def _prepare_account_move_line(
            self, qty, cost, credit_account_id, debit_account_id, description):
        result = super()._prepare_account_move_line(
            qty=qty, cost=cost, credit_account_id=credit_account_id,
            debit_account_id=debit_account_id, description=description)
        rest = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id'))
        for res in result:
            if res[2]['account_id'] == rest:
                res[2]['analytic_tag_ids'] = [(6, 0, self.analytic_tag_ids.ids)]
                res[2]['analytic_account_id'] = self.analytic_account_id.id
                if self.is_costing:
                    self._compute_is_real_time()
                    if self.sapps_is_real_time:

                        res[2]['transfer_journal_cost'] = True
                        period = self.env['ict_overhead_expenses.period'].search([('date_start', '<=', self.date),
                                                                         ('date_stop', '>=', self.date),
                                                                         ('state', '=', 'open')
                                                                         ], limit=1)
                        if not period:
                            raise UserError("Please Insure that the current period is opened")
                        res[2]['period_opened'] = period.id
                    else:
                        res[2]['transfer_journal_cost'] = True
                        res[2]['period_opened'] = self.period_opened.id
        return result

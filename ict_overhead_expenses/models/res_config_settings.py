# # -*- coding: utf-8 -*-
# # Part of Odoo. See LICENSE file for full copyright and licensing details.
#
from odoo import api, fields, models, _
from ast import literal_eval
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ict_cogs_journal = fields.Many2one('account.journal', 'COGS JVs type')
    ict_standard_cost_product_ids = fields.Many2many('product.product', string='product for standard costs')
    ict_rest_account_id = fields.Many2one('account.account', string='Rest Account')
    ict_analytic_account = fields.Many2one('account.analytic.account', string='Analytic Account')
    ict_initial_start_date = fields.Date(string='Initial Start Date')
    ict_analytic_period = fields.Selection(string='Period', selection=[
        ('month','Month'),
        ('quarter', 'Quarter'),
        ('half', 'Half Year')
    ])
    sapps_period_count = fields.Float(string='Number of opened periods allowed')
    sapps_is_real_time = fields.Boolean(string="Is Real Time Costing Method")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ict_cogs_journal = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_cogs_journal')
        standard_cost_product_ids = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_standard_cost_product_ids')
        ict_rest_account_id = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_rest_account_id')
        ict_analytic_period = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_period')
        ict_analytic_account = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_account')
        ict_initial_start_date = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_initial_start_date')
        sapps_period_count = float(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_period_count'))
        sapps_is_real_time = bool(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))
        if standard_cost_product_ids:
            scp = [(6, 0, literal_eval(standard_cost_product_ids))]
        else:
            scp = False

        res.update(
            ict_cogs_journal=int(ict_cogs_journal),
            ict_rest_account_id=int(ict_rest_account_id),
            ict_standard_cost_product_ids=scp,
            ict_analytic_period=ict_analytic_period,
            ict_analytic_account=int(ict_analytic_account),
            ict_initial_start_date=ict_initial_start_date,
            sapps_period_count=sapps_period_count,
            sapps_is_real_time=sapps_is_real_time,
        )
        return res

    def set_values(self):
        old_opened_period = self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_period_count')

        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_cogs_journal', self.ict_cogs_journal.id)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_standard_cost_product_ids', self.ict_standard_cost_product_ids.ids)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_rest_account_id', self.ict_rest_account_id.id)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_analytic_period', self.ict_analytic_period)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_analytic_account', self.ict_analytic_account.id)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.ict_initial_start_date', self.ict_initial_start_date)
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.sapps_is_real_time', self.sapps_is_real_time)

        if self.sapps_period_count == float(old_opened_period) and self.sapps_period_count != 0:
            return
        if self.sapps_period_count <= 0:
            raise UserError(_('Invalid Allowed Periods To Open'))
        self.env['ir.config_parameter'].sudo().set_param('ict_overhead_expenses.sapps_period_count', self.sapps_period_count)
        all_opened_period = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')], order='date_start')
        if len(all_opened_period) > self.sapps_period_count:
            # remove
            total = len(all_opened_period)
            diff = total - self.sapps_period_count
            index = 0
            while index < diff:
                c = self.env['account.analytic.line'].search_count([('period_date', '>=', all_opened_period[total - index - 1].date_start),
                                                                    ('period_date', '<=', all_opened_period[total - index - 1].date_stop)
                                                                    ])
                if c > 0:
                    raise UserError(_('Period %s contain overhead items'%all_opened_period[total - index - 1].name))
                all_opened_period[total - index - 1].unlink()
                index = index + 1

        if len(all_opened_period) < self.sapps_period_count:
            self.env['ict_overhead_expenses.period'].create_periods(opened_periods=self.sapps_period_count - len(all_opened_period))
        if len(all_opened_period) == 0:
            self.env['ict_overhead_expenses.period'].create_periods(opened_periods=self.sapps_period_count)

        return res

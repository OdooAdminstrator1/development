# models/res_config_settings.py

from odoo import models, fields, api
from ast import literal_eval
from odoo.exceptions import UserError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cost_account_ids = fields.Many2many(
        'account.account',
        'res_config_settingstrace_conf_rel',  # relation table
        'config_cost_id', 'accout_cost_id',
        string="Cost of Revenue Accounts",
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    )
    cost_journal_ids = fields.Many2many(
        'account.journal',
        # 'res_config_settings_ost_account_rel',  # relation table
        # 'config_id', 'journal_id',
        string="Sales Journal", # Stock Valuation Journal, Revenue Acounts
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    )

    revenue_ids = fields.Many2many(
        'account.account',
        'res_config_settingstrace_revenue_rel',  # relation table
        'config_rev_id', 'accout_rev_id',
        string="Revenue Acounts", # Stock Valuation Journal, Revenue Acounts
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    )      

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        cost_account_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.cost_account_ids')
        cost_journal_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.cost_journal_ids')
        revenue_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.revenue_ids')
        cra = False
        rj=False
        ra=False
        if cost_account_ids:
            cra = [(6, 0, literal_eval(cost_account_ids))]
        if cost_journal_ids:
            rj = [(6, 0, literal_eval(cost_journal_ids))]
        if revenue_ids:
            ra = [(6, 0, literal_eval(revenue_ids))]

        res.update(
            cost_account_ids=cra,
            cost_journal_ids=rj,
            revenue_ids= ra,
        )
        return res

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.cost_account_ids', self.cost_account_ids.ids)
        self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.cost_journal_ids', self.cost_journal_ids.ids)
        self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.revenue_ids', self.revenue_ids.ids)
        return res

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
        config_parameter='prod_qnt_cost_tracing.cost_account_ids',
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    )
    cost_journal_ids = fields.Many2many(
        'account.journal',
        'res_config_settingstrace_cost_journa_rel',  # relation table
        'config_id', 'journal_id',
        string="Sales Journal", # Stock Valuation Journal, Revenue Acounts
        config_parameter='prod_qnt_cost_tracing.cost_journal_ids',
        # inventory valuation journal
    )
    revenue_ids = fields.Many2many(
        'account.account',
        'res_config_settingstrace_revenue_rel',  # relation table
        'config_rev_id', 'accout_rev_id',
        string="Revenue Acounts", # Stock Valuation Journal, Revenue Acounts
        config_parameter='prod_qnt_cost_tracing.revenue_ids',
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    ) 
    inventory_val_journal_ids = fields.Many2many(
        'account.journal',
        'res_config_settingstrace_inval_journal_rel',  # relation table
        'config_id', 'journal_id',
        string="Inventory Valuation Journal", # Stock Valuation Journal, Revenue Acounts
        config_parameter='prod_qnt_cost_tracing.inventory_val_journal_ids',
        # inventory valuation journal
    ) 
    clearance_ids = fields.Many2many(
        'account.account',
        'res_config_settingclearance_acc_rel',  # relation table
        'config_clearance_id', 'accout_clearance_id',
        string="clearance In Acounts", # Stock Valuation Journal, Revenue Acounts
        config_parameter='prod_qnt_cost_tracing.clearance_ids',
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    ) 
    clearance_out_ids = fields.Many2many(
        'account.account',
        'res_config_settingclearance_acc_ouy_rel',  # relation table
        'config_clearance_out_id', 'accout_clearance_out_id',
        string="clearance Out Acounts", # Stock Valuation Journal, Revenue Acounts
        config_parameter='prod_qnt_cost_tracing.clearance_out_ids',
        # config_parameter='sale.allowed_account_ids'  # store in ir.config_parameter
    ) 
    last_closing_year=fields.Date(string="Last Closing Date",
                                  config_parameter='prod_qnt_cost_tracing.last_closing_year',
                                 )

    # @api.model
    # def get_values(self):
    #     res = super(ResConfigSettings, self).get_values()
    #     cost_account_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.cost_account_ids')
    #     cost_journal_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.cost_journal_ids')
    #     revenue_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.revenue_ids')
    #     inventory_val_journal_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.inventory_val_journal_ids')
    #     clearance_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.clearance_ids')
    #     clearance_out_ids = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.clearance_out_ids')
    #     last_closing_year = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.last_closing_year')
    
    #     cra = False
    #     rj=False
    #     ra=False
    #     ivj=False
    #     clids=False
    #     cloutids=False
    #     lastCY=last_closing_year

    #     if cost_account_ids:
    #         cra = [(6, 0, literal_eval(cost_account_ids))]
    #     if cost_journal_ids:
    #         rj = [(6, 0, literal_eval(cost_journal_ids))]
    #     if revenue_ids:
    #         ra = [(6, 0, literal_eval(revenue_ids))]
    #     if inventory_val_journal_ids:
    #         ivj = [(6, 0, literal_eval(inventory_val_journal_ids))]
    #     if clearance_ids:
    #         clids = [(6, 0, literal_eval(clearance_ids))]
    #     if clearance_out_ids:
    #         cloutids = [(6, 0, literal_eval(clearance_out_ids))]

    #     res.update(
    #         cost_account_ids=cra,
    #         cost_journal_ids=rj,
    #         revenue_ids= ra,
    #         inventory_val_journal_ids= ivj,
    #         clearance_ids=clids,
    #         clearance_out_ids=cloutids,
    #         last_closing_year=lastCY,
    #     )
    #     return res

    # def set_values(self):
    #     res = super(ResConfigSettings, self).set_values()
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.cost_account_ids', self.cost_account_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.cost_journal_ids', self.cost_journal_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.revenue_ids', self.revenue_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.inventory_val_journal_ids', self.inventory_val_journal_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.clearance_ids', self.clearance_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.clearance_out_ids', self.clearance_out_ids.ids)
    #     self.env['ir.config_parameter'].sudo().set_param('prod_qnt_cost_tracing.last_closing_year', self.last_closing_year)
    #     return res

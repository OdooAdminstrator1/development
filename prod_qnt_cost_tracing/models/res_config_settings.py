from odoo import models, fields, api
from ast import literal_eval

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # 1. REMOVE config_parameter from all Many2many fields
    cost_account_ids = fields.Many2many(
        'account.account',
        'res_config_trace_conf_rel',
        'config_cost_id', 'account_cost_id',
        string="Cost of Revenue Accounts"
    )
    cost_journal_ids = fields.Many2many(
        'account.journal',
        'res_config_trace_cost_journa_rel',
        'config_id', 'journal_id',
        string="Sales Journal"
    )
    revenue_ids = fields.Many2many(
        'account.account',
        'res_config_trace_revenue_rel',
        'config_rev_id', 'account_rev_id',
        string="Revenue Accounts"
    ) 
    inventory_val_journal_ids = fields.Many2many(
        'account.journal',
        'res_config_trace_inval_journal_rel',
        'config_id', 'journal_id',
        string="Inventory Valuation Journal"
    ) 
    clearance_ids = fields.Many2many(
        'account.account',
        'res_config_trace_clearance_acc_rel',
        'config_clearance_id', 'account_clearance_id',
        string="Clearance In Accounts"
    ) 
    clearance_out_ids = fields.Many2many(
        'account.account',
        'res_config_trace_clearance_acc_out_rel',
        'config_clearance_out_id', 'account_clearance_out_id',
        string="Clearance Out Accounts"
    ) 
    
    # Dates/Booleans/Chars can keep config_parameter safely
    last_closing_year = fields.Date(
        string="Last Closing Date",
        config_parameter='prod_qnt_cost_tracing.last_closing_year'
    )

    # 2. MANUALLY load the values
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        
        # We store M2M IDs as a string like "[1, 2, 3]" and convert back to list
        res.update(
            cost_account_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.cost_account_ids', '[]')))],
            cost_journal_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.cost_journal_ids', '[]')))],
            revenue_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.revenue_ids', '[]')))],
            inventory_val_journal_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.inventory_val_journal_ids', '[]')))],
            clearance_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.clearance_ids', '[]')))],
            clearance_out_ids=[(6, 0, literal_eval(get_param('prod_qnt_cost_tracing.clearance_out_ids', '[]')))],
        )
        return res

    # 3. MANUALLY save the values
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        
        # Save the list of IDs as a string representation
        set_param('prod_qnt_cost_tracing.cost_account_ids', self.cost_account_ids.ids)
        set_param('prod_qnt_cost_tracing.cost_journal_ids', self.cost_journal_ids.ids)
        set_param('prod_qnt_cost_tracing.revenue_ids', self.revenue_ids.ids)
        set_param('prod_qnt_cost_tracing.inventory_val_journal_ids', self.inventory_val_journal_ids.ids)
        set_param('prod_qnt_cost_tracing.clearance_ids', self.clearance_ids.ids)
        set_param('prod_qnt_cost_tracing.clearance_out_ids', self.clearance_out_ids.ids)

from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"
    advance_account_payable_id = fields.Many2one(
        "account.account", 
        company_dependent=True,
        string="Vendor Advanced Account",
        domain="[('account_type', '=', 'asset_current'), ('deprecated', '=', False), ('advanced', '=', True)]",
        help="This account will be used instead of the default one as the payable account for the current partner"
    )

    advance_account_receivable_id = fields.Many2one(
        "account.account", 
        company_dependent=True,
        string="Customer Advanced Account",
        domain="[('account_type', '=', 'liability_current'), ('deprecated', '=', False), ('advanced', '=', True)]",
        help="This account will be used instead of the default one as the advance receivable account for the current partner"
    )





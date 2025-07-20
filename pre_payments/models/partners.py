from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

# class partners(models.Model):

#     _inherit = ["res.partner"]

#     property_advacc_payable_id = fields.Many2one("account.account", company_dependent=True,
#                                                   string="Vendor Advanced Account",
#                                                   domain="[('user_type_id', '=', 'Current Assets'), ('deprecated', '=', False)]",
#                                                   help="This account will be used for pre payments to vendors"
#                                                   )
#     property_advacc_receivable_id = fields.Many2one("account.account", company_dependent=True,
#                                                      string="Customer Advanced Account",
#                                                      domain="[('user_type_id', '=', 'Current Liabilities'), ('deprecated', '=', False) ]",
#                                                      help="This account will be used for pre payments of customers"
#                                                     )

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

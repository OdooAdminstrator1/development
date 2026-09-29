from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_commercial_registration = fields.Char(
        string='Commercial Registration', 
        tracking=True,
        help="Commercial Registration Number for the partner"
    )

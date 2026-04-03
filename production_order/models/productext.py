from odoo import api, fields, models, tools

class ProductProduct(models.Model):
    _inherit = 'product.product'
    estimation_code = fields.Char(string='Estimation code')


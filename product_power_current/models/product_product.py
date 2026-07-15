from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    power = fields.Float(string="Power")
    min_voltage = fields.Float(string="Min Voltage")
    max_voltage = fields.Float(string="Max Voltage")
    mincurrent = fields.Float(string="Min Current")
    maxcurrent = fields.Float(string="Max Current")

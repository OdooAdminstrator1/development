from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    power = fields.Float(
        string="Power"
    )

    current = fields.Float(
        string="Current"
    )
from odoo import fields, models, api


class IctOverheadStockValuationLayer (models.Model):
    _inherit = 'stock.valuation.layer'

    ict_overhead_processed_quantity = fields.Integer('Overhead Processed Quantity', default=0)
    



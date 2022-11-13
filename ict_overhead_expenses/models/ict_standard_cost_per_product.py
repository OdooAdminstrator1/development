from odoo import fields, models, api


class ICTStandardCostPerProduct (models.Model):
    _name = 'ict_overhead_expenses.ict_standard_cost_per_product'
    _description = 'Standard Cost Table'

    product_id = fields.Many2one('product.product', string='Finished Product')
    hours_to_produce = fields.Float('Total Hours to produce')
    percentage = fields.Float('Percentage')
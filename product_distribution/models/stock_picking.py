from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    open_date_id = fields.Many2one('distribution.open.date', string='Open Date')
    distributor_id = fields.Many2one(
        'hr.employee', 
        string='Distributor', 
        domain="[('isdistributor', '=', True)]"
    )

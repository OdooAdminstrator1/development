from odoo import models, fields, api
from odoo.exceptions import UserError


class StockPickingInheritedMoTrans(models.Model):
    _inherit = 'stock.picking'

    related_mo_id = fields.Many2one('mrp.production')

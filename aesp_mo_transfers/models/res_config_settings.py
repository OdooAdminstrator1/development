from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    picking_type_id = fields.Many2one('stock.picking.type',
                                      string='Manufacturing Transfer Operation Type',
                                      config_parameter='manufacturing.raw_material_operation_type',
                                      domain=[('code', '=', 'internal')])


from odoo import models, api, fields

class ProductionOrder(models.Model):
    _inherit = 'production.order'

    project_id = fields.Integer(
        string="Project ID", 
        copy=False, 
        help="Unique project identifier, defaults to record ID if empty."
    )

    _sql_constraints = [
        (
            'project_id_unique', 
            'unique(project_id)', 
            'The Project ID must be unique!'
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.project_id:
                record.project_id = record.id
        return records



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_location = fields.Char(string="Delivery Location")
    subject_of_delivery = fields.Char(string="Subject of Delivery")
    project_id = fields.Integer(
            related='sale_id.production_order_id.project_id',
            string='Project ID',
            store=True,
            readonly=True
        )


class StockMove(models.Model):
    _inherit = 'stock.move'

    pre_sales_code = fields.Char(
        string='Pre Sales Code',
        compute='_compute_pre_sales_code',
        store=True
    )

    serial_number = fields.Integer(
        string='No.',
        compute='_compute_serial_number',
        store=False
    )

    @api.depends('picking_id.move_ids_without_package', 'picking_id.move_ids_without_package.sequence')
    def _compute_serial_number(self):
        for move in self:
            if move.picking_id:
                # Sort moves by sequence or ID to maintain consistent numbering
                moves = move.picking_id.move_ids_without_package.sorted(lambda m: (m.sequence, m.id))
                try:
                    move.serial_number = list(moves).index(move) + 1
                except ValueError:
                    move.serial_number = 1
            else:
                move.serial_number = 1

    @api.depends('picking_id.sale_id.production_order_id', 'product_id')
    def _compute_pre_sales_code(self):
        for move in self:
            code = False
            production_order = move.picking_id.sale_id.production_order_id
            if production_order and move.product_id:
                material = self.env['production.order.materials'].search([
                    ('production_order_id', '=', production_order.id),
                    ('product_id', '=', move.product_id.id)
                ], limit=1)
                if material:
                    code = material.name
            move.pre_sales_code = code
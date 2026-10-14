
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

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_product_quantities(self, **kwargs):
        aggregated_lines = super()._get_aggregated_product_quantities(
            **kwargs
        )

        seen_moves = {}

        for move_line in self:
            if (
                kwargs.get("except_package")
                and move_line.result_package_id
            ):
                continue

            properties = self._get_aggregated_properties(
                move_line=move_line
            )
            key = properties["line_key"]

            if key not in aggregated_lines:
                continue

            move = move_line.move_id
            if not move:
                continue

            seen = seen_moves.setdefault(key, set())

            # One entry per stock.move, even when it has multiple move lines.
            if move.id in seen:
                continue

            seen.add(move.id)


            aggregated_lines[key].setdefault(
                "custom_move_values", []
            ).append({
                "move": move,
                "pre_sales_code": move.pre_sales_code or "",
                "serial_number": (
                    str(move.serial_number)
                    if move.serial_number is not False
                    else ""
                ),
            })

        # Also handle aggregated rows that have no corresponding
        # move line in the current recordset.
        for line in aggregated_lines.values():
            if "custom_move_values" not in line:
                move = line.get("move")
        
                line["custom_move_values"] = (
                    [{
                        "move": move,
                        "pre_sales_code": move.pre_sales_code or "",
                        "serial_number": (
                            str(move.serial_number)
                            if move.serial_number is not False
                            else ""
                        ),
                    }]
                    if move
                    else []
                )

        return aggregated_lines


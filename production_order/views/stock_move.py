from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    component_available_qty = fields.Float(
        string="Available",
        compute="_compute_component_available_qty",
        digits="Product Unit of Measure",
    )

    @api.depends(
        "product_id",
        "location_id",
        "company_id",
    )
    def _compute_component_available_qty(self):
        for move in self:
            if not move.product_id:
                move.component_available_qty = 0.0
                continue

            move.component_available_qty = move.product_id.with_context(
                location=move.location_id.id,
                company_id=move.company_id.id,
            ).free_qty

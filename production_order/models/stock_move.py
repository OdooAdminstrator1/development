from collections import defaultdict

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    other_locations = fields.Char(
        string="Other Locations",
        compute="_compute_other_locations",
    )

    @api.depends(
        "product_id",
        "location_id",
        "forecast_availability",
        "product_uom_qty",
    )
    def _compute_other_locations(self):

        Quant = self.env["stock.quant"]

        for move in self:

            move.other_locations = False

            if (
                not move.product_id
                or move.state in ("done", "cancel")
            ):
                continue

            # Only show when there is a shortage
            if move.forecast_availability >= move.product_uom_qty:
                continue

            quants = Quant.search([
                ("product_id", "=", move.product_id.id),
                ("location_id", "!=", move.location_id.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0),
            ])

            grouped = defaultdict(float)

            for q in quants:
                qty = q.available_quantity
                if qty > 0:
                    grouped[q.location_id.display_name] += qty

            if grouped:
                move.other_locations = ", ".join(
                    "%s : %g" % (loc, qty)
                    for loc, qty in grouped.items()
                )

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    other_locations_qty = fields.Float(
        compute="_compute_other_locations",
        digits="Product Unit of Measure",
    )

    other_locations_status = fields.Selection(
        [
            ("none", "Unavailable"),
            ("partial", "Partial"),
            ("enough", "Enough"),
        ],
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

            # move.other_locations_qty = 0
            # move.other_locations_status = "none"

            # if (
            #     not move.product_id
            #     or move.state in ("done", "cancel")
            #     or move.forecast_availability >= move.product_uom_qty
            # ):
            #     continue

            # quants = Quant.search([
            #     ("product_id", "=", move.product_id.id),
            #  #   ("location_id", "!=", move.location_id.id),
            #    ("location_id.usage", "=", "internal"),
            #     ("inventory_quantity_auto_apply", ">", 0),
            #   #  ("available_quantity", ">", 0),inventory_quantity_auto_apply
            # ])

            # qty = sum(quants.mapped("inventory_quantity_auto_apply"))
         #   qty = sum(quants.mapped("available_quantity"))
            #            move.other_locations_qty = qty
            product = self.env['product.product'].browse(move.product_id.id)
            qty_on_hand = product.qty_available
            qty_on_hand_location =self.env['stock.quant']._get_available_quantity( product,    move.location_id.id)
            qty =qty_on_hand-qty_on_hand_location
            move.other_locations_qty =qty


            if qty == 0:
                move.other_locations_status = "none"
            elif qty >= move.product_uom_qty:
                move.other_locations_status = "enough"
            else:
                move.other_locations_status = "partial"


# from collections import defaultdict

# from odoo import api, fields, models


# class StockMove(models.Model):
#     _inherit = "stock.move"

#     other_locations = fields.Char(
#         string="Other Locations",
#         compute="_compute_other_locations",
#     )

#     @api.depends(
#         "product_id",
#         "location_id",
#         "forecast_availability",
#         "product_uom_qty",
#     )
#     def _compute_other_locations(self):

#         Quant = self.env["stock.quant"]

#         for move in self:

#             move.other_locations = False

#             if (
#                 not move.product_id
#                 or move.state in ("done", "cancel")
#             ):
#                 continue

#             # Only show when there is a shortage
#             if move.forecast_availability >= move.product_uom_qty:
#                 continue

#             quants = Quant.search([
#                 ("product_id", "=", move.product_id.id),
#                 ("location_id", "!=", move.location_id.id),
#                 ("location_id.usage", "=", "internal"),
#                 ("quantity", ">", 0),
#             ])

#             grouped = defaultdict(float)

#             for q in quants:
#                 qty = q.available_quantity
#                 if qty > 0:
#                     grouped[q.location_id.display_name] += qty

#             if grouped:
#                 move.other_locations = ", ".join(
#                     "%s : %g" % (loc, qty)
#                     for loc, qty in grouped.items()
#                 )

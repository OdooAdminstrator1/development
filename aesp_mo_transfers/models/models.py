# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class aesp_mo_transfers(models.Model):
    _inherit = 'mrp.production'

    def action_create_transfer(self):
        pick_type_id = self.env['ir.config_parameter'].sudo().get_param('manufacturing.raw_material_operation_type')
        if not pick_type_id:
            raise UserError("Please Define Raw Material Operation Type In Setting Before")
        for rec in self:
            move_lines = []
            product_ids_arr = []
            if rec.state not in ['draft', 'confirmed']:
                raise UserError("Only Draft/Confirmed Mo")
            for move in rec.move_raw_ids:
                if 'Manufacture' not in [v.name for v in
                                         move.product_tmpl_id.route_ids] and move.product_id.categ_id.property_cost_method != 'standard':
                    move_product_uom_qty = sum(move_raw.product_uom_qty for move_raw in
                                               self.move_raw_ids.filtered(
                                                   lambda l: l.product_id.id == move.product_id.id)
                                               )

                    qty = move_product_uom_qty
                    if qty > 0:
                        product_ids_arr.append(move.product_id.id)
                        move_line = {"product_id": move.product_id.id, "product_uom": move.product_uom.id,
                                     "product_uom_qty": qty, "name": move.name,
                                     "company_id": move.company_id.id,
                                     "location_id": pick_type_id.default_location_src_id.id,
                                     "location_dest_id": pick_type_id.default_location_dest_id.id,
                                     "production_id": rec.id,
                                     'group_id': rec.procurement_group_id.id,
                                     }
                        move_lines.append(move_line)
            if len(move_lines) == 0:
                raise UserError("You have no lines to order")

            vals = [{'picking_type_id': pick_type_id.id,
                     'location_id': pick_type_id.default_location_src_id.id,
                     'location_dest_id': pick_type_id.default_location_dest_id.id,
                     'origin': rec.name,
                     'group_id': rec.procurement_group_id.id,
                     'move_ids_without_package': move_lines,
                     }]
            picking = self.env['stock.picking'].create(vals)

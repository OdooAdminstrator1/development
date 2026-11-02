from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    manual_delivery_id = fields.Many2many('stock.picking',
        string='Source Delivery',
        domain="[('state', '=', 'done'), ('picking_type_id.code', '=', 'outgoing'), ('sale_id', '=', False)]",
        copy=False,
        help="Select an existing unlinked outgoing delivery to populate this quotation."
    )

    # Helper Many2one field to trigger the onchange reliably
    add_delivery_id = fields.Many2one(
        'stock.picking',
        string='Add Delivery Transfer',
        domain="[('state', 'not in', ('done', 'cancel')), ('picking_type_id.code', '=', 'outgoing'), ('sale_id', '=', False)]",
        copy=False,
        help="Select a delivery to merge its products into this quotation."
    )

    @api.onchange('add_delivery_id')
    def _onchange_add_delivery_id(self):
        if not self.add_delivery_id:
            return
        
        picking = self.add_delivery_id

        # Prevent duplicate selection
        if picking in self.manual_delivery_ids:
            self.add_delivery_id = False
            return

        # Add picking to the many2many list
        self.manual_delivery_ids = [(4, picking.id)] + [(4, p.id) for p in self.manual_delivery_ids]

        # 1. Auto-fill Partner from the first delivery if partner is empty
        if not self.partner_id and picking.partner_id:
            self.partner_id = picking.partner_id

        # 2. Gather existing order lines into a dictionary for merging
        delivery_products = {}
        for line in self.order_line:
            delivery_products[line.product_id] = {
                'qty': line.product_uom_qty,
                'uom': line.product_uom,
                'name': line.name,
            }

        # 3. Merge new delivery moves (update quantities if product already exists)
        for move in picking.move_ids_without_package:
            prod = move.product_id
            if prod not in delivery_products:
                delivery_products[prod] = {
                    'qty': 0.0,
                    'uom': move.product_uom,
                    'name': move.name or prod.display_name,
                }
            delivery_products[prod]['qty'] += move.product_uom_qty

        # 4. Rebuild the order lines command list
        commands = [(5, 0, 0)]
        for prod, data in delivery_products.items():
            commands.append((0, 0, {
                'product_id': prod.id,
                'product_uom_qty': data['qty'],
                'product_uom': data['uom'].id,
                'name': data['name'],
            }))
        
        self.order_line = commands

        # 5. Reset helper field so it's ready for the next selection
        self.add_delivery_id = False

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self.filtered(lambda o: o.manual_delivery_ids):
            for picking in order.manual_delivery_ids:
                picking.sale_id = order.id
                
                if not picking.group_id and order.procurement_group_id:
                    picking.group_id = order.procurement_group_id
                elif picking.group_id and not order.procurement_group_id:
                    order.procurement_group_id = picking.group_id
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        lines_without_manual = self.filtered(lambda l: not l.order_id.manual_delivery_ids)
        lines_with_manual = self - lines_without_manual
        
        res = super(SaleOrderLine, lines_without_manual)._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        
        for line in lines_with_manual:
            order = line.order_id
            moves = order.manual_delivery_ids.mapped('move_ids_without_package').filtered(
                lambda m: m.product_id == line.product_id and not m.sale_line_id
            )
            for move in moves:
                move.sale_line_id = line.id
                    
        return res

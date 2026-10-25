from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    manual_delivery_id = fields.Many2one(
        'stock.picking',
        string='Source Delivery',
        domain="[('state', '=', 'done'), ('picking_type_id.code', '=', 'outgoing'), ('sale_id', '=', False)]",
        copy=False,
        help="Select an existing unlinked outgoing delivery to populate this quotation."
    )

    @api.onchange('manual_delivery_id')
    def _onchange_manual_delivery_id(self):
        if not self.manual_delivery_id:
            return
        
        picking = self.manual_delivery_id
        
        # 1. Auto-fill Partner/Customer
        if picking.partner_id:
            self.partner_id = picking.partner_id
            self.production_order_id = picking.production_order_id.id

        # 2. Clear existing lines and populate from delivery stock moves
        lines = []
        for move in picking.move_ids_without_package:
            lines.append((0, 0, {
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'product_uom': move.product_uom.id,
                'name': move.name or move.product_id.display_name,
            }))
        
        self.order_line = [(5, 0, 0)] + lines

    def _action_confirm(self):
        res = super()._action_confirm()
        # Bind the pre-existing manual delivery to the confirmed sale order
        for order in self.filtered('manual_delivery_id'):
            picking = order.manual_delivery_id
            picking.sale_id = order.id
            
            # Align procurement groups if necessary
            if not picking.group_id and order.procurement_group_id:
                picking.group_id = order.procurement_group_id
            elif picking.group_id and not order.procurement_group_id:
                order.procurement_group_id = picking.group_id
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Override to prevent stock rules from creating a new delivery 
        for lines associated with a manual delivery."""
        
        # Separate lines that belong to orders with a manual delivery
        lines_without_manual = self.filtered(lambda l: not l.order_id.manual_delivery_id)
        lines_with_manual = self - lines_without_manual
        
        # Let Odoo process normal lines normally
        res = super(SaleOrderLine, lines_without_manual)._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        
        # For manual delivery lines, skip rule launch and map existing moves instead
        for line in lines_with_manual:
            order = line.order_id
            picking = order.manual_delivery_id
            
            # Find the matching stock move in the pre-existing delivery and link it
            move = picking.move_ids_without_package.filtered(
                lambda m: m.product_id == line.product_id and not m.sale_line_id
            )
            if move:
                move[0].sale_line_id = line.id
                
        return res


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

        # 2. Clear existing lines and populate from delivery stock moves
        lines = []
        for move in picking.move_ids_without_package:
            lines.append((0, 0, {
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'product_uom': move.product_uom.id,
                'name': move.name or move.product_id.display_name,
            }))
        
        # (5, 0, 0) clears existing lines in the draft
        self.order_line = [(5, 0, 0)] + lines

    def _create_picking(self):
        """Override to prevent auto-creating a new delivery draft if a manual delivery is already linked,
        and bind the selected manual delivery to the confirmed sale order."""
        orders_with_manual = self.filtered('manual_delivery_id')
        orders_without_manual = self - orders_with_manual
        
        # Let Odoo handle normal orders normally
        res = super(SaleOrder, orders_without_manual)._create_picking()
        
        # Handle orders with a pre-selected manual delivery
        for order in orders_with_manual:
            picking = order.manual_delivery_id
            
            # Bind picking to the sale order
            picking.sale_id = order.id
            
            # Ensure procurement group alignment
            if not picking.group_id and order.procurement_group_id:
                picking.group_id = order.procurement_group_id
            elif picking.group_id and not order.procurement_group_id:
                order.procurement_group_id = picking.group_id
            
            # Link existing stock moves to the newly created sale order lines
            for move in picking.move_ids_without_package:
                line = order.order_line.filtered(lambda l: l.product_id == move.product_id and not l.sale_line_id)
                if line:
                    move.sale_line_id = line[0].id
                    
        return res

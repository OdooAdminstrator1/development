from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    manual_delivery_ids = fields.Many2many(
        comodel_name='stock.picking',
        relation='sale_order_manual_delivery_rel',
        column1='order_id',
        column2='picking_id',
        string='Source Deliveries',
        copy=False,
        domain="[('partner_id', '=', partner_id),"
               " ('state', '=', 'done'),"
               " ('picking_type_id.code', '=', 'outgoing'),"
               " ('sale_id', '=', False)]",
        help="Done outgoing deliveries of this customer that are not linked to "
             "any sale order yet. Their products are merged into the order "
             "lines, and they are bound to this order on confirmation instead "
             "of a new delivery being created.",
    )

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('partner_id')
    def _onchange_partner_id_manual_deliveries(self):
        """Drop selected deliveries that no longer belong to the new customer."""
        if not self.manual_delivery_ids:
            return
        partner = self.partner_id._origin
        selected = self.manual_delivery_ids._origin
        kept = selected.filtered(lambda p: p.partner_id == partner)
        if kept != selected:
            self.manual_delivery_ids = [Command.set(kept.ids)]
            self._onchange_manual_delivery_ids()

    @api.onchange('manual_delivery_ids')
    def _onchange_manual_delivery_ids(self):
        """Rebuild order lines from the selected deliveries, merging products."""
        pickings = self.manual_delivery_ids._origin

        # A. Empty selection -> reset lines
        if not pickings:
            self.order_line = [Command.clear()]
            return

        # B. Aggregate done quantities per product, in the product's base UoM
        aggregated = {}  # product.id -> {'product': record, 'qty': float}
        for picking in pickings:
            for move in picking.move_ids_without_package:
                if move.state != 'done' or not move.product_id:
                    continue
                product = move.product_id
                qty = move.product_uom._compute_quantity(move.quantity, product.uom_id)
                if product.id in aggregated:
                    aggregated[product.id]['qty'] += qty
                else:
                    aggregated[product.id] = {'product': product, 'qty': qty}

        # C. Rebuild lines. Description, price, taxes, etc. are filled by the
        #    standard sale.order.line computes triggered by product_id.
        commands = [Command.clear()]
        for data in aggregated.values():
            product = data['product']
            commands.append(Command.create({
                'product_id': product.id,
                'product_uom_qty': data['qty'],
                'product_uom': product.uom_id.id,
            }))
        self.order_line = commands

    # -------------------------------------------------------------------------
    # Confirmation
    # -------------------------------------------------------------------------

    def _action_confirm(self):
        self._check_manual_deliveries()
        # sale_stock's _action_confirm launches stock rules; lines of orders
        # with manual deliveries are skipped in sale.order.line.
        res = super()._action_confirm()
        for order in self.filtered('manual_delivery_ids'):
            order._bind_manual_deliveries()
        return res

    def _check_manual_deliveries(self):
        """Re-validate the selection: it may have changed since it was made
        (e.g. another quotation confirmed with the same delivery)."""
        for order in self.filtered('manual_delivery_ids'):
            invalid = order.manual_delivery_ids.filtered(
                lambda p: p.state != 'done'
                or p.picking_type_id.code != 'outgoing'
                or p.partner_id != order.partner_id
                or p.company_id != order.company_id
                or (p.sale_id and p.sale_id != order)
            )
            if invalid:
                raise UserError(_(
                    "The following deliveries can no longer be used for %(order)s "
                    "(not done, not outgoing, another customer/company, or already "
                    "linked to a sale order): %(pickings)s",
                    order=order.name,
                    pickings=", ".join(invalid.mapped('name')),
                ))

    def _bind_manual_deliveries(self):
        self.ensure_one()
        pickings = self.manual_delivery_ids.sudo()
        moves = pickings.move_ids_without_package

        # 1. Procurement group: the stock rule was skipped, so none was created.
        group = self.procurement_group_id.sudo()
        if not group:
            group = self.env['procurement.group'].sudo().create({
                'name': self.name,
                'move_type': self.picking_policy,
                'sale_id': self.id,
                'partner_id': self.partner_shipping_id.id,
            })
            self.procurement_group_id = group
        elif not group.sale_id:
            group.sale_id = self

        # 2. Align groups on the moves first. stock.picking.group_id is a
        #    stored related on move_ids.group_id, and picking.sale_id is a
        #    related on group_id.sale_id, so this is what makes the binding stick.
        moves.write({'group_id': group.id})

        # 3. Link moves to the order lines (merged by product).
        line_by_product = {}
        for line in self.order_line.filtered(lambda l: not l.display_type and l.product_id):
            line_by_product.setdefault(line.product_id.id, line)

        for line in line_by_product.values():
            moves.filtered(lambda m: m.product_id == line.product_id).write(
                {'sale_line_id': line.id})
        unmatched = moves.filtered(
            lambda m: m.product_id.id not in line_by_product).product_id

        # 4. Bind pickings (explicit write, consistent with the group above).
        pickings.write({'sale_id': self.id})
        for picking in pickings.filtered(lambda p: not p.origin):
            picking.origin = self.name

        # 5. Trace in chatter
        body = _("Linked existing deliveries: %s", ", ".join(pickings.mapped('name')))
        if unmatched:
            body += " " + _(
                "Products delivered but not on the order (moves left unlinked): %s",
                ", ".join(unmatched.mapped('display_name')),
            )
        self.message_post(body=body)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, *args, **kwargs):
        """Skip procurement (and thus delivery creation) for lines of orders
        built from pre-existing done deliveries."""
        regular_lines = self.filtered(lambda line: not line.order_id.manual_delivery_ids)
        return super(SaleOrderLine, regular_lines)._action_launch_stock_rule(*args, **kwargs)


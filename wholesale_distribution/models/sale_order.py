from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_distribution_order = fields.Boolean(
        string="Distribution Order", default=False, copy=False, index=True,
    )
    is_distribution_master_order = fields.Boolean(
        string="General Order", default=False, copy=False, index=True,
        help="Aggregated end-of-day master order produced by batching distribution runs.",
    )
    delivery_run_id = fields.Many2one(
        'distribution.delivery.run', string="Delivery Run", copy=False, index=True,
    )

    # --- Distribution buffer figures, shown only to distributors / managers. ---
    distribution_payment_ids = fields.One2many(
        'distribution.payment', 'sale_order_id', string="Temporary Payments",
    )
    distribution_payment_count = fields.Integer(compute='_compute_distribution_payment_totals')
    distribution_paid = fields.Monetary(
        string="Collected", compute='_compute_distribution_payment_totals',
        currency_field='currency_id',
    )
    distribution_validated = fields.Monetary(
        string="Validated", compute='_compute_distribution_payment_totals',
        currency_field='currency_id',
    )
    distribution_rest = fields.Monetary(
        string="Remaining", compute='_compute_distribution_payment_totals',
        currency_field='currency_id',
    )

    @api.depends(
        'distribution_payment_ids.amount', 'distribution_payment_ids.state',
        'amount_total',
    )
    def _compute_distribution_payment_totals(self):
        for order in self:
            payments = order.distribution_payment_ids
            paid = sum(payments.filtered(lambda p: p.state == 'collected').mapped('amount'))
            validated = sum(payments.filtered(lambda p: p.state == 'validated').mapped('amount'))
            order.distribution_paid = paid
            order.distribution_validated = validated
            order.distribution_rest = order.amount_total - paid - validated
            order.distribution_payment_count = len(payments)

    # ------------------------------------------------------------------ #
    # Visibility: keep distribution orders out of the standard Sales app
    # ------------------------------------------------------------------ #
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Hide distribution orders from the standard Sales app.
        """
        if not self.env.context.get('is_distribution') and not self._domain_targets_ids(domain):
            domain = list(domain) + [('is_distribution_order', '=', False)]
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @staticmethod
    def _domain_targets_ids(domain):
        """True if the domain explicitly constrains 'id' (read/fetch by id)."""
        for leaf in domain or []:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'id':
                return True
        return False

    # ------------------------------------------------------------------ #
    # Dedicated sequence for distribution orders
    # ------------------------------------------------------------------ #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_distribution_order'):
                # Bypass the standard sale.order sequence with the distribution one.
                if not vals.get('name') or vals['name'] == _('New'):
                    vals['name'] = self.env['ir.sequence'].next_by_code(
                        'distribution.sale.order') or _('New')
                # Salesperson is always the run's distributor.
                run_id = vals.get('delivery_run_id')
                if run_id:
                    run = self.env['distribution.delivery.run'].browse(run_id)
                    if run.user_id:
                        vals['user_id'] = run.user_id.id
        return super().create(vals_list)

    # ------------------------------------------------------------------ #
    # Defensive invoice prevention
    # ------------------------------------------------------------------ #
    def _create_invoices(self, grouped=False, final=False, date=None):
        """Distribution orders are never invoiced individually; the clean ledger is
        produced by the single aggregated master order. Drop them from any invoicing
        request instead of letting an account.move be generated and reversed later."""
        invoiceable = self.filtered(lambda o: not o.is_distribution_order)
        if not invoiceable:
            return self.env['account.move']
        return super(SaleOrder, invoiceable)._create_invoices(
            grouped=grouped, final=final, date=date)

    # ------------------------------------------------------------------ #
    # Smart button: temporary payments
    # ------------------------------------------------------------------ #
    def action_view_distribution_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Payments"),
            'res_model': 'distribution.payment',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_sale_order_id': self.id,
                'default_delivery_run_id': self.delivery_run_id.id,
            },
        }

    def action_add_distribution_payment(self):
        """Open a new temporary payment pre-filled for this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Add Payment"),
            'res_model': 'distribution.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_delivery_run_id': self.delivery_run_id.id,
                'default_amount': self.distribution_rest,
            },
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Defensive override.

        Instead of generating pickings for a distribution order and deleting them
        afterwards, we prevent the stock-rule execution path entirely for those
        lines. Distribution inventory is handled by the explicit run pipeline
        (Charge / Run close / Master order delivery) -- never by sale-order delivery.
        All native pricing, tax and multi-currency logic is left untouched because
        it runs elsewhere in the confirmation flow.
        """
        # The mobile API also passes an explicit {'is_distribution': True} context switch;
        # honour it as an additional guard on top of the persistent order flag.
        if self.env.context.get('is_distribution'):
            return True
        standard_lines = self.filtered(lambda line: not line.order_id.is_distribution_order)
        if not standard_lines:
            return True
        return super(SaleOrderLine, standard_lines)._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty)

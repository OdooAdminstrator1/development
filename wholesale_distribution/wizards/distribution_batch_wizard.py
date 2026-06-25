from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class DistributionBatchWizard(models.TransientModel):
    _name = 'distribution.batch.wizard'
    _description = 'End-of-Day Distribution Aggregation Wizard'

    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company,
    )
    run_filter = fields.Selection(
        selection=[
            ('all', 'All Runs'),
            ('truck', 'Truck Outlets Only'),
            ('shop', 'Shop Outlets Only'),
        ],
        string="Runs", default='all', required=True,
    )
    excluded_run_ids = fields.Many2many(
        'distribution.delivery.run',
        'distribution_batch_excluded_rel', 'wizard_id', 'run_id',
        string="Exclude Runs",
        domain="[('state', '!=', 'open'), ('master_order_id', '=', False),"
               " ('company_id', '=', company_id)]",
        help="Eligible runs to leave out of this batch.",
    )
    run_ids = fields.Many2many(
        'distribution.delivery.run',
        'distribution_batch_run_rel', 'wizard_id', 'run_id',
        string="Runs to Batch", compute='_compute_run_ids',
        help="Runs that will be aggregated, derived from the filter minus the excluded ones.",
    )

    def _eligible_domain(self):
        # Only non-open (i.e. closed) runs are batchable: their stock has already been
        # moved to the delivery location at run close. Open runs are excluded.
        self.ensure_one()
        return [
            ('state', '!=', 'open'),
            ('master_order_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ]

    @api.depends('run_filter', 'excluded_run_ids', 'company_id')
    def _compute_run_ids(self):
        for wizard in self:
            domain = wizard._eligible_domain()
            if wizard.run_filter in ('truck', 'shop'):
                domain.append(('outlet_id.distribution_type', '=', wizard.run_filter))
            runs = self.env['distribution.delivery.run'].search(domain)
            wizard.run_ids = runs - wizard.excluded_run_ids

    # ------------------------------------------------------------------ #
    def _get_config_record(self, param_key, model_name):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'wholesale_distribution.%s' % param_key)
        record = self.env[model_name].browse(int(value)) if value else self.env[model_name]
        if not record.exists():
            raise UserError(_(
                "The Wholesale Distribution settings are incomplete: '%s' is not configured.",
                param_key))
        return record

    def action_generate_master_order(self):
        self.ensure_one()
        runs = self.run_ids
        if not runs:
            raise UserError(_("There are no eligible delivery runs to batch."))

        general_customer = self._get_config_record(
            'default_general_customer_id', 'res.partner')
        # Goods are already sitting in the delivery location (moved there at run close).
        delivery_location = self._get_config_record(
            'default_delevery_location_id', 'stock.location')

        # 1. Aggregate sold products/quantities across all targeted distribution orders.
        orders = runs.sale_order_ids.filtered(
            lambda o: o.is_distribution_order and o.state == 'sale')
        if not orders:
            raise UserError(_("The selected runs have no confirmed distribution orders."))

        grouped = self.env['sale.order.line']._read_group(
            domain=[
                ('order_id', 'in', orders.ids),
                ('display_type', '=', False),
                ('product_id', '!=', False),
            ],
            groupby=['product_id'],
            aggregates=['product_uom_qty:sum'],
        )
        product_qty = {product: qty for product, qty in grouped if product.is_storable}
        if not product_qty:
            raise UserError(_("No storable products to aggregate in the selected runs."))

        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_("No warehouse found for company %s.", self.company_id.display_name))

        # 2. Create ONE master sale order using the STANDARD sequence.
        order_lines = [
            Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
            })
            for product, qty in product_qty.items()
        ]
        master_order = self.env['sale.order'].create({
            'partner_id': general_customer.id,
            'is_distribution_order': False,
            'is_distribution_master_order': True,
            'warehouse_id': warehouse.id,
            'order_line': order_lines,
        })

        # 3. Confirm -> Odoo natively generates the delivery; retarget it to ship
        #    from the delivery location where the run-close transfers deposited the goods.
        master_order.action_confirm()
        self._retarget_delivery_source(master_order, delivery_location)

        # 4. Single clean master invoice.
        invoice = master_order._create_invoices()

        invoice.action_post()

        # 5. Reconcile the runs' accounting payments against the master invoice.
        self._reconcile_run_payments(runs, master_order, invoice)

        # Link the runs to their master order (marks them as batched).
        runs.write({'master_order_id': master_order.id})

        return {
            'type': 'ir.actions.act_window',
            'name': _("Master Order"),
            'res_model': 'sale.order',
            'res_id': master_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------ #
    def _retarget_delivery_source(self, master_order, delivery_location):
        """Force the master order's outgoing delivery to ship from the delivery
        location where the run-close transfers deposited the goods (rather than
        the default warehouse stock)."""
        outgoing = master_order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state not in ('done', 'cancel'))
        for picking in outgoing:
            picking.move_ids.write({'location_id': delivery_location.id})
            picking.write({'location_id': delivery_location.id})
            picking.action_assign()

    def _reconcile_run_payments(self, runs, master_order, invoice):
        """Match the runs' close-time accounting payments against the master invoice.

        A posted customer payment books its counterpart on the *payment partner's*
        receivable account (here the distributer). For each such line we:
          * reconcile it with the master invoice's receivable line via the native
            outstanding-payment mechanism (which only pairs same-account lines), and
          * link the payment onto the invoice so it surfaces in
            ``reconciled_payment_ids`` (backed by the stored ``matched_payment_ids``).
        """
        invoice.ensure_one()
        # Posted payments in 'in_process'/'paid' (v19 has no 'posted' payment state)
        # that are NOT already attached to a master order.
        payments = runs.account_payment_ids.filtered(
            lambda p: p.state in ('in_process', 'paid')
            and p.move_id.state == 'posted'
            and not p.distribution_master_order_id)
        if not payments:
            return

        invoice_accounts = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
            and not line.reconciled).account_id
        if not invoice_accounts:
            return

        reconciled = self.env['account.payment']
        for payment in payments:
            pay_lines = payment.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and not line.reconciled
                and line.account_id in invoice_accounts)
            if not pay_lines:
                continue
            for line in pay_lines:
                invoice.js_assign_outstanding_line(line.id)
            reconciled |= payment

        if not reconciled:
            # Loud failure instead of a silently unpaid invoice: the payments are booked
            # on a receivable account the master invoice never touches (typically the
            # distributer resolves to a different receivable account than the customer).
            raise UserError(_(
                "None of the run payments could be matched to the master invoice: they "
                "are booked on receivable account(s) %(pay)s while the invoice uses "
                "%(inv)s. Align the distributer's and the general customer's receivable "
                "account so the payment can settle the invoice.",
                pay=", ".join(payments.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                ).account_id.mapped('display_name')),
                inv=", ".join(invoice_accounts.mapped('display_name'))))

        # Surface the payments on the invoice (reconciled_payment_ids unions this m2m).
        invoice.matched_payment_ids = [Command.link(p.id) for p in reconciled]
        reconciled.write({'distribution_master_order_id': master_order.id})

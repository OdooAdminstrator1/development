from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_compare, float_is_zero


class DistributionDeliveryRun(models.Model):
    _name = 'distribution.delivery.run'
    _description = 'Distribution Delivery Run'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'),
    )
    user_id = fields.Many2one(
        'res.users', string="Distributor", required=True, tracking=True,
        default=lambda self: self.env.user,
        help="Odoo user the run is operated under. For mobile runs this is the single "
             "system integration user; the physical distributer is held in 'distributer_employee_id'.",
    )
    distributer_employee_id = fields.Many2one(
        'hr.employee', string="Distributer (Employee)", tracking=True,
        domain="[('department_id', '=', distribution_department_id)]",
        help="Physical field distributer running this route. Distributers do not own an Odoo "
             "user account; they are identified by their employee record via the mobile API.",
    )
    distribution_department_id = fields.Many2one(
        'hr.department', compute='_compute_distribution_department_id',
        help="The Distribution department; used to filter the distributer field.",
    )
    outlet_id = fields.Many2one(
        'distribution.outlet', string="Outlet", required=True, tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string="Currency", readonly=True,
    )

    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('partial_closed', 'Partially Closed'),
            ('requires_validate', 'Requires Validate'),
            ('closed', 'Closed'),
        ],
        string="Status", default='open', required=True, tracking=True, copy=False,
    )

    start_date = fields.Datetime(string="Start Date", default=fields.Datetime.now)
    end_date = fields.Datetime(string="End Date")

    sale_order_ids = fields.One2many(
        'sale.order', 'delivery_run_id', string="Distribution Orders",
        context={'is_distribution': True},
    )
    payment_ids = fields.One2many(
        'distribution.payment', 'delivery_run_id', string="Payments",
    )
    sale_order_count = fields.Integer(compute='_compute_counts')
    payment_count = fields.Integer(compute='_compute_counts')
    account_payment_count = fields.Integer(compute='_compute_counts')
    picking_count = fields.Integer(compute='_compute_counts')
    outlet_product_count = fields.Integer(
        string="Outlet Products", compute='_compute_outlet_product_count',
    )

    # Inventory / accounting traceability.
    charge_picking_id = fields.Many2one('stock.picking', string="Charge Transfer", copy=False)
    discharge_picking_id = fields.Many2one('stock.picking', string="Discharge Transfer", copy=False)
    close_picking_id = fields.Many2one('stock.picking', string="Run Close Transfer", copy=False)
    account_payment_ids = fields.One2many(
        'account.payment', 'delivery_run_id', string="Accounting Payments",
    )

    # Master order batching tracking.
    master_order_id = fields.Many2one(
        'sale.order', string="Master Order", copy=False,
        help="Aggregated master sale order this run was batched into.",
    )
    is_batched = fields.Boolean(compute='_compute_is_batched', store=True)

    # ---- Computed monetary totals (manager / distributor only via views) ----
    total_sale_orders = fields.Monetary(
        string="Sales Total", compute='_compute_totals', currency_field='currency_id',
    )
    total_paid = fields.Monetary(
        string="Collected", compute='_compute_totals', currency_field='currency_id',
    )
    total_validated = fields.Monetary(
        string="Validated", compute='_compute_totals', currency_field='currency_id',
    )
    total_rest = fields.Monetary(
        string="Remaining", compute='_compute_totals', currency_field='currency_id',
    )
    margin_formula_total = fields.Monetary(
        string="Reconciliation Check", compute='_compute_totals', currency_field='currency_id',
        help="total_sale_orders - total_paid - total_rest - total_validated. "
             "Should always be zero; a non-zero value flags a data inconsistency.",
    )

    # Cashier physically counted intake captured at closing time.
    cashier_counted_amount = fields.Monetary(
        string="Cashier Counted Amount", currency_field='currency_id', copy=False,
        help="Physical cash counted by the cashier. Must match the collected temporary "
             "payments before the run can be closed.",
    )


    # ------------------------------------------------------------------ #
    # Compute methods
    # ------------------------------------------------------------------ #
    @api.depends('master_order_id')
    def _compute_is_batched(self):
        for run in self:
            run.is_batched = bool(run.master_order_id)

    @api.depends_context('uid')
    def _compute_distribution_department_id(self):
        department = self.env.ref(
            'wholesale_distribution.department_distribution', raise_if_not_found=False)
        for run in self:
            run.distribution_department_id = department.id if department else False

    @api.depends(
        'sale_order_ids', 'payment_ids', 'account_payment_ids',
        'charge_picking_id', 'discharge_picking_id', 'close_picking_id',
    )
    def _compute_counts(self):
        for run in self:
            run.sale_order_count = len(run.sale_order_ids)
            run.payment_count = len(run.payment_ids)
            run.account_payment_count = len(run.account_payment_ids)
            run.picking_count = len(run._get_run_pickings())

    def _get_run_pickings(self):
        """All inventory transfers produced by this run (charge / discharge / close)."""
        self.ensure_one()
        return (
            self.charge_picking_id
            | self.discharge_picking_id
            | self.close_picking_id
        )

    @api.depends('outlet_id.location_id')
    def _compute_outlet_product_count(self):
        Quant = self.env['stock.quant']
        for run in self:
            location = run.outlet_id.location_id
            if location:
                groups = Quant._read_group(
                    [('location_id', 'child_of', location.id), ('quantity', '!=', 0)],
                    groupby=['product_id'])
                run.outlet_product_count = len(groups)
            else:
                run.outlet_product_count = 0

    @api.depends(
        'sale_order_ids.amount_total',
        'payment_ids.amount', 'payment_ids.state',
    )
    def _compute_totals(self):
        for run in self:
            total_sale = sum(run.sale_order_ids.mapped('amount_total'))
            paid = sum(run.payment_ids.filtered(lambda p: p.state == 'collected').mapped('amount'))
            validated = sum(run.payment_ids.filtered(lambda p: p.state == 'validated').mapped('amount'))
            rest = total_sale - paid - validated
            run.total_sale_orders = total_sale
            run.total_paid = paid
            run.total_validated = validated
            run.total_rest = rest
            # By construction this collapses to zero; kept as an explicit invariant check.
            run.margin_formula_total = total_sale - paid - rest - validated

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'distribution.delivery.run') or _('New')
        return super().create(vals_list)

    @api.onchange('outlet_id')
    def _onchange_outlet_id(self):
        """Default the distributer from the selected outlet (user can override)."""
        if self.outlet_id.default_distributer_id:
            self.distributer_employee_id = self.outlet_id.default_distributer_id
            self.user_id = self.distributer_employee_id.user_id

    @api.onchange('distributer_employee_id')
    def _onchange_distributer_employee_id(self):
        """The run is operated under the distributer's own (portal) user."""
        if self.distributer_employee_id.user_id:
            self.user_id = self.distributer_employee_id.user_id

    @api.constrains('state', 'outlet_id')
    def _check_single_open_run_per_outlet(self):
        """An outlet may have at most one open run at any time."""
        for run in self.filtered(lambda r: r.state == 'open'):
            duplicate = self.search([
                ('outlet_id', '=', run.outlet_id.id),
                ('state', '=', 'open'),
                ('id', '!=', run.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Outlet %(outlet)s already has an open run (%(run)s). "
                    "Close it before opening a new one.",
                    outlet=run.outlet_id.display_name, run=duplicate.name))

    # ------------------------------------------------------------------ #
    # Settings helpers
    # ------------------------------------------------------------------ #
    def _get_config_location(self, param_key):
        self.ensure_one()
        value = self.env['ir.config_parameter'].sudo().get_param(
            'wholesale_distribution.%s' % param_key)
        location = self.env['stock.location'].browse(int(value)) if value else self.env['stock.location']
        if not location.exists():
            raise UserError(_(
                "The Wholesale Distribution settings are incomplete: '%s' is not configured.",
                param_key))
        return location

    def _get_main_warehouse(self):
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_("No warehouse found for company %s.", self.company_id.display_name))
        return warehouse

    # ------------------------------------------------------------------ #
    # Internal transfer engine (create + auto-validate one picking)
    # ------------------------------------------------------------------ #
    def _build_internal_transfer(self, picking_type, src_location, dest_location, product_qty_map, origin):
        """Create and immediately validate a single internal transfer.

        :param product_qty_map: dict {product.product record: qty (float)}
        :returns: the validated stock.picking (or empty recordset if nothing to move)
        """
        self.ensure_one()
        moves = []
        for product, qty in product_qty_map.items():
            if float_is_zero(qty, precision_rounding=product.uom_id.rounding):
                continue
            moves.append(Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
            }))
        if not moves:
            return self.env['stock.picking']

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': origin,
            'company_id': self.company_id.id,
            'move_ids': moves,
        })

        # Not confirm this keep it draft
        # picking.action_confirm()
        # picking.action_assign()

        # Force the done quantities to match the demand so no backorder wizard pops up.
        for move in picking.move_ids:
            if float_compare(move.quantity, move.product_uom_qty,
                             precision_rounding=move.product_uom.rounding) != 0:
                move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
        return picking

    def _aggregate_sold_products(self):
        """Aggregate confirmed distribution order lines into {product: qty}."""
        self.ensure_one()
        product_qty = {}
        confirmed_orders = self.sale_order_ids.filtered(lambda o: o.state == 'sale')
        for line in confirmed_orders.order_line:
            # Only physically storable goods take part in the inventory pipeline.
            if line.display_type or not line.product_id or not line.product_id.is_storable:
                continue
            product_qty[line.product_id] = product_qty.get(line.product_id, 0.0) + line.product_uom_qty
        return product_qty

    # ------------------------------------------------------------------ #
    # Action: Charge (Main Warehouse -> outlet location)
    # ------------------------------------------------------------------ #
    def action_charge(self):
        """Prepare a DRAFT internal transfer (main warehouse -> outlet location).

        Charging the outlet is unrelated to the distribution orders: it is the
        physical loading of the truck/shop. This button just creates an empty draft
        picking pre-filled with the right source/destination so the user only has to
        add the product lines and validate it.
        """
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_("Only an open run can be charged."))
        warehouse = self._get_main_warehouse()
        distributer_partner = self._get_distributer_partner()
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': self.outlet_id.location_id.id,
            'partner_id': distributer_partner.id,
            'origin': _("Charge %s", self.name),
            'company_id': self.company_id.id,
        })
        self.charge_picking_id = picking
        return {
            'type': 'ir.actions.act_window',
            'name': _("Charge Outlet"),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------ #
    # Action: Discharge (outlet location -> Main Warehouse) -- unsold stock
    # ------------------------------------------------------------------ #
    def action_discharge(self):
        self.ensure_one()
        warehouse = self._get_main_warehouse()
        outlet_location = self.outlet_id.location_id
        # Whatever physically remains in the outlet is "unsold".
        quants = self.env['stock.quant'].search([
            ('location_id', 'child_of', outlet_location.id),
            ('quantity', '>', 0),
        ])
        product_qty = {}
        for quant in quants:
            product_qty[quant.product_id] = product_qty.get(quant.product_id, 0.0) + quant.quantity
        if not product_qty:
            raise UserError(_("No remaining inventory to discharge for run %s.", self.name))
        picking = self._build_internal_transfer(
            picking_type=warehouse.int_type_id,
            src_location=outlet_location,
            dest_location=warehouse.lot_stock_id,
            product_qty_map=product_qty,
            origin=_("Discharge %s", self.name),
        )
        self.discharge_picking_id = picking
        # Open the resulting transfer so the user lands on the discharge picking.
        return {
            'type': 'ir.actions.act_window',
            'name': _("Discharge Transfer"),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------ #
    # Action: Close the delivery run (manager + cashier)
    # ------------------------------------------------------------------ #
    def action_close_delivery_run(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_("Run %s is already closed.", self.name))

        collected_payments = self.payment_ids.filtered(lambda p: p.state == 'collected')

        # 1. Cashier intake validation: the figure the cashier physically counted is
        #    captured on the run (cashier_counted_amount) and MUST match the collected
        #    sum being handed over, otherwise we refuse to close.
        expected = sum(collected_payments.mapped('amount'))
        if float_compare(self.cashier_counted_amount, expected,
                         precision_rounding=self.currency_id.rounding) != 0:
            raise UserError(_(
                "Cashier intake mismatch: counted %(counted)s but the collected "
                "temporary payments total %(expected)s.",
                counted=self.cashier_counted_amount, expected=expected))

        # 2. Generate ONE accounting payment for the amount being validated, then clear
        #    the counted intake so it does not linger on the run after booking.
        if not float_is_zero(expected, precision_rounding=self.currency_id.rounding):
            self._create_accounting_payment(expected)
        self.cashier_counted_amount = 0.0

        # 3. Inventory: outlet (truck) location -> delivery location.
        delivery_location = self._get_config_location('default_delevery_location_id')
        product_qty = self._aggregate_sold_products()
        if product_qty:
            warehouse = self._get_main_warehouse()
            self.close_picking_id = self._build_internal_transfer(
                picking_type=warehouse.int_type_id,
                src_location=self.outlet_id.location_id,
                dest_location=delivery_location,
                product_qty_map=product_qty,
                origin=_("Close %s", self.name),
            )

        # 4. Flip collected -> validated and set the resulting run state.
        collected_payments.write({'state': 'validated'})

        # total_rest is recomputed from the (now validated) payments.
        if float_is_zero(self.total_rest, precision_rounding=self.currency_id.rounding):
            self.state = 'closed'
        else:
            self.state = 'partial_closed'
        self.end_date = fields.Datetime.now()
        return True

    def _get_distributer_partner(self):
        """The partner standing behind the run: the physical distributer, falling
        back to the operating user when no employee contact is configured."""
        self.ensure_one()
        partner = (
            self.distributer_employee_id.work_contact_id
            or self.distributer_employee_id.user_id.partner_id
            or self.user_id.partner_id
        )
        if not partner:
            raise UserError(_(
                "No partner could be resolved for the distributer of run %s.", self.name))
        return partner

    def _create_accounting_payment(self, amount):
        self.ensure_one()
        partner = self._get_distributer_partner()
        journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_("No cash journal found for company %s.", self.company_id.display_name))
        # force_payment_move guarantees the journal entry (move_id) is generated
        payment = self.env['account.payment'].with_context(force_payment_move=True).create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': amount,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'delivery_run_id': self.id,
            'memo': _("Distribution run %s", self.name),
        })
        payment.action_post()
        return payment

    def _get_general_customer(self):
        self.ensure_one()
        value = self.env['ir.config_parameter'].sudo().get_param(
            'wholesale_distribution.default_general_customer_id')
        partner = self.env['res.partner'].browse(int(value)) if value else self.env['res.partner']
        if not partner.exists():
            raise UserError(_("The general distribution customer is not configured in Settings."))
        return partner

    # ------------------------------------------------------------------ #
    # Action: Validate late payments (no inventory move)
    # ------------------------------------------------------------------ #
    def action_validate_payment_run(self):
        """Validate the cash collected on an already-(partially-)closed run.

        Unlike :meth:`action_close_delivery_run` this performs NO inventory move:
        the goods left the outlet at close time. It only books the newly collected
        cash into one accounting payment, reconciles that payment against the run's
        general (master) sale order invoice, and returns the run to a closed state.
        """
        self.ensure_one()
        if self.state != 'requires_validate':
            raise UserError(_("Run %s has no payments awaiting validation.", self.name))

        collected_payments = self.payment_ids.filtered(lambda p: p.state == 'collected')
        expected = sum(collected_payments.mapped('amount'))

        # Cashier intake must match the cash being validated (same rule as closing).
        if float_compare(self.cashier_counted_amount, expected,
                         precision_rounding=self.currency_id.rounding) != 0:
            raise UserError(_(
                "Cashier intake mismatch: counted %(counted)s but the collected "
                "temporary payments total %(expected)s.",
                counted=self.cashier_counted_amount, expected=expected))

        # Book one accounting payment and reconcile it against the master invoice.
        if not float_is_zero(expected, precision_rounding=self.currency_id.rounding):
            payment = self._create_accounting_payment(expected)
            self._reconcile_payment_with_master(payment)
        self.cashier_counted_amount = 0.0

        # Flip collected -> validated and re-settle the run state.
        collected_payments.write({'state': 'validated'})
        if float_is_zero(self.total_rest, precision_rounding=self.currency_id.rounding):
            self.state = 'closed'
        else:
            self.state = 'partial_closed'
        return True

    def _reconcile_payment_with_master(self, payment):
        """Reconcile a run accounting payment against the master order's invoice and
        surface it on the invoice's reconciled payments.

        Mirrors the batch wizard: pair the payment's receivable line with the master
        invoice's receivable line (native outstanding-payment mechanism, same-account
        only), then link the payment onto the invoice's matched payments.
        """
        self.ensure_one()
        master_order = self.master_order_id
        if not master_order or not payment.move_id:
            return
        invoice = master_order.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'posted')[:1]
        if not invoice:
            return
        if payment.distribution_master_order_id:
            return

        invoice_accounts = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
            and not line.reconciled).account_id
        pay_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
            and not line.reconciled
            and line.account_id in invoice_accounts)
        if not pay_lines:
            raise UserError(_(
                "The run payment could not be matched to the master invoice: it is booked "
                "on receivable account(s) %(pay)s while the invoice uses %(inv)s. Align the "
                "distributer's and the general customer's receivable account.",
                pay=", ".join(payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                ).account_id.mapped('display_name')),
                inv=", ".join(invoice_accounts.mapped('display_name'))))

        for line in pay_lines:
            invoice.js_assign_outstanding_line(line.id)
        invoice.matched_payment_ids = [Command.link(payment.id)]
        payment.distribution_master_order_id = master_order


    # ------------------------------------------------------------------ #
    # Smart-button helpers
    # ------------------------------------------------------------------ #
    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Distribution Orders"),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('delivery_run_id', '=', self.id)],
            'context': {
                'is_distribution': True,
                'default_delivery_run_id': self.id,
                'default_is_distribution_order': True,
            },
        }

    def action_create_distribution_order(self):
        """Create a new distribution order attached to this run."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_("Distribution orders can only be added to an open run."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("New Distribution Order"),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'is_distribution': True,
                'default_is_distribution_order': True,
                'default_delivery_run_id': self.id,
                'default_user_id': self.user_id.id,
            },
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Payments"),
            'res_model': 'distribution.payment',
            'view_mode': 'list,form',
            'domain': [('delivery_run_id', '=', self.id)],
            'context': {'default_delivery_run_id': self.id},
        }

    def action_view_account_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Accounting Payments"),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('delivery_run_id', '=', self.id)],
            'context': {'default_delivery_run_id': self.id},
        }

    def action_view_pickings(self):
        self.ensure_one()
        pickings = self._get_run_pickings()
        action = {
            'type': 'ir.actions.act_window',
            'name': _("Run Transfers"),
            'res_model': 'stock.picking',
            'domain': [('id', 'in', pickings.ids)],
            'context': {'create': False},
        }
        if len(pickings) == 1:
            action.update(view_mode='form', res_id=pickings.id)
        else:
            action.update(view_mode='list,form')
        return action

    def action_view_outlet_quantities(self):
        self.ensure_one()
        location = self.outlet_id.location_id
        if not location:
            raise UserError(_("Outlet %s has no stock location.", self.outlet_id.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Outlet Stock"),
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('location_id', 'child_of', location.id), ('quantity', '!=', 0)],
            'context': {'search_default_productgroup': 1},
        }

    # ------------------------------------------------------------------ #
    # Kanban quick navigation
    # ------------------------------------------------------------------ #
    def action_open_outlet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Outlet"),
            'res_model': 'distribution.outlet',
            'res_id': self.outlet_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_employee(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Distributer"),
            'res_model': 'hr.employee',
            'res_id': self.distributer_employee_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_batch_wizard(self):
        """Open the End-of-Day aggregation wizard from the run form."""
        return self.env['ir.actions.act_window']._for_xml_id(
            'wholesale_distribution.action_distribution_batch_wizard')

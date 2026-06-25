"""Wholesale Distribution - Mobile API (v1).

Full mobile-developer reference (auth, JSON-RPC envelope, every endpoint,
responses and error codes) lives next to this module:
"""

import logging

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

# scope of the Odoo API keys accepted on both tokens (see controllers/README.md §1).
API_KEY_SCOPE = 'rpc'
DISTRIBUTER_TOKEN_HEADER = 'X-Distributer-Token'


class DistributionAPIController(http.Controller):

    # ------------------------------------------------------------------ #
    # Auth helpers
    # ------------------------------------------------------------------ #
    def _safe(self, func):
        """Run an endpoint body returning a uniform JSON envelope instead of an
        HTML error page for the expected business/authentication errors."""
        try:
            return {'status': 'success', 'data': func()}
        except AccessError as err:
            return {'status': 'error', 'code': 'forbidden', 'message': str(err)}
        except (UserError, ValidationError) as err:
            return {'status': 'error', 'code': 'invalid_request', 'message': str(err)}
        except Exception as err:  # noqa: BLE001 - surface a controlled payload to the app
            _logger.exception("Distribution API unexpected error")
            return {'status': 'error', 'code': 'server_error', 'message': str(err)}

    def _check_key(self, raw_header):
        """Resolve an API key header to a uid (low-level, user-agnostic).

        Accepts a 'Bearer <key>' header or a bare key. Returns int uid or None.
        """
        raw_header = (raw_header or '').strip()
        if not raw_header:
            return None
        if raw_header.lower().startswith('bearer '):
            token = raw_header[7:].strip()
        else:
            # Tolerate a bare token (no 'Bearer ' prefix).
            token = raw_header
        if not token:
            return None
        return request.env['res.users.apikeys']._check_credentials(
            scope=API_KEY_SCOPE, key=token)

    def _authenticate(self):
        """Validate BOTH tokens.

        1. Integration key -> switch the request env to the internal integration user.
        2. Distributer portal key -> resolve the acting distributer's portal user.

        :returns: (integration_uid, distributer_user record)
        """
        integration_uid = self._check_key(request.httprequest.headers.get('Authorization'))
        if not integration_uid:
            raise AccessError(_("Missing or invalid integration API token."))

        # Everything from here on runs as the internal integration user.
        request.update_env(user=integration_uid)

        distributer_uid = self._check_key(
            request.httprequest.headers.get(DISTRIBUTER_TOKEN_HEADER))
        if not distributer_uid:
            raise AccessError(_(
                "Missing or invalid distributer portal token (%s header).",
                DISTRIBUTER_TOKEN_HEADER))
        distributer_user = request.env['res.users'].sudo().browse(distributer_uid)
        if not distributer_user.exists():
            raise AccessError(_("Distributer portal user could not be resolved."))
        return integration_uid, distributer_user

    def _resolve_distributer_context(self, distributer_user):
        """From the distributer's portal user, derive the outlet and employee.

        The employee is the hr.employee linked to this portal user; the outlet is
        the one whose default distributer is that employee.
        """
        env = request.env
        employee = env['hr.employee'].sudo().search(
            [('user_id', '=', distributer_user.id)], limit=1)
        if not employee:
            raise UserError(_(
                "No employee is linked to distributer user %s.",
                distributer_user.display_name))
        outlet = env['distribution.outlet'].sudo().search(
            [('default_distributer_id', '=', employee.id)], limit=1)
        if not outlet:
            raise UserError(_(
                "Distributer %s is not assigned to any outlet. Set this employee as the "
                "'Default Distributer' on an outlet first.", employee.display_name))
        return outlet, employee

    def _get_distributer_run(self, distributer_user, run_id=None, require_open=True):
        """Fetch the run for the acting distributer.

        If ``run_id`` is given it is used and ownership is enforced; otherwise the
        distributer's most recent run is returned. ``require_open`` restricts to
        open runs (orders) vs. any state (late payments on closed runs).
        """
        Run = request.env['distribution.delivery.run'].sudo()
        if run_id:
            run = Run.browse(int(run_id))
            if not run.exists():
                raise UserError(_("Unknown delivery run id %s.", run_id))
            if run.user_id != distributer_user:
                raise AccessError(_("This run does not belong to you."))
            if require_open and run.state != 'open':
                raise UserError(_("Run %s is not open.", run.name))
            return run
        domain = [('user_id', '=', distributer_user.id)]
        if require_open:
            domain.append(('state', '=', 'open'))
        run = Run.search(domain, limit=1, order='id desc')
        if not run:
            raise UserError(_(
                "No %(kind)srun found for distributer %(name)s.",
                kind=_("open ") if require_open else "",
                name=distributer_user.display_name))
        return run

    # ------------------------------------------------------------------ #
    # 2. Session initialization: open (or receive) the outlet's delivery run
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/run/open', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def open_run(self, **kw):
        """Open or receive the distributer's delivery run. Params: none.
        Returns {run_id, name, state, outlet_id, outlet_name, distributer_employee_id}.
        See controllers/README.md §4 for the full contract."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()

            Run = request.env['distribution.delivery.run'].sudo()
            # Reuse the distributer's existing open run if there is one.
            run = Run.search([
                ('user_id', '=', distributer_user.id),
                ('state', '=', 'open'),
            ], limit=1, order='id desc')

            if not run:
                # Resolve the outlet (also validates this distributer is assigned one).
                outlet, employee = self._resolve_distributer_context(distributer_user)
                # No open run: only create one if distributers are allowed to.
                can_open = request.env['ir.config_parameter'].sudo().get_param(
                    'wholesale_distribution.distributor_can_open_run', 'True')
                if str(can_open).lower() not in ('true', '1'):
                    raise UserError(_(
                        "No open run exists for outlet %s. Distributers are not allowed "
                        "to open runs; please ask a cashier/manager to open one.",
                        outlet.display_name))
                run = Run.create({
                    'outlet_id': outlet.id,
                    'distributer_employee_id': employee.id if employee else False,
                    'user_id': distributer_user.id,
                })
            return {
                'run_id': run.id,
                'name': run.name,
                'state': run.state,
                'outlet_id': run.outlet_id.id,
                'outlet_name': run.outlet_id.display_name,
                'distributer_employee_id': run.distributer_employee_id.id,
            }
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 3. Order placement: create a distribution sale order + temp payments
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/order/create', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def create_order(self, partner_id=None, lines=None, payments=None, **kw):
        """Create + confirm a distribution order (no picking/invoice) on the
        distributer's open run. Params: partner_id (req), lines[] (req), payments[] (opt).
        Returns {order_id, name, state, amount_total, payment_ids}. See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            if not partner_id:
                raise UserError(_("'partner_id' is required."))
            if not lines:
                raise UserError(_("At least one order line is required."))
            env = request.env

            # The order is always attached to the distributer's own open run; the
            # mobile app never passes a run id.
            run = self._get_distributer_run(distributer_user, require_open=True)
            partner = env['res.partner'].sudo().browse(int(partner_id))
            if not partner.exists():
                raise UserError(_("Unknown customer id %s.", partner_id))

            # 1. Build the order lines.
            order_lines = []
            for line in lines:
                vals = {
                    'product_id': int(line['product_id']),
                    'product_uom_qty': float(line.get('qty', 1.0)),
                }
                if line.get('price') is not None:
                    vals['price_unit'] = float(line['price'])
                order_lines.append((0, 0, vals))

            # 2. Create the distribution sale order. The {'is_distribution': True}
            #    context switch (plus the persistent is_distribution_order flag)
            #    suppresses native delivery-picking generation on confirmation.
            order = env['sale.order'].sudo().with_context(is_distribution=True).create({
                'partner_id': partner.id,
                'is_distribution_order': True,
                'delivery_run_id': run.id,
                'order_line': order_lines,
            })
            order.with_context(is_distribution=True).action_confirm()

            # 3. Register the collected temporary payments.
            created_payments = env['distribution.payment'].sudo()
            for pay in (payments or []):
                created_payments |= env['distribution.payment'].sudo().create({
                    'amount': float(pay['amount']),
                    'currency_id': int(pay['currency_id']) if pay.get('currency_id')
                    else order.currency_id.id,
                    'state': 'collected',
                    'delivery_run_id': run.id,
                    'sale_order_id': order.id,
                })

            return {
                'order_id': order.id,
                'name': order.name,
                'state': order.state,
                'amount_total': order.amount_total,
                'payment_ids': created_payments.ids,
            }
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 4. Independent payment intake (late / standalone collections)
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/payment/add', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def add_payment(self, amount=None, sale_order_id=None, currency_id=None, **kw):
        """Record a cash collection (incl. late, on closed runs). Params: amount (req),
        sale_order_id (opt), currency_id (opt). Returns {payment_id, run_id, run_state, amount}.
        See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            if amount is None:
                raise UserError(_("'amount' is required."))
            env = request.env

            # The run is derived from the order it is paid against (its delivery_run_id);
            # for a standalone collection (no order) we fall back to the distributer's
            # most recent run. Late payments may target an already (partially) closed run.
            order = env['sale.order'].sudo()
            if sale_order_id:
                order = order.browse(int(sale_order_id))
                if not order.exists():
                    raise UserError(_("Unknown sale order id %s.", sale_order_id))
                run = order.delivery_run_id
                if not run:
                    raise UserError(_("Order %s is not attached to a delivery run.", order.name))
                if run.user_id != distributer_user:
                    raise AccessError(_("This order does not belong to you."))
            else:
                run = self._get_distributer_run(distributer_user, require_open=False)

            # A late collection on an already (partially) closed run will flip the run
            # to 'requires_validate' through distribution.payment.create().
            payment = env['distribution.payment'].sudo().create({
                'amount': float(amount),
                'currency_id': int(currency_id) if currency_id else run.currency_id.id,
                'state': 'collected',
                'delivery_run_id': run.id,
                'sale_order_id': order.id if order else False,
            })
            return {
                'payment_id': payment.id,
                'run_id': run.id,
                'run_state': run.state,
                'amount': payment.amount,
            }
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # Read-only serialisers
    # ------------------------------------------------------------------ #
    def _run_summary(self, run):
        return {
            'run_id': run.id,
            'name': run.name,
            'state': run.state,
            'outlet_id': run.outlet_id.id,
            'outlet_name': run.outlet_id.display_name,
            'start_date': run.start_date and str(run.start_date) or None,
            'end_date': run.end_date and str(run.end_date) or None,
            'currency_id': run.currency_id.id,
            'total_sale_orders': run.total_sale_orders,
            'total_paid': run.total_paid,
            'total_validated': run.total_validated,
            'total_rest': run.total_rest,
        }

    def _payment_summary(self, payment):
        return {
            'payment_id': payment.id,
            'date': payment.date and str(payment.date) or None,
            'amount': payment.amount,
            'currency_id': payment.currency_id.id,
            'state': payment.state,
            'sale_order_id': payment.sale_order_id.id or None,
        }

    def _order_summary(self, order, with_payments=False):
        data = {
            'order_id': order.id,
            'name': order.name,
            'partner_id': order.partner_id.id,
            'partner_name': order.partner_id.display_name,
            'date_order': order.date_order and str(order.date_order) or None,
            'state': order.state,
            'amount_total': order.amount_total,
            'currency_id': order.currency_id.id,
        }
        if with_payments:
            data['payments'] = [
                self._payment_summary(p) for p in order.distribution_payment_ids]
        return data

    # ------------------------------------------------------------------ #
    # 5. Runs list (filter + pagination)
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/run/list', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def run_list(self, states=None, limit=80, offset=0, **kw):
        """List the distributer's runs. Params: states[] (opt), limit (80), offset (0).
        Returns {total, count, runs:[run_summary]}. See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            domain = [('user_id', '=', distributer_user.id)]
            if states:
                domain.append(('state', 'in', states))
            Run = request.env['distribution.delivery.run'].sudo()
            total = Run.search_count(domain)
            runs = Run.search(domain, limit=int(limit), offset=int(offset), order='id desc')
            return {
                'total': total,
                'count': len(runs),
                'runs': [self._run_summary(r) for r in runs],
            }
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 6. Run detail: orders with their payments
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/run/detail', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def run_detail(self, run_id=None, **kw):
        """One run with its orders (incl. payments) + run-level payments. Param: run_id (req).
        Returns run_summary + {orders:[...], unlinked_payments:[...]}. See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            if not run_id:
                raise UserError(_("'run_id' is required."))
            run = self._get_distributer_run(distributer_user, run_id, require_open=False)
            summary = self._run_summary(run)
            summary['orders'] = [
                self._order_summary(o, with_payments=True) for o in run.sale_order_ids]
            # Run-level payments that are not tied to a specific order.
            summary['unlinked_payments'] = [
                self._payment_summary(p)
                for p in run.payment_ids.filtered(lambda p: not p.sale_order_id)]
            return summary
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 7. Catalog: products + pricelist price
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/catalog', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def catalog(self, search=None, pricelist_id=None, limit=80, offset=0, **kw):
        """Sellable products with price. Params: search (opt), pricelist_id (opt),
        limit (80), offset (0). Returns {total, count, products:[...]}. See controllers/README.md §4."""
        def _run():
            self._authenticate()
            env = request.env
            domain = [('sale_ok', '=', True)]
            if search:
                domain += ['|', ('name', 'ilike', search),
                           ('default_code', 'ilike', search)]
            Product = env['product.product'].sudo()
            pricelist = env['product.pricelist'].sudo().browse(int(pricelist_id)) \
                if pricelist_id else env['product.pricelist'].sudo()
            total = Product.search_count(domain)
            products = Product.search(domain, limit=int(limit), offset=int(offset), order='name')
            items = []
            for product in products:
                price = pricelist._get_product_price(product, 1.0) \
                    if pricelist else product.list_price
                items.append({
                    'product_id': product.id,
                    'name': product.display_name,
                    'default_code': product.default_code or None,
                    'uom': product.uom_id.display_name,
                    'list_price': product.list_price,
                    'price': price,
                    'currency_id': (pricelist.currency_id.id if pricelist
                                    else product.currency_id.id),
                    'is_storable': product.is_storable,
                })
            return {'total': total, 'count': len(products), 'products': items}
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 8. Open-run outlet on-hand quantities
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/outlet/quantities', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def outlet_quantities(self, run_id=None, **kw):
        """On-hand stock in the run's outlet location. Param: run_id (opt, default open run).
        Returns {run_id, location_id, location_name, lines:[...]}. See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            # Default to the distributer's open run; allow an explicit owned run id.
            run = self._get_distributer_run(distributer_user, run_id, require_open=not run_id)
            location = run.outlet_id.location_id
            if not location:
                raise UserError(_("Outlet %s has no stock location.", run.outlet_id.display_name))
            # available_quantity is a non-stored computed field, so it cannot be
            # aggregated in SQL; derive it as quantity - reserved_quantity.
            groups = request.env['stock.quant'].sudo()._read_group(
                domain=[('location_id', 'child_of', location.id), ('quantity', '!=', 0)],
                groupby=['product_id'],
                aggregates=['quantity:sum', 'reserved_quantity:sum'],
            )
            lines = [{
                'product_id': product.id,
                'name': product.display_name,
                'uom': product.uom_id.display_name,
                'quantity': qty,
                'available_quantity': qty - reserved,
            } for product, qty, reserved in groups]
            return {
                'run_id': run.id,
                'location_id': location.id,
                'location_name': location.display_name,
                'lines': lines,
            }
        return self._safe(_run)

    # ------------------------------------------------------------------ #
    # 9. Search distribution orders by customer / date
    # ------------------------------------------------------------------ #
    @http.route('/api/v1/distribution/order/search', type='jsonrpc',
                auth='none', methods=['POST'], csrf=False)
    def order_search(self, partner_id=None, date_from=None, date_to=None,
                     limit=80, offset=0, **kw):
        """Search the distributer's distribution orders. Params: partner_id (opt),
        date_from (opt), date_to (opt), limit (80), offset (0).
        Returns {total, count, orders:[order_summary]}. See controllers/README.md §4."""
        def _run():
            _integration_uid, distributer_user = self._authenticate()
            domain = [
                ('is_distribution_order', '=', True),
                ('delivery_run_id.user_id', '=', distributer_user.id),
            ]
            if partner_id:
                domain.append(('partner_id', '=', int(partner_id)))
            if date_from:
                domain.append(('date_order', '>=', date_from))
            if date_to:
                # Make a bare date inclusive of the whole day.
                upper = date_to if len(str(date_to)) > 10 else '%s 23:59:59' % date_to
                domain.append(('date_order', '<=', upper))
            Order = request.env['sale.order'].sudo().with_context(is_distribution=True)
            total = Order.search_count(domain)
            orders = Order.search(domain, limit=int(limit), offset=int(offset),
                                  order='date_order desc')
            return {
                'total': total,
                'count': len(orders),
                'orders': [self._order_summary(o) for o in orders],
            }
        return self._safe(_run)

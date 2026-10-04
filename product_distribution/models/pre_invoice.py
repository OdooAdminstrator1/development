from odoo import models, fields, api, _
import logging
from odoo.exceptions import ValidationError,UserError
_logger = logging.getLogger(__name__)

class DistributionPreInvoice(models.Model):
    _name = 'distribution.pre.invoice'
    _description = 'Pre-Invoice'

    distributor_id = fields.Many2one('hr.employee', string='Distributor', domain=[('isdistributor', '=', True)])
    client_id = fields.Many2one('distribution.customer', string='Customer')
    open_date_id = fields.Many2one('distribution.open.date', string='Open Date')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    payment_id = fields.Many2one('account.payment', string='Payment Reference', ondelete='set null')
    
    # NEW FIELD: Relational link to the standard Odoo Sale Order model
    sale_order_id = fields.Many2one('sale.order', string='Sale Order Reference', ondelete='set null')
    
    line_ids = fields.One2many('distribution.pre.invoice.line', 'pre_invoice_id', string='Lines')
    
    total_value = fields.Float(string='Total Value', compute='_compute_total_value', store=False)
    received_amount = fields.Float(string='Received Amount')
    posted_amount = fields.Float(string='Posted Amount', default=0.0)
    rest_amount = fields.Float(string='Rest Amount', compute='_compute_rest_amount', store=False)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('done', 'Done')
    ], string='State', default='draft')

    @api.depends('line_ids.quantity', 'line_ids.price')
    def _compute_total_value(self):
        for record in self:
            record.total_value = sum(line.quantity * line.price for line in record.line_ids)

    @api.depends('total_value', 'posted_amount','received_amount')
    def _compute_rest_amount(self):
        for record in self:
            record.rest_amount = record.total_value - record.received_amount-record.posted_amount

    def action_generate_sale_order(self):
        # Filter out records that are already 'done' or already assigned to a Sale Order
        valid_invoices = self.filtered(lambda r: r.state != 'done' and not r.sale_order_id)
        if not valid_invoices:
            return
            
        product_totals = {}
        for inv in valid_invoices:
            for line in inv.line_ids:
                if line.product_id not in product_totals:
                    product_totals[line.product_id] = {'quantity': 0.0, 'price': line.price}
                # Group by product and sum total quantities across all selected pre-invoices
                product_totals[line.product_id]['quantity'] += line.quantity

        order_lines = []
        for product, data in product_totals.items():
            p_rec=self.env['product.product'].browse(product.id)
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': data['quantity'],
                'product_uom_id': p_rec.uom_id.id,
                'price_unit': data['price'],
            }))

        partner_id = valid_invoices[0].client_id.id if valid_invoices[0].client_id else self.env.company.partner_id.id
        
        # 1. Create the aggregated Sale Order object
        sale_order = self.env['sale.order'].create({
            'partner_id': partner_id,
            'date_order' : fields.Date.context_today(self),
            'order_line': order_lines,
        })

        # 2. UPDATED LOGIC: Map the new Sale Order ID back to all processed Pre-Invoices and set to 'done'
        valid_invoices.write({
            'sale_order_id': sale_order.id,
            'state': 'done'
        })
        
        # Automatically redirect user to the newly generated Sale Order form view
        partner =    self._get_general_customer()    
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'partner_id': partner,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_general_customer(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_distribution.default_general_customer_id')
        partner = self.env['res.partner'].browse(int(value)) if value else self.env['res.partner']
        if not partner.exists():
            raise UserError("The general distribution customer is not configured in Settings.")
        return partner
    


    def action_sync_from_mobile(self, invoices_payload):
        """
        Synchronizes pre-invoices created offline in Flutter app.
        
        :param list invoices_payload: List of dictionaries matching LocalPreInvoice layout.
        :return: Dict containing execution status and local_id -> odoo_id mappings.
        """
        sync_results = []

        for invoice_data in invoices_payload:
            local_id = invoice_data.get('local_id')
            
            try:
                # Use savepoint so failure on one invoice doesn't roll back the whole batch
                with self.env.cr.savepoint():
                    # 1. Format line commands for One2many field
                    line_commands = []
                    for line in invoice_data.get('lines', []):
                        line_commands.append((0, 0, {
                            'product_id': line.get('product_id'),
                            'quantity': line.get('quantity', 1.0),
                            'price': line.get('price', 0.0),
                        }))

                    # 2. Build values dictionary
                    vals = {
                        'client_id': invoice_data.get('client_id'),
                        'distributor_id': invoice_data.get('distributor_id'),
                        'open_date_id': invoice_data.get('open_date_id'),
                        'received_amount': invoice_data.get('received_amount', 0.0),
                        'currency_id': invoice_data.get('currency_id') or self.env.company.currency_id.id,
                        'line_ids': line_commands,
                    }

                    # 3. Create pre-invoice record in Odoo
                    record = self.create(vals)

                    sync_results.append({
                        'local_id': local_id,
                        'odoo_id': record.id,
                        'status': 'success',
                        'error': None
                    })

            except Exception as e:
                _logger.error("Sync failed for local pre-invoice ID %s: %s", local_id, str(e))
                sync_results.append({
                    'local_id': local_id,
                    'odoo_id': None,
                    'status': 'error',
                    'error': str(e)
                })

        return {
            'success': True,
            'synced_count': len([r for r in sync_results if r['status'] == 'success']),
            'results': sync_results
        }




class DistributionPreInvoiceLine(models.Model):
    _name = 'distribution.pre.invoice.line'
    _description = 'Pre-Invoice Line'

    pre_invoice_id = fields.Many2one('distribution.pre.invoice', string='Pre-Invoice', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    lot_id = fields.Many2one('stock.lot', string='Lot')
    quantity = fields.Float(string='Quantity', default=1.0)
    price = fields.Float(string='Price')
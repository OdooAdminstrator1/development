from odoo import models, fields, api, _

class ProductTrace(models.Model):
    _name = "stock.product.trace"
    _description = "Product Cost and Quantity Trace"
    _order = "date desc, id desc"

    date = fields.Datetime('Date', required=True, default=fields.Datetime.now)
    reference = fields.Char(string='Reference')
    location_id = fields.Many2one('stock.location', 'From', domain="[('usage', '!=', 'view')]", check_company=True)
    location_dest_id = fields.Many2one('stock.location', 'To', domain="[('usage', '!=', 'view')]", check_company=True)
    product_id = fields.Many2one(
        'product.product', 'Product', required=True, ondelete="cascade", check_company=True,
        domain="[('type', '!=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )
    qty_done = fields.Float('Done Quantity', digits='Product Unit of Measure', default=0.0)
    qty_old = fields.Float('Old Quantity', digits='Product Unit of Measure', default=0.0)
    qty_new = fields.Float('New Quantity', digits='Product Unit of Measure', default=0.0)
    cost_unit_value = fields.Monetary('Unit Cost', currency_field='currency_id')
    cost_old_value = fields.Monetary('Old AVG cost', currency_field='currency_id')
    cost_new_value = fields.Monetary('New AVG cost', currency_field='currency_id')
    ref_value = fields.Char('Source Document')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    move_id = fields.Many2one('account.move', 'Account Move', check_company=True, index=True)

    stock_move_type = fields.Selection([
        ('preceipt', 'Purchase / Receipt'),
        ('preturn', 'Purchase / Return'),
        ('sdeliver', 'Sales / Delivery'),
        ('sreturn', 'Sales / Return'),
        ('qty_manualy', 'Update Quantity Manually'),
        ('adjustment', 'Inventory Adjustment'),
        ('manufacturing', 'Manufacturing/finished'),
        ('unbuilt', 'Unbuild/finished'),
        ('manufacturing_raw', 'Manufacturing/raw'),
        ('unbuilt_raw', 'Unbuild/raw'),
        ('cost_manually', 'Update Cost Manually'),
        ('landed_cost', 'Landed Cost'),
        ('scrap', 'Scrap'),
        ('inventory_loss', 'Inventory loss'),
        ('undefined', 'Undefined'),

    ], string='Move Type', required=False)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Helper method for creation from valuation layer
    @api.model
    def create_from_valuation_layer(self, valuation_layer):
        """Create a product trace record from a stock_valuation_layer record."""
     #   move_type = self._get_move_type_from_layer(valuation_layer)
        max_id_record = self.env['stock.product.trace'].search([], order='id desc', limit=1)
        # rec =self.env['stock.product.trace'].browse(max_id_record)
        # old_c=0
        # old_q=0

        # if (rec):
        #     old_c= rec.qty_new
        #     old_q= rec.cost_new_value


        return self.create({
            'date': valuation_layer.create_date,
            'reference': valuation_layer.description,
            'product_id': valuation_layer.product_id.id,
            'cost_unit_value': valuation_layer.unit_cost,
            # 'cost_old_value': old_c, #valuation_layer.value - valuation_layer.remaining_value,
            # 'qty_old' : old_q,
            'cost_new_value': valuation_layer.value,
            'qty_done': valuation_layer.quantity,
            'move_id': valuation_layer.account_move_id.id,
            'ref_value': valuation_layer.description or valuation_layer.stock_move_id.name,
          #  'stock_move_type': move_type,
        })

    def _get_move_type_from_layer(self, valuation_layer):
        """Deduce the move type based on related model fields."""
        move = valuation_layer.stock_move_id
        if not move:
            if valuation_layer.stock_landed_cost_id:
                return 'landed_cost'
            return 'cost_manually'

        picking = move.picking_id
        if picking:
            if picking.picking_type_id.code == 'incoming':
                return 'preceipt'
            elif picking.picking_type_id.code == 'outgoing':
                return 'sdeliver'
            elif 'return' in (picking.name or '').lower():
                return 'sreturn'
        if move.raw_material_production_id:
            return 'man_deliver'
        if move.production_id:
            return 'man_unbuilt'
        if move.scrapped:
            return 'scrap'
        return 'adjustment'


class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        trace_model = self.env['stock.product.trace'].sudo()
        for rec in records:
            try:
                trace_model.create_from_valuation_layer(rec)
               
            except Exception as e:
                # You can log the error, but avoid breaking main flow
                _logger = self.env['ir.logging']
                _logger.create({
                    'name': 'Product Trace Log',
                    'type': 'server',
                    'level': 'ERROR',
                    'dbname': self._cr.dbname,
                    'message': f'Failed to create trace for valuation layer {rec.id}: {e}',
                    'path': 'stock.product.trace',
                    'line': 'create_hook',
                    'func': 'create_from_valuation_layer'
                })
        return records


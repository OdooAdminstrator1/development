from odoo import models, fields, api, _
#from odoo.osv import expression
from odoo.tools.float_utils import float_round

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
    cost_unit_value = fields.Float('Unit Cost', currency_field='currency_id')
    cost_old_value = fields.Float('Old AVG cost', currency_field='currency_id')
    cost_new_value = fields.Float('New AVG cost', currency_field='currency_id')
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
    stock_valuation_id=fields.Many2one('stock.valuation.layer', 'valuation_id', check_company=True, index=True)

    attribute_search = fields.Char(
        string='Attribute Search',
        compute='_compute_dummy',
        search='_search_attribute',
    )
    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False

    def _search_attribute(self, operator, value):
        if operator not in ['ilike', 'like'] or not value:
            return []
        return [('product_id.attribute_line_ids.value_ids.name', 'ilike', value)]

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search method to use AND logic between product_id and attribute_search
        """
        new_args = []
        search_terms = []

        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                if field in ['product_id', 'attribute_search'] and operator == 'ilike':
                    search_terms.append((field, operator, value))
                else:
                    new_args.append(domain)
            else:
                new_args.append(domain)

        # Combine all ilike search terms with AND logic safely
        if search_terms:
            if len(search_terms) == 1:
                new_args.append(search_terms[0])
            else:
                combined_domain = []
                for term in search_terms:
                    if not combined_domain:
                        combined_domain = [term]
                    else:
                        combined_domain = combined_domain + [term]
                # extend, not append, to avoid nesting
                new_args += combined_domain

        return super(ProductTrace, self).search(new_args, offset=offset, limit=limit, order=order, count=count)


class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        trace_model = self.env['stock.product.trace'].sudo()
        for rec in records:
            try:
                 trace_model.create_from_valuation_layer(rec,False,False)
             #   newtrace.post_init_hook(rec)
               
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

    def write(self, vals):
        records = super().write(vals)
        # Trigger your function after update
        for rec in self:
            trace_model = self.env['stock.product.trace'].sudo().search([('stock_valuation_id', '=', rec.id)],limit=1)
            if not trace_model.move_id:
                move_id=vals.get('account_move_id')
                if move_id:
                    trace_model.write({'move_id': move_id})
                else:
                    move_id=  rec.account_move_id.id 
                    if not move_id:
                        if  rec.stock_landed_cost_id :
                            move_id=rec.stock_landed_cost_id.account_move_id.id 
                        else:
                            aux=self.env['account.move'].sudo().search(
                                [('stock_move_id', '=', rec.stock_move_id.id)],
                                order='id desc',
                                limit=1
                            )
                            move_id= aux.id 
                    trace_model.write({'move_id': move_id})

        return records
    


from odoo import models, fields, api, _
from odoo.osv import expression

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
    stock_valuation_id=fields.Many2one('stock.valuation.layer', 'valuation_id', check_company=True, index=True)

    attribute_value_id = fields.Many2one(
        'product.attribute.value', 
        string='Attribute Value',
        compute='_compute_attribute_value_id',
        search='_search_attribute_value_id'
    )
    
    def _compute_attribute_value_id(self):
        for record in self:
            # Set to first attribute value or False
            record.attribute_value_id = record.product_id.attribute_line_ids.value_ids[:1] or False
    
    def _search_attribute_value_id(self, operator, value):
        if operator == 'ilike' and value:
            return [('product_id.attribute_line_ids.value_ids.name', 'ilike', value)]
        return []
    
    # Helper method for creation from valuation layer
    @api.model
    def create_from_valuation_layer(self, valuation_layer,trace_rescords,isHook):
        """Create a product trace record from a stock_valuation_layer record."""

        move_id=  valuation_layer.account_move_id.id 
        if not move_id:
            if  valuation_layer.stock_landed_cost_id :
                move_id=valuation_layer.stock_landed_cost_id.account_move_id.id 
            else:
                aux=self.env['account.move'].sudo().search(
                    [('stock_move_id', '=', valuation_layer.stock_move_id.id)],
                    order='id desc',
                    limit=1
                )
                move_id= aux.id 
       
        newtrace= self.create({
            'date': valuation_layer.create_date,
            'reference': valuation_layer.description,
            'product_id': valuation_layer.product_id.id,
            'cost_unit_value': valuation_layer.unit_cost,
            'cost_new_value': valuation_layer.value,
            'qty_done': valuation_layer.quantity,
            #'move_id':valuation_layer.stock_landed_cost_id.account_move_id.id  if  valuation_layer.stock_landed_cost_id else valuation_layer.account_move_id.id ,
            'move_id': move_id,
            'ref_value': valuation_layer.description or valuation_layer.stock_move_id.name,
            'stock_valuation_id': valuation_layer.id,
        })




        # if  isHook:
        #     trace_rescords+=newtrace
        # else:
        #     trace_rescords=None
        newtrace.post_init_hook(valuation_layer,trace_rescords,isHook)

        return newtrace
    

    def post_init_hook(self,valuation_layers,trace_rescords,isHook):
        """Backfill product trace records for existing valuation layers."""
        env = self.env
        new_trace=self


        for vl in valuation_layers:
                # Skip if trace already exists for this valuation layer
        # if trace_model.search_count([('move_id', '=', vl.account_move_id.id)]):
            #    continue
        #   if not vl.account_move_id.id:
        #       continue

            product_id = vl.product_id.id
            loc_id=vl.stock_move_id.location_id
            loc_dest_id=vl.stock_move_id.location_dest_id
            stock_landed_cost_id =vl.stock_landed_cost_id
            is_finished=False
            is_unbuild=vl.stock_move_id.unbuild_id
            loc_dest_usage=vl.stock_move_id.location_dest_id.usage
            is_finished= vl.stock_move_id.production_id
            is_component=not (is_unbuild and product_id==is_unbuild.product_id.id)

            #  Get the latest trace record for the same product

            if isHook:
                # last_trace=trace_rescords
                # valuation_layers = env['stock.product.trace'].search([], order='id')
                max_layer = False
                # max_id = 0
                if trace_rescords:
                    for layer in trace_rescords:
                        # if layer.product_id.id == product_id and layer.id > max_id:
                        #     max_id = layer.id
                            max_layer = layer

                last_trace = max_layer
            else:
                trace_model = env['stock.product.trace'].sudo()
                last_trace = trace_model.search(
                    [('product_id', '=', product_id),('id', '!=', self.id)],
                    order='id desc',
                    limit=1
                )

            #  Determine old cost value
            cost_old_value = last_trace.cost_new_value if last_trace else 0.0
            qty_old_value = last_trace.qty_new if last_trace else 0.0

            #  Create the trace from valuation layer
            #new_trace = trace_model.create_from_valuation_layer(vl)

            #  Update the old cost value
        # new_trace.cost_old_value = cost_old_value
            new_trace.cost_old_value=cost_old_value
            new_trace.qty_new = qty_old_value+new_trace.qty_done
            new_trace.qty_old = qty_old_value
            

            new_trace.cost_new_value=cost_old_value if last_trace else vl.unit_cost
        # new_avg_cost=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
            new_trace.ref_value=vl.stock_move_id.origin

            if stock_landed_cost_id:
                new_trace.stock_move_type='landed_cost'
                new_trace.ref_value=stock_landed_cost_id.name
                if qty_old_value:
                    new_trace.cost_new_value=round((vl.value+cost_old_value*qty_old_value)/qty_old_value,2)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value

            elif loc_id.name=='Vendors':
                new_trace.stock_move_type='preceipt'
                new_trace.ref_value=vl.stock_move_id.origin
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=round((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done),2)
            
            elif loc_id.name=='Customers':
                new_trace.stock_move_type='sreturn'
                new_trace.ref_value=vl.stock_move_id.origin
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=round((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done),2)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value

            elif loc_dest_id.name=='Vendors':
                new_trace.ref_value=vl.stock_move_id.origin
                new_trace.stock_move_type='preturn'

            elif loc_dest_id.name=='Customers':
                new_trace.ref_value=vl.stock_move_id.origin
                new_trace.stock_move_type='sdeliver'

            elif loc_id.name=='Inventory adjustment' or loc_dest_id.name=='Inventory adjustment':
                new_trace.stock_move_type='adjustment'
                new_trace.ref_value=vl.stock_move_id.picking_id.name
                new_trace.ref_value=vl.description



            elif (not loc_id.name) and  (not loc_dest_id):
                new_trace.stock_move_type='cost_manually'
                new_trace.ref_value=vl.stock_move_id.origin

                if  qty_old_value:
                    new_trace.cost_new_value=round(cost_old_value+vl.value/qty_old_value,2)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (loc_dest_id.name=='Scrap'):
                new_trace.stock_move_type='scrap'
            
            elif (loc_dest_usage=='inventory'):
                new_trace.stock_move_type='inventory_loss'
            
            elif (is_finished and loc_id.name=='Production'):
                new_trace.stock_move_type='manufacturing'
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=round((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done),2)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (is_unbuild and product_id==is_unbuild.product_id.id and loc_dest_id.name=='Production'):
                new_trace.stock_move_type='unbuilt'
                new_trace.ref_value=vl.stock_move_id.unbuild_id.mo_id.name
            
            elif (is_component and loc_id.name=='Production'):
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=round((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done),2)
                new_trace.stock_move_type='unbuilt_raw'
                new_trace.ref_value=vl.stock_move_id.unbuild_id.mo_id.name
            
            elif (is_component and loc_dest_id.name=='Production'):
                new_trace.stock_move_type='manufacturing_raw'
                
  
            else:
                new_trace.stock_move_type='undefined'




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
    

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        Enhanced search so typing "ProductName AttrValue"
        returns products that match BOTH tokens (AND).
        Each token must match either the product name
        or an attribute value.
        Only activates when context flag 'from_trace_search' is True.
        """
        args = args or []

        if name and self._context.get('from_trace_search'):
            # Split the search string into individual tokens
            terms = [t.strip() for t in name.split() if t.strip()]
            if terms:
                per_term_domains = []
                for term in terms:
                    # Odoo 15: attribute values are in product_template_attribute_value_ids
                    per_term = [
                        '|',
                        ('name', operator, term),
                        ('product_template_attribute_value_ids.name', operator, term),
                    ]
                    per_term_domains.append(per_term)

                # Combine all per-term domains using AND
                combined_domain = per_term_domains[0]
                for d in per_term_domains[1:]:
                    combined_domain = expression.AND([combined_domain, d])

                # Combine with any existing args
                final_domain = expression.AND([args, combined_domain])
            else:
                final_domain = args

            return super(ProductProduct, self)._name_search(name, final_domain, operator, limit, name_get_uid)

        # Default behavior when context flag is not set
        return super(ProductProduct, self)._name_search(name, args, operator, limit, name_get_uid)

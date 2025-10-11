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
    stock_valuation_id=fields.Many2one('stock.valuation.layer', 'valuation_id', check_company=True, index=True)
    
    # Helper method for creation from valuation layer
    @api.model
    def create_from_valuation_layer(self, valuation_layer,trace_rescords,isHook):
        """Create a product trace record from a stock_valuation_layer record."""


        newtrace= self.create({
            'date': valuation_layer.create_date,
            'reference': valuation_layer.description,
            'product_id': valuation_layer.product_id.id,
            'cost_unit_value': valuation_layer.unit_cost,
            'cost_new_value': valuation_layer.value,
            'qty_done': valuation_layer.quantity,
            'move_id': valuation_layer.account_move_id.id,
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
                max_layer = False
                if trace_rescords:
                    for layer in trace_rescords:
                            max_layer = layer

                last_trace = max_layer
            else:
                trace_model = env['stock.product.trace'].sudo()
                last_trace = trace_model.search(
                    [('product_id', '=', product_id)],
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

            if stock_landed_cost_id:
                new_trace.stock_move_type='landed_cost'
                if qty_old_value:
                    new_trace.cost_new_value=(vl.value+cost_old_value*qty_old_value)/qty_old_value
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value

            elif loc_id.name=='Vendors':
                new_trace.stock_move_type='preceipt'
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
            
            elif loc_id.name=='Customers':
                new_trace.stock_move_type='sreturn'
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value

            elif loc_dest_id.name=='Vendors':
                new_trace.stock_move_type='preturn'

            elif loc_dest_id.name=='Customers':
                new_trace.stock_move_type='sdeliver'

            elif loc_id.name=='Inventory adjustment' or loc_dest_id.name=='Inventory adjustment':
                new_trace.stock_move_type='adjustment'

            elif (not loc_id.name) and  (not loc_dest_id):
                new_trace.stock_move_type='cost_manually'
                if  qty_old_value:
                    new_trace.cost_new_value=cost_old_value+vl.value/qty_old_value
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (loc_dest_id.name=='Scrap'):
                new_trace.stock_move_type='scrap'
            
            elif (loc_dest_usage=='inventory'):
                new_trace.stock_move_type='inventory_loss'
            
            elif (is_finished and loc_id.name=='Production'):
                new_trace.stock_move_type='manufacturing'
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (is_unbuild and product_id==is_unbuild.product_id.id and loc_dest_id.name=='Production'):
                new_trace.stock_move_type='unbuilt'
            
            elif (is_component and loc_id.name=='Production'):
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
                new_trace.stock_move_type='unbuilt_raw'
            
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
                newtrace=trace_model.create_from_valuation_layer(rec,[],False)
                newtrace.post_init_hook(rec)
               
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


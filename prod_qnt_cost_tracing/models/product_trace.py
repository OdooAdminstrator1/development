from odoo import models, fields, api, _
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
    cost_system = fields.Float('System cost', currency_field='currency_id')
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

    attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')

    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False

    def _search_attribute(self, operator, value):
        """Search by product attribute values"""
        if operator == 'ilike' and value:
            return [('product_id.attribute_line_ids.value_ids.name', 'ilike', value)]
        return []

    
    def open_date_filter(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Filter by Accounting Date',
            'res_model': 'stock.product.trace.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
    

    def get_latest_traces_fast(self, dd):
        query = """
                SELECT  MAX(spt2.id) AS id
                FROM stock_product_trace spt2
                JOIN account_move am2 ON am2.id = spt2.move_id
                WHERE am2.date <= %s
                GROUP BY spt2.product_id
        """
        self.env.cr.execute(query, [dd])
        ids = [r[0] for r in self.env.cr.fetchall()]
        return ids # self.browse(ids)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search method to use AND logic between search terms,
        including computed fields like attribute_search.
        """
        new_args = []
        search_terms = []

        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                if field =='attribute_search':
                    attrib=self.env['product.attribute.value'].search([('name', 'ilike', value)]).ids
                    search_terms.append(('product_id.product_template_attribute_value_ids.product_attribute_value_id', 'in', attrib))
                else:
                    new_args.append(domain)
            else:
                new_args.append(domain)

        # Combine search terms with AND (&) logic properly
        if search_terms:
            # Start with the first term
            combined_domain = [search_terms[0]]
            # For each next term, prepend an '&' and the new term
            for term in search_terms[1:]:
                combined_domain =combined_domain + [term]
            new_args += combined_domain  # extend, not append

        return super(ProductTrace, self).search(new_args, offset=offset, limit=limit, order=order, count=count)



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
            'cost_system': None if isHook else valuation_layer.product_id.standard_price
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
            precision_digits = 12

            #  Create the trace from valuation layer
            #new_trace = trace_model.create_from_valuation_layer(vl)

            #  Update the old cost value
        # new_trace.cost_old_value = cost_old_value
            new_trace.cost_old_value=cost_old_value
            new_trace.qty_new  = float_round(qty_old_value+new_trace.qty_done, precision_digits=precision_digits, rounding_method='DOWN')
         #   new_trace.qty_new = qty_old_value+new_trace.qty_done
            new_trace.qty_old = qty_old_value
            

            new_trace.cost_new_value=cost_old_value if last_trace else vl.unit_cost
        # new_avg_cost=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)
            new_trace.ref_value=vl.stock_move_id.origin

            if stock_landed_cost_id:
                new_trace.stock_move_type='landed_cost'
                new_trace.ref_value=stock_landed_cost_id.name
                if qty_old_value:
                    new_trace.cost_new_value=float_round ((vl.value+cost_old_value*qty_old_value)/qty_old_value, precision_digits=precision_digits, rounding_method='DOWN')
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value

            elif loc_id.name=='Vendors':
                new_trace.stock_move_type='preceipt'
                new_trace.ref_value=vl.stock_move_id.origin
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=float_round ((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done), precision_digits=precision_digits, rounding_method='DOWN')
            
            elif loc_id.name=='Customers':
                new_trace.stock_move_type='sreturn'
                new_trace.ref_value=vl.stock_move_id.origin
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=float_round ((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done), precision_digits=precision_digits, rounding_method='DOWN')
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
                    new_trace.cost_new_value=float_round (cost_old_value+vl.value/qty_old_value, precision_digits=precision_digits, rounding_method='DOWN')
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (loc_dest_id.name=='Scrap'):
                new_trace.stock_move_type='scrap'
            
            elif (loc_dest_usage=='inventory'):
                new_trace.stock_move_type='inventory_loss'
            
            elif (is_finished and loc_id.name=='Production'):
                new_trace.stock_move_type='manufacturing'
                if (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=float_round ((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done), precision_digits=precision_digits, rounding_method='DOWN')
                else:
                    new_trace.cost_new_value=new_trace.cost_old_value
                
            elif (is_unbuild and product_id==is_unbuild.product_id.id and loc_dest_id.name=='Production'):
                new_trace.stock_move_type='unbuilt'
                new_trace.ref_value=vl.stock_move_id.unbuild_id.mo_id.name
            
            elif (is_component and loc_id.name=='Production'):
                if not (qty_old_value+new_trace.qty_done):
                    new_trace.cost_new_value=new_trace.cost_old_value
                else:
                    new_trace.cost_new_value=float_round((cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done), precision_digits=precision_digits, rounding_method='DOWN')
                new_trace.stock_move_type='unbuilt_raw'
                new_trace.ref_value=vl.stock_move_id.unbuild_id.mo_id.name
            
            elif (is_component and loc_dest_id.name=='Production'):
                new_trace.stock_move_type='manufacturing_raw'
                
  
            else:
                new_trace.stock_move_type='undefined'

class TraceProduct(models.Model):
    _inherit = 'product.product'  
    def write(self, vals):
        records = super().write(vals)
        self.ensure_one()
        domain = [('stock_move_type', '=', 'cost_manually')]  # Add your filters here
        last_record = self.env['stock.product.trace'].search(domain, order='id desc', limit=1)
        
        if last_record:
            last_record.write({
                'cost_system': vals.get('standard_price'),
            })

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        trace_model = self.env['stock.product.trace'].sudo()
        for rec in records:
            # try:
                 trace_model.create_from_valuation_layer(rec,False,False)
             #   newtrace.post_init_hook(rec)
               
            # except Exception as e:
            #     # You can log the error, but avoid breaking main flow
            #     _logger = self.env['ir.logging']
            #     _logger.create({
            #         'name': 'Product Trace Log',
            #         'type': 'server',
            #         'level': 'ERROR',
            #         'dbname': self._cr.dbname,
            #         'message': f'Failed to create trace for valuation layer {rec.id}: {e}',
            #         'path': 'stock.product.trace',
            #         'line': 'create_hook',
            #         'func': 'create_from_valuation_layer'
            #     })
        
        return records

    def write(self, vals):
        records = super().write(vals)
        # Trigger your function after update
        recLanded=False
        trace_rec=False
        if records:
            for rec in self:

                trace_model = self.env['stock.product.trace'].sudo().search([('stock_valuation_id', '=', rec.id)],limit=1)
                trace_model.cost_system=trace_model.product_id.standard_price
                if rec.stock_landed_cost_id:
                    print('land cost id ' +str(rec.stock_landed_cost_id))
                    print('account_move_id ' +str(rec.account_move_id))
                    print('account_move_id landed ' +str(rec.stock_landed_cost_id.account_move_id))

                if not trace_model.move_id:
                    move_id=rec.account_move_id
                    if move_id:
                        trace_model.write({'move_id': move_id})
                        if  rec.stock_landed_cost_id:
                            
                            recLanded=rec
                            trace_rec=trace_model
                    else:
                            aux=self.env['account.move'].sudo().search(
                                [('stock_move_id', '=', rec.stock_move_id.id)],
                                order='id desc',
                                limit=1
                            )
                            move_id= aux.id 
                            trace_model.write({'move_id': move_id})
        self.env.cr.commit()
        if (recLanded):
            self.updateRelated(rec,trace_rec)

        return records
    
    def updateRelated(self,rec,trace_rec):
        related = self.env['stock.product.trace'].sudo().search([('ref_value', '=', rec.stock_landed_cost_id.name),('id','!=',trace_rec.id)])
        for item in related:
            print('id: '+str(item.id));
            item.write({'move_id': rec.account_move_id.id,
                        'cost_system':item.product_id.standard_price })
        
    


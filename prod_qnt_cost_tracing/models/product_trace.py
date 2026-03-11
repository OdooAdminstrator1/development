from odoo import models, fields, api, _
from odoo.tools.float_utils import float_round
from collections import defaultdict
from datetime import date
from odoo.exceptions import ValidationError #  ,UserError
from odoo.api import SUPERUSER_ID

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
    result_value = fields.Float('SubT Value', currency_field='currency_id',compute='_compute_value')
    attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')
    product_num = fields.Char(string='Product ID', compute='_compute_dummy', search='_search_product_id')
    product_category = fields.Many2one(
        'product.category', 
        string='Product Category',
        related='product_id.categ_id',
        store=True,
        readonly=True
    )
    external_id = fields.Char(
        string='External ID',
        compute='_compute_external_id',
        store=False,
        compute_sudo=True  # Required to access ir.model.data records
    )
    move_updated = fields.Boolean(string='Updated',default= False, readonly=True)
    accdate = fields.Date(string='Accounting Date', related='move_id.date',readonly=True,)
    seq = fields.Integer(string='Seq', related='stock_valuation_id.id',readonly=True,)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        self.env.cr.execute("""update stock_product_trace A
set move_id=B.move_id                    
from stock_product_trace B inner join stock_valuation_layer v on b.stock_valuation_id =v.id 
where v.stock_valuation_layer_id is not null
and A.stock_move_type= 'landed_cost'
and A.ref_value=B.ref_value
and B.move_id is not null;
update stock_product_trace A
set move_id=vl.account_move_id
from stock_valuation_layer vl
where A.stock_move_type='cost_manually'
and A.stock_valuation_id=vl.id
and  A.move_id<>vl.account_move_id
and vl.account_move_id is not null;
         """)
        return super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )

        
    # @api.depends()
    def _compute_external_id(self):
        """Compute the export external ID in the same format as Odoo's export wizard."""
        for record in self:
            # Check if we should use the regular XML ID or generate an export ID
            xml_id_data = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'product.product'),
                ('res_id', '=', record.product_id.id)
            ], limit=1)
            
            if xml_id_data:
                # If the product has a regular XML ID, use it
                record.external_id = f"{xml_id_data.module}.{xml_id_data.name}"
            else:
                # Otherwise, generate the export format: __export__.model_name_id_suffix
                # Note: The suffix in real export is a hash of some data, but we'll use a simpler approach
                import hashlib
                import time
                
                # Create a unique suffix based on product ID and timestamp
                # This mimics Odoo's behavior but won't match exactly what export generates
                unique_string = f"product_product_{record.product_id.id}_{time.time()}"
                suffix = hashlib.md5(unique_string.encode()).hexdigest()[:8]
                
                record.external_id = f"__export__.product_product_{record.product_id.id}_{suffix}"

    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False
            record.product_num = False
    def _compute_value(self):
        for rec in self:
            rec.result_value=rec.qty_new*rec.cost_new_value
           # rec.result_value=rec.qty_new*(rec.cost_system if rec.cost_system>0 else rec.cost_new_value)
    
    def _search_attribute(self, operator, value):
        """Search by product attribute values"""
        if operator == 'ilike' and value:
            return [('product_id.attribute_line_ids.value_ids.name', 'ilike', value)]
        return []
    
    def _search_product_id(self, operator, value):
        """Search by product by id"""
        if operator == 'ilike' and value:
            return [('product_id.id', '=', value)]
        return []    

    
    def open_date_filter(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Filter by Accounting Date',
            'res_model': 'stock.product.trace.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_process_date': date.today(),
            }
        }

    def open_date_for_move(self):
        last_day_prev_year = date(date.today().year - 1, 12, 31)
        records = self.env.context.get('active_ids', [])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Set Accounting Date To',
            'res_model': 'stock.product.trace.wizard',
            'view_id': self.env.ref('prod_qnt_cost_tracing.view_stock_product_trace_acc_move').id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_process_date': last_day_prev_year,
                'active_ids': records,
            }
        }
    
    def update_move_dates(self,active_ids,mdate):
        # selected records from tree view
        recs=self.env['stock.product.trace'].browse(active_ids) 
        move_ids=recs.mapped('move_id').ids
        journal_entries = self.env['account.move'].browse(move_ids)
        for entry in journal_entries:
            if entry.date < mdate:
                raise ValidationError("New date must be less than original date!!")

            entry.write({'name': self.env['ir.sequence'].next_by_code('account.move'),'date': mdate })
            entry._compute_name()
        related = self.env['stock.product.trace'].search([('move_id', 'in', move_ids)])
        for rec in related:
            rec.write({'move_updated':True})

    
    def getSummary(self,domain):
        records = self.env['stock.product.trace'].search(domain)
        total = sum( record.result_value 
        for record in records if record.result_value 
    )
        return format(int(total or 0),',') 

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
        query = """
               -- select sum(qty_new*(case when cost_system>0 then cost_system else cost_new_value end)) from
                select sum(qty_new*cost_new_value) from
                stock_product_trace where id in (
                SELECT  MAX(spt2.id) AS id
                FROM stock_product_trace spt2
                JOIN account_move am2 ON am2.id = spt2.move_id
                WHERE am2.date <= %s
                GROUP BY spt2.product_id)
        """
        self.env.cr.execute(query, [dd])
        res=self.env.cr.fetchone()
        tot= format( int(res[0]),',') if res[0] else '0'

        return ids,tot # self.browse(ids)

    @api.model
    def create_from_valuation_layer(self, valuation_layer,trace_rescords,isHook):
        """Create a product trace record from a stock_valuation_layer record."""

        move_id=  valuation_layer.account_move_id.id 

                
        if not move_id and not valuation_layer.stock_landed_cost_id :
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


        newtrace.post_init_hook(valuation_layer,trace_rescords,isHook)
        # if  move_id :
        #         related = self.env['stock.product.trace'].sudo().search([('ref_value', '=', valuation_layer.description)])
        #         for item in related:
        #             item.write({'move_id': move_id,
        #                         'cost_system':item.product_id.standard_price })

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
                    new_trace.cost_system=new_trace.cost_new_value
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
            # if isHook:
            #         new_trace.cost_system=new_trace.cost_new_value

    def update_ref(self):
        for rec in self:
            if rec.stock_move_type =='landed_cost':
                sql =f"""
        SELECT stock_picking.name as source FROM  stock_valuation_layer
        inner join stock_move_line on stock_valuation_layer.stock_move_id=stock_move_line.move_id
        inner join stock_picking on stock_move_line.picking_id=stock_picking.id
        where  stock_valuation_layer.id={rec.stock_valuation_id.id}"""
                self.env.cr.execute(sql)
                res=self.env.cr.fetchone()
                if res:
                    rec.ref_value=res[0]

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
                elif field =='product_category' and value=='-1':
                    search_terms.append(('id','in',self.getNormalTrace()))
                else:
                    new_args.append(domain)


               # [('id', 'in', latest_traces)]
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

        
        res= super(ProductTrace, self).search(new_args, offset=offset, limit=limit, order=order, count=count)    
        return res

    def getNormalTrace(self):
        recs=[]
        allrec=self.env['stock.product.trace'].search([])
        for rec in allrec:
            acc_id=rec.product_id.categ_id.property_stock_valuation_account_id
            if not acc_id:
                continue
            sql =f"""
select count(*) from stock_product_trace s 
inner join account_move as m on s.move_id=m.id
inner join account_move_line as l on l.move_id=m.id  
where s.id={rec.id} and l.account_id ={acc_id.id}
"""
            self.env.cr.execute(sql)
            res=self.env.cr.fetchone()
            if int(res[0])>0:
                recs.append(rec.id)
        return recs

    @api.ondelete(at_uninstall=False)
    def _check_deletion_conditions(self):
        raise ValidationError("Deleting is not allowed")
        # for record in self:
        #     # Check multiple conditions
        #     if record.protected_field:
        #         raise exceptions.UserError(
        #             _('Record is protected and cannot be deleted.')
        #         )
        #     if record.has_related_records():
        #         raise exceptions.UserError(
        #             _('Cannot delete record with related data.')
        #         )

    # def write(self, vals):
    #     all_keys=vals.keys()
    #     if len(all_keys)>1 or vals.get('move_updated') is None:
    #         raise ValidationError("Modifying traced data is not allowed")

class TraceProduct(models.Model):
    _inherit = 'product.product'
    nbr_moves_trace = fields.Integer(compute='_compute_trace_moves', compute_sudo=False)
  
    def _compute_trace_moves(self):
        res = defaultdict(dict)
        trace_moves = self.env['stock.product.trace'].read_group([
                ('product_id', 'in', self.ids),
            ], ['product_id'], ['product_id'])
        for move in trace_moves:
            res[move['product_id'][0]]['moves_tr'] = int(move['product_id_count'])
        for product in self:
            product_res = res.get(product.id) or {}
            product.nbr_moves_trace = product_res.get('moves_tr', 0)
    
    def write(self, vals):
        if 'categ_id' in vals:
            for rec in self:
                SQL="select count(*)  from account_move_line where product_id="+str(rec.id)
                self._cr.execute(SQL)
                query_res = self._cr.fetchone()
                if (int(query_res[0])>0):
                    SQL="select id  from account_move_line where product_id="+str(rec.id)
                    self._cr.execute(SQL)
                    query_res = self._cr.fetchone()
                    raise ValidationError("You cannot change the category because of the existance of account moves which are related to the product, referenced by "+str(query_res[0]))


        records = super().write(vals)
        # if 'standard_price' in vals:
        #    new_price = vals.get('standard_price')
        #    for rec in self: 
        #         domain = [('stock_move_type', '=', 'cost_manually'),('product_id','=',rec.id)]  # Add your filters here
        #         last_record = self.env['stock.product.trace'].search(domain, order='id desc', limit=1)
        #         if last_record:
        #             last_record.write({
        #                 'cost_system': new_price,
        #             })
        return records
                    
    def action_view_stock_product_trace(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("prod_qnt_cost_tracing.stock_product_trace_action")
        action['domain'] = [('product_id', '=', self.id)]
        return action

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # record_ids = records.ids
        def _after_commit():
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                for rec in records:
                    trace_model = env['stock.product.trace'].sudo().search([('stock_valuation_id', '=', rec.id)],limit=1)
                    trace_model.cost_system=trace_model.product_id.standard_price
                env.cr.commit()
#                 env.cr.execute("""
# update stock_product_trace A
# set move_id=B.move_id                    
# from stock_product_trace B inner join stock_valuation_layer v on b.stock_valuation_id =v.id 
# where v.stock_valuation_layer_id is not null
# and A.stock_move_type= 'landed_cost'
# and A.ref_value=B.ref_value
# and B.move_id is not null;
#         """)
#                # env.cr.commit()
#                 env.cr.execute("""
# update stock_product_trace A 
# set move_id=vl.account_move_id
# from stock_valuation_layer vl
# where 
#  A.stock_valuation_id=vl.id
# and  A.move_id<>vl.account_move_id
# and vl.account_move_id is not null;
#         """)

                


    
        
        trace_model = self.env['stock.product.trace'].sudo()
        for rec in records:
                 trace_model.create_from_valuation_layer(rec,False,False)
        if self.env.context.get('no_post_commit'):
            return records
        self.env.cr.postcommit.add(_after_commit)
        return records

    def write(self, vals):
        records = super().write(vals)
        if self.env.context.get('no_post_commit'):
            # Skip if already in post-commit context
            return records
        record_ids = self.ids
        self.env.cr.postcommit.add(
            lambda: self._after_commit_write(record_ids)
        )
        return records
    

    def _after_commit_write(self, record_ids):
        """Called ONLY after successful commit"""
        # Create new cursor/environment since transaction is complete
        with api.Environment.manage():
            if record_ids:
                with self.pool.cursor() as new_cr:
                    new_env = api.Environment(new_cr, SUPERUSER_ID, self.env.context)
                    # new_env.cr.execute("""
                    # update stock_product_trace A
                    # set move_id=B.move_id                    
                    # from stock_product_trace B inner join stock_valuation_layer v on b.stock_valuation_id =v.id 
                    # where v.stock_valuation_layer_id is not null
                    # and A.stock_move_type= 'landed_cost'
                    # and A.ref_value=B.ref_value
                    # and B.move_id is not null;
                    #         """)
                    records = new_env[self._name].browse(record_ids)
                    for rec in records:

                        trace_model = new_env['stock.product.trace'].sudo().search([('stock_valuation_id', '=', rec.id)],limit=1)
                        # trace_model.cost_system=trace_model.product_id.standard_price
                        if not trace_model.move_id:
                            move_id=rec.account_move_id.id
                            if move_id:
                                trace_model.write({'move_id': move_id})
                            else:
                                    aux=new_env['account.move'].sudo().search(
                                        [('stock_move_id', '=', rec.stock_move_id.id)],
                                        order='id desc',
                                        limit=1
                                    )
                                    if aux:
                                        trace_model.write({'move_id': aux.id})
                    new_env.cr.commit()

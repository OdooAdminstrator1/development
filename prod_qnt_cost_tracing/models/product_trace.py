from odoo import models, fields, api, _
from odoo.tools.float_utils import float_round
from collections import defaultdict

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
    def _compute_value(self):
        for rec in self:
            rec.result_value=rec.qty_new*(rec.cost_system if rec.cost_system>0 else rec.cost_new_value)
    
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
                select sum(qty_new*(case when cost_system>0 then cost_system else cost_new_value end)) from
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

        
        res= super(ProductTrace, self).search(new_args, offset=offset, limit=limit, order=order, count=count)    
        return res


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
        records = super().write(vals)
        if 'standard_price' in vals:
           new_price = vals.get('standard_price')
           for rec in self: 
                domain = [('stock_move_type', '=', 'cost_manually'),('product_id','=',rec.id)]  # Add your filters here
                last_record = self.env['stock.product.trace'].search(domain, order='id desc', limit=1)
                if last_record:
                    last_record.write({
                        'cost_system': new_price,
                    })
                    
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



        
    


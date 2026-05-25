from odoo import api, fields, models, tools

class ProductionOrderFile(models.Model):
    _name = 'production.order.file'
    _description = 'Production Order File'

    name = fields.Char(string="Filename")
    file = fields.Binary(string="File", required=True, attachment=True) 
    production_order_id = fields.Many2one('production.order', string="Production Order")
    file_download = fields.Binary(string="Download", related="file", readonly=True)
    opportunity_stage = fields.Char(
        string="Opportunity Stage",
        compute='_compute_opportunity_stage',
        store=True,
        readonly=True
    )

    @api.depends('production_order_id.opportunity_id.stage_id')
    def _compute_opportunity_stage(self):
        """Automatically get the stage name from the linked opportunity"""
        for file_record in self:
            if file_record.production_order_id and file_record.production_order_id.opportunity_id and (not file_record.opportunity_stage):
                file_record.opportunity_stage = file_record.production_order_id.opportunity_id.stage_id.name
            else:
                file_record.opportunity_stage = False

    @api.model
    def create(self, vals):
        """Override create to automatically set opportunity_stage when a new file is created"""
        record = super(ProductionOrderFile, self).create(vals)
        # Force computation of opportunity_stage after creation
        if 'opportunity_stage' not in vals:
            record._compute_opportunity_stage()
        return record
    
class ProductionOrderMaterials(models.Model):
    _name = 'production.order.materials'
    _description = 'Finished Products'

    production_order_id = fields.Many2one('production.order', string="Production Order")
    name = fields.Char(string="Pre Sales Code")
    product_id = fields.Many2one('product.product', 'Product', required=True, ondelete="cascade",    )
    qty = fields.Float('Quantity', digits='Product Unit of Measure', default=0.0)
    row_mat = fields.Selection([('totaly', 'Totaly'), ('partialy', 'Partialy'), ('none', 'None')],string='Availability', compute='_compute_mat_availability')

    @api.depends("product_id","qty")
    def _compute_mat_availability(self):
        for rec in self:
            on_hand_qty = 0
            mprs=self.env['mrp.production'].search([('production_order_id','=',rec.production_order_id.id),('product_id','=',rec.product_id.id)])
            for mprs_rec in mprs:
                if mprs_rec.qty_producing:
                    on_hand_qty+=mprs_rec.qty_producing
            if on_hand_qty>= rec.qty:
                rec.row_mat='totaly'
            elif on_hand_qty>0:
                rec.row_mat='partialy'
            else:
                rec.row_mat='none'

class ProductionOrder(models.Model):
    _name = 'production.order'
    _description = 'Production Order'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', compute='_compute_partner', store=True, readonly=True)
    adopted_date = fields.Date(string='Adopted date')
    row_mat = fields.Selection([('totaly', 'Totaly'), ('partialy', 'Partialy'), ('none', 'None')],string='Raw Material Availability')
    manufactured = fields.Selection([('totaly', 'Totaly'), ('partialy', 'Partialy'), ('none', 'None')],string='Manufactured',compute='_compute_manufactured',)
    file_ids = fields.One2many('production.order.file', 'production_order_id', string="Files")
    product_ids = fields.One2many('production.order.materials', 'production_order_id', string="Finished Products")
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )
    expected_revenue = fields.Monetary(string='Expected Revenue', related='opportunity_id.expected_revenue',currency_field='currency_id',readonly=True,)
    
    total_invoiced_untaxed = fields.Float(
        string='Total Invoiced',
        compute='_compute_invoice_totals',
    )

    to_be_invoiced = fields.Float(
        string='To be invoiced',
        compute='_compute_invoice_totals',
    )
    
    total_paid_untaxed = fields.Float(
        string='Net Collected',
        compute='_compute_invoice_totals',
    )
    
    total_tax = fields.Float(
        string='Total Taxes',
        compute='_compute_invoice_totals',
    )

    total_paid = fields.Float(
        string='Total Collected',
        compute='_compute_invoice_totals',
        store=False,
    )

    # NEW: Reverse one‑to‑many from sale.order (sale.order already has 'production_order_id')
    sale_ids = fields.One2many('sale.order', 'production_order_id', string='Sale Orders')

    # NEW: Reverse one‑to‑many from mrp.production (mrp.production already has 'production_order_id')
    mrp_production_ids = fields.One2many('mrp.production', 'production_order_id', string='MRP Productions')

    # NEW: Many‑to‑many to purchase.order using the existing relation table
    purchase_ids = fields.Many2many(
        'purchase.order',
        relation='rel_production__purchase',   # same table used in purchase.order
        column1='production_id',                # column for this model
        column2='purchase_id',                 # column for purchase.order
        string='Purchase Orders'
    )


    def _compute_invoice_totals(self):
        for record in self:
            # Get all sale orders linked to this production order
            sale_orders = self.env['sale.order'].search([
                ('production_order_id', '=', record.id)
            ])

            untaxed_sum = 0.0
            paid_untaxed_sum = 0.0
            tax_sum = 0.0
            paid_total = 0.0

            for sale in sale_orders:
                # Only consider posted invoices
                posted_invoices = sale.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                for inv in posted_invoices:
                    untaxed = inv.amount_untaxed
                    total = inv.amount_total
                    tax = total - untaxed   # total tax amount
                    paid_total += inv.amount_total - inv.amount_residual

                    untaxed_sum += untaxed
                    tax_sum += tax

                    # Proportional paid amount (excl. tax)
                    if total != 0:
                        paid_proportion = (total - inv.amount_residual) / total
                        paid_untaxed_sum += untaxed * paid_proportion
                    # else: if total is zero, paid_untaxed remains unchanged
            record.total_invoiced_untaxed = untaxed_sum
            record.to_be_invoiced =record.expected_revenue - untaxed_sum
            record.total_paid_untaxed = paid_untaxed_sum
            record.total_paid =paid_total
            record.total_tax = tax_sum


    @api.depends('opportunity_id')
    def _compute_partner(self):
        for record in self:
            record.partner_id = record.opportunity_id.partner_id

    @api.depends('product_ids.product_id','product_ids.qty')
    def _compute_manufactured(self): #_compute_mat_availability
        for pro_order in self:
            all_p=pro_order.product_ids
            ret ='none'
            if len(all_p)>0:
                ret ='totaly'
            else:
               pro_order.manufactured= 'none'
               next
                
            for rec in all_p:
                if rec.row_mat=='partialy':
                    ret='partialy'
                    break
                elif rec.row_mat=='none':
                    ret='none'
            pro_order.manufactured=ret
            
    @api.onchange('opportunity_id')
    def _onchange_opportunity_id(self):
        """Auto-fill name from opportunity if empty."""
        if self.opportunity_id and not self.name:
            self.name = self.opportunity_id.name

    # Smart button fields (from previous implementation)
    sale_order_count = fields.Integer(string='Sale Order Count', compute='_compute_sale_order_count')
    mrp_production_count = fields.Integer(string='Manufacturing Order Count', compute='_compute_mrp_production_count')

    @api.depends('opportunity_id')
    def _compute_partner(self):
        for record in self:
            record.partner_id = record.opportunity_id.partner_id

    @api.depends('opportunity_id')
    def _compute_sale_order_count(self):
        for order in self:
            order.sale_order_count = self.env['sale.order'].search_count([('production_order_id', '=', order.id)])

    @api.depends('opportunity_id')
    def _compute_mrp_production_count(self):
        for order in self:
            order.mrp_production_count = self.env['mrp.production'].search_count([('production_order_id', '=', order.id)])

    @api.onchange('opportunity_id')
    def _onchange_opportunity_id(self):
        """Auto-fill name from opportunity if empty."""
        if self.opportunity_id and not self.name:
            self.name = self.opportunity_id.name

    # Action methods for smart buttons
    def action_view_sale_orders(self):
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

    def action_view_mrp_productions(self):
        action = self.env.ref('mrp.mrp_production_action').read()[0]
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action


    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     """
    #     Override search method to use AND logic between search terms,
    #     including computed fields like attribute_search.
    #     """
    #     new_args = []
    #     search_terms = []

    #     for domain in args:
    #         if isinstance(domain, (list, tuple)) and len(domain) == 3:
    #             field, operator, value = domain
    #             if field =='sale_id':
    #                 attrib=self.env['product.attribute.value'].search([('name', 'ilike', value)]).ids
    #                 search_terms.append(('product_id.product_template_attribute_value_ids.product_attribute_value_id', 'in', attrib))
    #             elif field =='purchase_id' :
    #                 search_terms.append(('id','in',self.getNormalTrace()))
    #             else:
    #                 new_args.append(domain)


    #            # [('id', 'in', latest_traces)]
    #         else:
    #             new_args.append(domain)

    #     # Combine search terms with AND (&) logic properly
    #     if search_terms:
    #         # Start with the first term
    #         combined_domain = [search_terms[0]]
    #         # For each next term, prepend an '&' and the new term
    #         for term in search_terms[1:]:
    #             combined_domain =combined_domain + [term]
    #         new_args += combined_domain  # extend, not append

        
    #     res= super(ProductionOrder, self).search(new_args, offset=offset, limit=limit, order=order, count=count)    
    #     return res

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order',
        domain="[('partner_id', '=', partner_id)]"
    )

class MrpProduction(models.Model):
    _inherit = 'mrp.production'
   # partner_id = fields.Many2one('res.partner', string='Customer')
    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order'
        #,domain="[('partner_id', '=', partner_id)]"
    )





            # otherwise keep partner_id as-is (user can fill it manually)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    production_order_ids = fields.Many2many(
        'production.order','rel_production__purchase','purchase_id','production_id',
         string='Production Orders'
       # ,domain="[('partner_id', '=', partner_id)]"
    )

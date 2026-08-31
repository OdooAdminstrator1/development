from odoo import api, fields, models, tools, Command
from collections import defaultdict
from datetime import date

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
    po_bom = fields.Many2one('mrp.bom', 'Bill of Materials',  ondelete="cascade", domain="[('product_id', '=', product_id)]")
    #mrp.bom

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
    sales_man = fields.Many2many('hr.employee','production_order_hr_employees_rel','production_id','employee_id', string='Sales man')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )
    expected_revenue = fields.Monetary(string='Expected Revenue', related='opportunity_id.expected_revenue',currency_field='currency_id',readonly=True,
                                      store=False,)
    
    total_invoiced_untaxed = fields.Float(
        string='Total Invoiced',
        compute='_compute_invoice_totals',
        store=False,
    )

    to_be_invoiced = fields.Float(
        string='To be invoiced',
        compute='_compute_invoice_totals',
        store=False,
    )
    
    total_paid_untaxed = fields.Float(
        string='Net Collected',
        compute='_compute_invoice_totals',
        store=False,
    )
    
    total_tax = fields.Float(
        string='Total Taxes',
        compute='_compute_invoice_totals',
        store=False,
    )

    total_paid = fields.Float(
        string='Total Collected',
        compute='_compute_invoice_totals',
        store=False,
    )

    remaining_val  = fields.Float(
        string='Remaining',
        compute='_compute_invoice_totals2',
        store=False,
    )
    total_due  = fields.Float(
        string='Total Due',
        compute='_compute_invoice_totals2',
        store=False,
    )
    old_due =fields.Float(
        string='Old Due',
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

    delivery_state = fields.Selection(
        [
            ('none', 'None'),
            ('partial', 'Partially'),
            ('total', 'Totally'),
        ],
        string='Delivery Status',
        compute='_compute_delivery_state',
        store=True,
        default='none'
    )
    remark = fields.Char(string='Remark')
    engineer = fields.Many2one('hr.employee', string='Engineer')

    def _compute_delivery_state(self):
        for order in self:

            # Condition 3: no sale orders or no products
            if not order.sale_ids or not order.product_ids:
                order.delivery_state = 'none'
                continue

            delivered_qty = defaultdict(float)

            # Collect delivered quantities from completed outgoing deliveries
            pickings = order.sale_ids.mapped('picking_ids').filtered(
                lambda p: p.state == 'done' and p.picking_type_id.code == 'outgoing'
            )

            for picking in pickings:
                for move in picking.move_ids:
                    delivered_qty[move.product_id.id] += move.quantity

            # If no delivered products
            if not delivered_qty:
                order.delivery_state = 'none'
                continue

            matched = 0
            fully_matched = 0

            for material in order.product_ids:
                product_id = material.product_id.id
                required_qty = material.qty
                delivered = delivered_qty.get(product_id, 0)

                if delivered > 0:
                    matched += 1

                    if delivered >= required_qty:
                        fully_matched += 1

            # No products matched
            if matched == 0:
                order.delivery_state = 'none'

            # All products fully delivered
            elif fully_matched == len(order.product_ids):
                order.delivery_state = 'total'

            # Some delivered but not all / insufficient qty
            else:
                order.delivery_state = 'partial'


    @api.depends('sale_ids')
    def _compute_invoice_totals(self):
        for record in self:
            # Get all sale orders linked to this production order
            sale_orders = self.env['sale.order'].search([
                ('production_order_id', '=', record.id)
            ])
            beginning_of_year = date(date.today().year, 1, 1)

            untaxed_sum = 0.0
            paid_untaxed_sum = 0.0
            tax_sum = 0.0
            paid_total = 0.0
            old_due = 0.0
            remaining_val=0

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

                    if  inv.date and inv.date < beginning_of_year and inv.amount_residual>0:
                        old_due+=inv.amount_untaxed

                    # Proportional paid amount (excl. tax)
                    if total != 0:
                        paid_proportion = (total - inv.amount_residual) / total
                        paid_untaxed_sum += untaxed * paid_proportion
                    # else: if total is zero, paid_untaxed remains unchanged
            remaining_val=untaxed_sum - paid_untaxed_sum
            record.total_invoiced_untaxed = untaxed_sum
            record.to_be_invoiced =record.opportunity_id.expected_revenue - untaxed_sum
            record.total_paid_untaxed = paid_untaxed_sum
            record.total_paid = paid_total
            record.total_tax = tax_sum
            # record.total_due= record.expected_revenue - paid_untaxed_sum
            record.old_due = old_due
    
    @api.depends('total_invoiced_untaxed','total_paid_untaxed')
    def _compute_invoice_totals2(self):
        for rec in self:
            rec.remaining_val=rec.total_invoiced_untaxed-rec.total_paid_untaxed
            rec.total_due= record.expected_revenue - rec.total_paid_untaxed

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
    purchase_count = fields.Integer(string='Purchase Order Count', compute='_compute_purchase_count')

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

    @api.depends('purchase_ids')
    def _compute_purchase_count(self):
        for order in self:
            order.purchase_count = len(order.purchase_ids)
            

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

    def action_view_purchase_orders(self):
        domain = [('production_order_ids', '=', self.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase order',
            'res_model': 'purchase.order',
            'views': [ 
                (self.env.ref('purchase.purchase_order_view_tree').id, 'tree'),
                (self.env.ref('purchase.purchase_order_form').id, 'form'),
            ],
            'domain': domain,
        }


    def action_group_by_quarter(self):
        # Find the ID of the summary view we created in XML
        # Replace 'your_module_name' with the actual technical name of your module
        view_id = self.env.ref('production_order.view_production_order_summary_tree').id

        return {
            'name': 'Quarterly Aggregation',
            'type': 'ir.actions.act_window',
            'res_model': 'production.order',
            'view_mode': 'tree',
            'views': [(view_id, 'tree')],
            'context': {
                # This forces the grouping by Year and Quarter
                'group_by': 'adopted_date:quarter'
            },
            # 'current' replaces the screen, 'new' would open a pop-up dialog
            'target': 'current', 
        }
    
    row_materials_html = fields.Html(
        string='Raw Materials', 
        compute='_compute_row_materials_html'
    )
    row_needed_materials_html = fields.Html(
        string='unavailable RM', 
        compute='_compute_row_materials_html'
    )

    @api.depends(
        'product_ids',
        'product_ids.qty',
        'product_ids.po_bom',
        'product_ids.po_bom.bom_line_ids',
        'product_ids.po_bom.bom_line_ids.product_id',
        'product_ids.po_bom.bom_line_ids.product_qty',
    )
    def _compute_row_materials_html(self):
        for order in self:
            needed = {}
            for finished_line in order.product_ids:
                bom = finished_line.po_bom
                if not bom:
                    continue
                finished_qty = finished_line.qty or 0.0
                done_qty=0
                for manf_order in order.mrp_production_ids:
                    if manf_order.product_id.id==finished_line.product_id.id and manf_order.state=='done':
                        done_qty=done_qty+manf_order.product_qty
                 
                finished_qty=finished_qty-(done_qty or 0)
                if finished_qty<0:
                    finished_qty=0
                for bom_line in bom.bom_line_ids:
                    component = bom_line.product_id
                    component_qty_per_unit = bom_line.product_qty
                    total = finished_qty * component_qty_per_unit
                    needed[component] = needed.get(component, 0.0) + total

            # Build an Odoo-styled Bootstrap table
            html_content = """
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Needed Quantity</th>
                            <th>Quantity On Hand</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            html_content2 = """
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Needed Quantity</th>
                            <th>Quantity On Hand</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for component, needed_qty in needed.items():
                qty_on_hand = component.qty_available
                # Optional: Highlight row in red if we don't have enough stock
                row_style = "color: red;" 
                if qty_on_hand >= needed_qty :
                    html_content += f"""
                            <tr>
                                <td>{component.display_name}</td>
                                <td>{needed_qty}</td>
                                <td>{qty_on_hand}</td>
                            </tr>
                    """
                else:
                    html_content2 += f"""
                            <tr style="{row_style}">
                                <td>{component.display_name}</td>
                                <td>{needed_qty}</td>
                                <td>{qty_on_hand}</td>
                            </tr>
                    """

            
            html_content += """
                    </tbody>
                </table>
            """
            html_content2 += """
                    </tbody>
                </table>
            """
            order.row_materials_html = html_content
            order.row_needed_materials_html = html_content2


##### """

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
        string='Production Order',
       

    )





            # otherwise keep partner_id as-is (user can fill it manually)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    production_order_ids = fields.Many2many(
        'production.order','rel_production__purchase','purchase_id','production_id',
         string='Production Orders'
       # ,domain="[('partner_id', '=', partner_id)]"
    )

class ProductionOrderRawMaterial(models.Model):
    _name = 'production.order.raw.material'
    _description = 'Raw Material Requirement'
    _auto = False               # no database table – records live only in cache

    production_order_id = fields.Many2one(
        'production.order', string='Production Order',
    )
    product_id_row = fields.Many2one(
        'product.product', string='Component', required=True,
    )
    needed_quantity = fields.Float(
        'Needed Quantity', digits='Product Unit of Measure',
    )
    quantity_on_hand = fields.Float(
        'Quantity On Hand', digits='Product Unit of Measure',
    )

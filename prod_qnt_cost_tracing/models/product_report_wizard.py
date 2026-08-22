from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta

class ProductReportWizard(models.TransientModel):
    _name = 'product.report.wizard'
    _description = 'Product Report Filter'

    period = fields.Selection(
        selection=[
            ('current_fy', 'From Date'),           
             ('no_constraint', 'Openning - Too Aged'),
        ],
        string='Period',
        default='current_fy',
        required=True
    )
    from_date = fields.Date('Date',default=lambda self: date(date.today().year, 1, 1))

    def action_show_products(self):
        """Called by the 'Show Products' button. Returns an action to open the product list view."""
        
        # Step 1: Determine the date range based on selection
        date_from = False
        # date_to = False
        # company = self.env.company

        if self.period == 'current_fy':
            # fy_dates = company.compute_fiscalyear_dates(date.today())
            date_from = self.from_date
            # date_to = fy_dates['date_to']
        
        # elif self.period == 'current_last_fy':
        #     # Current year
        #     fy_dates_current = company.compute_fiscalyear_dates(date.today())
        #     date_from = fy_dates_current['date_from']
        #     date_to = fy_dates_current['date_to']
            
            # # Previous year (compute fiscal year for a date exactly 1 year ago)
            # last_year_date = date.today() - relativedelta(years=1)
            # fy_dates_previous = company.compute_fiscalyear_dates(last_year_date)
            
            # # Override date_from to the start of the previous year
            # date_from = fy_dates_previous['date_from']
            # # date_to remains the end of the current year
        

        # 1. Find all stock.valuation.layer records linked to an account.move
        #    whose ref starts with 'Opening Inv'.
        move_domain = [
            '|',  # OR condition
                ('picking_id.picking_type_code', '=', 'outgoing'),  # Receipts
                ('raw_material_production_id', '!=', False),       # Component in a Manufacturing Order[reference:2]
        ]
        moves = self.env['stock.move'].search(move_domain)
        
        valuation_domain = [
            ('stock_move_id', 'in', moves.ids),
            ('account_move_id', '!=', False),
        ]

        
        opening_layers = self.env['stock.valuation.layer'].search(valuation_domain)
        outgoing_or_man_product_ids = opening_layers.mapped('product_id').ids
        
        all_layer= self.env['stock.valuation.layer'].search([])
        all_products=all_layer.mapped('product_id').ids

        opening_layers_opening = self.env['stock.valuation.layer'].search([('account_move_id.ref', 'not like', 'Opening Inv%')])
        opening_products= opening_layers_opening.mapped('product_id').ids
        # final_product_ids = list(set(opening_product_ids) - set(non_opening_product_ids))
        final_list_no_out_manf_set=set(all_products)-set(outgoing_or_man_product_ids)-set(opening_products)
        

        
        finished_categ = self.env.ref('mrp.product_category_finished', raise_if_not_found=False)
        if not finished_categ:
            finished_categ = self.env['product.category'].search([
                ('name', '=', 'Finished Product')
            ], limit=1)
            
        product_domain = [('categ_id', '!=', finished_categ.id),('detailed_type','=','product'),('qty_available', '>=', 1)]
        if date_from :
            account_moves = self.env['account.move'].search([
                ('date', '>=', date_from),
            ])
            valuation_domain=[('account_move_id', 'in', account_moves.ids),('stock_move_id', '!=', False)]
            valuation_layers_obj = self.env['stock.valuation.layer'].search(valuation_domain)
            all_p=(valuation_layers_obj.mapped("product_id")).ids
            valuation_domain_f=[('account_move_id', 'in', account_moves.ids),('stock_move_id', 'in', moves.ids)]
            valuation_layers_obj = self.env['stock.valuation.layer'].search(valuation_domain_f)
            p_outgoing_manuf=(valuation_layers_obj.mapped("product_id")).ids
            included_product_ids=list(set(all_p)-set(p_outgoing_manuf)-final_list_no_out_manf_set)
            product_domain.append(('id', 'in', included_product_ids))
        else:
            product_domain.append(('id', 'in', list(final_list_no_out_manf_set)))

        # 5. Return the action to open the product list view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Aged Products',
            'res_model': 'product.product',
            'order' : 'value desc',
            'view_mode': 'tree',
            'views' : [
                (self.env.ref('prod_qnt_cost_tracing.view_product_product_aged_tree').id, 'tree'),
                (self.env.ref('product.product_normal_form_view').id, 'form')
            ],
         #   'view_id': self.env.ref('prod_qnt_cost_tracing.view_product_product_aged_tree').id,
            'domain': product_domain,
            'context': self.env.context,
        }



class ProductProduct(models.Model):
    _inherit = 'product.product'

    value = fields.Float(
        string='Stock Value',
        compute='_compute_value',
        store=True,
    )
    nb_in = fields.Integer(string="In /Nb",compute="_compute_numbers",store=False)
    total_in_aged = fields.Integer(string="Total In",compute="_compute_numbers",store=False)
    nb_out = fields.Integer(string="Out /Nb",compute="_compute_numbers",store=False)
    total_out_aged = fields.Integer(string="Total out",compute="_compute_numbers",store=False)

    @api.depends('standard_price', 'qty_available')
    def _compute_value(self):
        for product in self:
            product.value = product.standard_price * product.qty_available

    def _compute_numbers(self):
        for product in self:
            self.env.cr.execute("SELECT COUNT(*), SUM(qty_new) FROM stock_product_trace WHERE stock_move_type in ('preceipt') and product_id = "+str(product.id))
            count, total = self.env.cr.fetchone()
            product.nb_in=count
            product.total_in_aged=total
            self.env.cr.execute("SELECT COUNT(*), SUM(qty_new) FROM stock_product_trace WHERE stock_move_type in ('sdeliver','manufacturing_raw') and product_id = "+str(product.id))
            count, total = self.env.cr.fetchone()
            product.nb_out=count
            product.total_out_aged=total

    def _compute_quantities(self):
        super()._compute_quantities()
        # qty_available is not stored, so we update `value` manually
        # after stock quantities are recomputed.
        self._compute_value()
from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta

class ProductReportWizard(models.TransientModel):
    _name = 'product.report.wizard'
    _description = 'Product Report Filter'

    period = fields.Selection(
        selection=[
             ('no_constraint', 'Openning - Too Aged'),
            ('current_fy', 'Current Financial Year'),
            ('current_last_fy', 'Current + Last Financial Year'),
           
        ],
        string='Period',
        default='current_fy',
        required=True
    )

    def action_show_products(self):
        """Called by the 'Show Products' button. Returns an action to open the product list view."""
        
        # Step 1: Determine the date range based on selection
        date_from = False
        date_to = False
        company = self.env.company

        if self.period == 'current_fy':
            fy_dates = company.compute_fiscalyear_dates(date.today())
            date_from = fy_dates['date_from']
            date_to = fy_dates['date_to']
        
        elif self.period == 'current_last_fy':
            # Current year
            fy_dates_current = company.compute_fiscalyear_dates(date.today())
            date_from = fy_dates_current['date_from']
            date_to = fy_dates_current['date_to']
            
            # Previous year (compute fiscal year for a date exactly 1 year ago)
            last_year_date = date.today() - relativedelta(years=1)
            fy_dates_previous = company.compute_fiscalyear_dates(last_year_date)
            
            # Override date_from to the start of the previous year
            date_from = fy_dates_previous['date_from']
            # date_to remains the end of the current year
        
        elif self.period == 'no_constraint':
            # No date filter applied
            pass

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
        # final_product_ids = list(set(opening_product_ids) - set(non_opening_product_ids))
        final_list_no_out_manf=list(set(all_products)-set(outgoing_or_man_product_ids))
        

        
        finished_categ = self.env.ref('mrp.product_category_finished', raise_if_not_found=False)
        if not finished_categ:
            finished_categ = self.env['product.category'].search([
                ('name', '=', 'Finished Product')
            ], limit=1)
            
        # Step 2: Find all stock moves that are either Incoming or Manufacturing,
        # within the selected date range (if date constraints exist).
        # move_domain = [
        #     ('picking_id.picking_type_code', 'in', ['incoming', 'mrp_operation'])
        # ]

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
        if date_from and date_to:
            # We need to filter by the date of the related account.move
            # We'll do this in a subquery or by searching account.move separately
            # Since we can't directly filter valuation layers by account.move.date via domain,
            # we'll get account move IDs with the date range and then filter valuation layers.
            account_moves = self.env['account.move'].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            if account_moves:
                valuation_domain.append(('account_move_id', 'in', account_moves.ids))
            else:
                # No account moves in the period, so no product should be excluded
                valuation_domain = [('id', '=', -1)]  # force empty result



            
        valuation_layers = self.env['stock.valuation.layer'].search(valuation_domain)

        # Get the product IDs from the related stock moves
        excluded_product_ids = valuation_layers.mapped('stock_move_id.product_id').ids


        # 4. Build the final domain: Only Finished Products, excluding those found
      #  product_domain = []
        product_domain = [('categ_id', '!=', finished_categ.id),('detailed_type','=','product'),('qty_available', '>=', 1)]
        if date_from and date_to:
            excluded_product_ids+= outgoing_or_man_product_ids
            product_domain.append(('id', 'not in', excluded_product_ids))
        else:
            product_domain.append(('id', 'in', final_list_no_out_manf))

        # 5. Return the action to open the product list view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Aged Products',
            'res_model': 'product.product',
            'view_mode': 'tree,form',
            'domain': product_domain,
            'context': self.env.context,
        }

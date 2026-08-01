from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta

class ProductReportWizard(models.TransientModel):
    _name = 'product.report.wizard'
    _description = 'Product Report Filter'

    period = fields.Selection(
        selection=[
            ('current_fy', 'Current Financial Year'),
            ('current_last_fy', 'Current + Last Financial Year'),
            ('no_constraint', 'No Constraint (All Time)'),
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

        # Step 2: Find all stock moves that are either Incoming or Manufacturing,
        # within the selected date range (if date constraints exist).
        move_domain = [
            ('picking_id.picking_type_code', 'in', ['incoming', 'mrp_operation'])
        ]
        
        if date_from and date_to:
            move_domain += [('date', '>=', date_from), ('date', '<=', date_to)]
        # If no date constraint, we just check moves of that type regardless of date.

        # Fetch all stock.move records matching the criteria
        moves = self.env['stock.move'].search(move_domain)
        
        # Get the IDs of products that HAVE such moves (these will be excluded)
        excluded_product_ids = moves.mapped('product_id').ids

        # Step 3: Build the domain for the final product list
        product_domain = []
        if excluded_product_ids:
            # Exclude products that had ANY manufacturing or receipt in the period
            product_domain = [('id', 'not in', excluded_product_ids)]
        # If excluded_product_ids is empty, no products are excluded (all products pass)

        # Step 4: Return the action to open the product list view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Products (No MFG/Receipt in period)',
            'res_model': 'product.product',
            'view_mode': 'tree,form',
            'domain': product_domain,
            'context': self.env.context,
        }

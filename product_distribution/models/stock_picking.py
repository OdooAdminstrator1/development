from odoo import models, fields,api
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    open_date_id = fields.Many2one('distribution.open.date', string='Open Date')
    distributor_id = fields.Many2one(
        'hr.employee', 
        string='Distributor', 
        domain="[('isdistributor', '=', True)]"
    )
    show_distribution_fields = fields.Boolean(
        compute='_compute_show_distribution_fields',
        store=False # Can be stored=True if you need it for search/domain purposes
    )


    def action_insert_product(self):
        self.ensure_one()

        # 1. Validation checks
        if not self.distributor_id:
            raise UserError("Please select a distributor/driver first.")
        
        if not self.location_dest_id:
            raise UserError("Please select a destination location first.")

        # Get the product list template from the vehicle/distributor configuration
        product_template = getattr(self.distributor_id, 'vehicle_id', False) and self.distributor_id.vehicle_id.product_list_id
        if not product_template:
            raise UserError("No product template list is configured for the selected distributor's vehicle.")

        # 2. Fetch template lines matching the template
        template_lines = self.env['list.template.line'].search([
            ('template_id', '=', product_template.id)
        ])

        if not template_lines:
            raise UserError("The product list template contains no lines.")

        # 3. Prepare values for creating new stock moves
        moves_vals = []
        for line in template_lines:
            product = line.product_id
            max_qty = line.max_quantity

            # 4. Calculate current stock quantity (current_quant) in the destination location
            # We search stock.quant for the product in the specific destination location
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', '=', self.location_dest_id.id)
            ])
            current_quant = sum(quants.mapped('quantity'))

            # 5. Compare current stock with max_quantity
            if current_quant >= max_qty:
                continue  # Do nothing if current stock meets or exceeds max quantity

            # Calculate the missing quantity needed
            missing_qty = max_qty - current_quant

            # 6. Build values for the stock.move line
            moves_vals.append({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': missing_qty,
                'product_uom': product.uom_id.id,
                'picking_id': self.id,
                'location_id': self.location_id.id,  # Source location of the picking
                'location_dest_id': self.location_dest_id.id,
            })

        # Create the moves if any products need to be added
        if moves_vals:
            self.env['stock.move'].create(moves_vals)

        return True

    # def action_insert_product(self):
    #     product_template_id=self.distributor_id.vehicle_id.product_list_id
    #     pass

    @api.depends('location_dest_id')
    def _compute_show_distribution_fields(self):
        # Get configured distribution locations from ir.config_parameter
        get_param = self.env['ir.config_parameter'].sudo().get_param
        param_value = get_param('product_distribution.distribution_location_ids', '')
        
        # Parse IDs from the config parameter (adjust based on how your config saves them)
        for picking in self:
            try:
                allowed_location_ids = [int(loc_id) for loc_id in param_value.split(',') if loc_id.strip()]
            except ValueError:
                allowed_location_ids = []

            if not picking.location_dest_id or not allowed_location_ids:
                picking.show_distribution_fields = False
                continue

            # Traverse up the location hierarchy to check parents
            current_loc = picking.location_dest_id
            found = False
            while current_loc:
                if current_loc.id in allowed_location_ids:
                    found = True
                    break
                current_loc = current_loc.location_id  # location_id points to the parent location

            picking.show_distribution_fields = found



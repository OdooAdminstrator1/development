from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # NOTE: field names must NOT start with 'default_' -- in res.config.settings that
    # prefix is reserved for ir.default fields (it is classified before config_parameter
    # and would raise "Field ... without attribute 'default_model'"). The config_parameter
    # keys keep the historical 'default_*' names so model/wizard helpers stay unchanged.

    # FIXED: Changed to plural '_ids' and REMOVED 'config_parameter' to let custom methods handle it safely
    distribution_location_ids = fields.Many2many(
        'stock.location',
        'res_config_settings_stock_distribution_location_rel',  # Explicit relation table name
        'config_id',
        'location_id',
        string="Distribution Locations",
        domain="[('usage', '=', 'view')]",
        help="Virtual (view) location that is the parent of every outlet location.",
    )

    # Location goods land in at run close; the master order ships from here.
    delivery_location_id = fields.Many2one(
        'stock.location',
        string="Delivery Location",
        domain="[('usage', '=', 'internal')]",
        config_parameter='product_distribution.default_delivery_location_id',  # FIXED: Fixed typo 'delevery' to 'delivery'
        help="Internal location that collects run-close transfers and from which the "
             "single master sale order ships to the general customer.",
    )

    # Customer used on the aggregated master sale order.
    general_customer_id = fields.Many2one(
        'res.partner',
        string="General Distribution Customer",
        config_parameter='product_distribution.default_general_customer_id',
        help="Partner used as the customer of the daily aggregated master sale order.",
    )


    @api.model
    def get_values(self):
        """Retrieve the comma-separated string of IDs from parameters and convert back to Many2many relation format"""
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        
        # FIXED: Key matches what is saved in set_values, and field names match pluralization
        location_ids_str = params.get_param('product_distribution.distribution_location_ids', '')
        if location_ids_str:
            # Convert string "1,2,3" back into an executable list of integers [1, 2, 3]
            location_ids = [int(x) for x in location_ids_str.split(',') if x.isdigit()]
            # Update transient dictionary using Odoo's standard Many2many command (6, 0, [IDs])
            res.update(distribution_location_ids=[(6, 0, location_ids)])
        return res

    def set_values(self):
        """Convert the selected Many2many recordset IDs into a single flat string to store in system parameters"""
        super(ResConfigSettings, self).set_values()
        # FIXED: Key matches what is fetched in get_values, and field names match pluralization
        location_ids_str = ','.join(map(str, self.distribution_location_ids.ids))
        self.env['ir.config_parameter'].sudo().set_param('product_distribution.distribution_location_ids', location_ids_str)






# from odoo import models, fields, api


# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'

#     # NOTE: field names must NOT start with 'default_' -- in res.config.settings that
#     # prefix is reserved for ir.default fields (it is classified before config_parameter
#     # and would raise "Field ... without attribute 'default_model'"). The config_parameter
#     # keys keep the historical 'default_*' names so model/wizard helpers stay unchanged.

#     # Virtual parent umbrella for outlets (all truck/shop internal locations live under it).
#     distribution_location_id = fields.Many2many(
#         'stock.location',
#         'res_config_settings_stock_distribution_location_rel',  # Explicit relation table name
#         'config_id',
#         'location_id',
#         string="Distribution Locations",
#         domain="[('usage', '=', 'view')]",
#         config_parameter='product_distribution.default_distribution_location_id',
#         help="Virtual (view) location that is the parent of every outlet location.",
#     )

#     # Location goods land in at run close; the master order ships from here.
#     delivery_location_id = fields.Many2one(
#         'stock.location',
#         string="Delivery Location",
#         domain="[('usage', '=', 'internal')]",
#         config_parameter='product_distribution.default_delevery_location_id',
#         help="Internal location that collects run-close transfers and from which the "
#              "single master sale order ships to the general customer.",
#     )

#     # Customer used on the aggregated master sale order.
#     general_customer_id = fields.Many2one(
#         'res.partner',
#         string="General Distribution Customer",
#         config_parameter='product_distribution.default_general_customer_id',
#         help="Partner used as the customer of the daily aggregated master sale order.",
#     )


#     @api.model
#     def get_values(self):
#         """Retrieve the comma-separated string of IDs from parameters and convert back to Many2many relation format"""
#         res = super(ResConfigSettings, self).get_values()
#         params = self.env['ir.config_parameter'].sudo()
        
#         location_ids_str = params.get_param('product_distribution.distribution_location_id', '')
#         if location_ids_str:
#             # Convert string "1,2,3" back into an executable list of integers [1, 2, 3]
#             location_ids = [int(x) for x in location_ids_str.split(',') if x.isdigit()]
#             # Update transient dictionary using Odoo's standard Many2many command (6, 0, [IDs])
#             res.update(distribution_location_id=[(6, 0, location_ids)])
#         return res

#     def set_values(self):
#         """Convert the selected Many2many recordset IDs into a single flat string to store in system parameters"""
#         super(ResConfigSettings, self).set_values()
#         # Join list of active IDs into a comma-separated format string, e.g., "1,2,4"
#         location_ids_str = ','.join(map(str, self.distribution_location_id.ids))
#         self.env['ir.config_parameter'].sudo().set_param('product_distribution.distribution_location_id', location_ids_str)

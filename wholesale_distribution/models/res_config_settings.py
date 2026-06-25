from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # NOTE: field names must NOT start with 'default_' -- in res.config.settings that
    # prefix is reserved for ir.default fields (it is classified before config_parameter
    # and would raise "Field ... without attribute 'default_model'"). The config_parameter
    # keys keep the historical 'default_*' names so model/wizard helpers stay unchanged.

    # Virtual parent umbrella for outlets (all truck/shop internal locations live under it).
    distribution_location_id = fields.Many2one(
        'stock.location',
        string="Distribution Umbrella Location",
        domain="[('usage', '=', 'view')]",
        config_parameter='wholesale_distribution.default_distribution_location_id',
        help="Virtual (view) location that is the parent of every outlet location.",
    )

    # Location goods land in at run close; the master order ships from here.
    delivery_location_id = fields.Many2one(
        'stock.location',
        string="Delivery Location",
        domain="[('usage', '=', 'internal')]",
        config_parameter='wholesale_distribution.default_delevery_location_id',
        help="Internal location that collects run-close transfers and from which the "
             "single master sale order ships to the general customer.",
    )

    # Customer used on the aggregated master sale order.
    general_customer_id = fields.Many2one(
        'res.partner',
        string="General Distribution Customer",
        config_parameter='wholesale_distribution.default_general_customer_id',
        help="Partner used as the customer of the daily aggregated master sale order.",
    )

    # Governance: who is allowed to OPEN a delivery run from the mobile API.
    distributor_can_open_run = fields.Boolean(
        string="Distributors Can Open Runs",
        config_parameter='wholesale_distribution.distributor_can_open_run',
        default=True,
        help="If enabled, a distributor may open a delivery run from the mobile app. "
             "If disabled, only a cashier/manager opens runs and the distributor simply "
             "receives the already-opened run for the outlet.",
    )

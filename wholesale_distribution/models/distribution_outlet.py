from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DistributionOutlet(models.Model):
    _name = 'distribution.outlet'
    _description = 'Distribution Outlet (Mobile Truck / Retail Shop)'
    _order = 'name'

    name = fields.Char(string="Outlet Name", required=True)
    active = fields.Boolean(default=True)

    # Configured umbrella (view) location; outlet locations must live under it.
    umbrella_location_id = fields.Many2one(
        'stock.location', compute='_compute_umbrella_location_id',
        string="Distribution Umbrella Location",
    )
    location_id = fields.Many2one(
        'stock.location',
        string="Outlet Stock Location",
        required=True,
        domain="[('usage', '=', 'internal'), ('id', 'child_of', umbrella_location_id)]"
               " if umbrella_location_id else [('usage', '=', 'internal')]",
        help="Internal stock location representing the physical outlet (truck or shop). "
             "It must be a child of the configured distribution umbrella location.",
    )

    distribution_type = fields.Selection(
        selection=[
            ('truck', 'Mobile Outlet (Truck)'),
            ('shop', 'Retail Outlet (Shop)'),
        ],
        string="Outlet Type",
        required=True,
        default='truck',
    )

    # Fleet (truck) details -- restricted to managers in the views.
    truck_name = fields.Char(string="Truck Name")
    truck_number = fields.Char(string="Truck Plate Number")

    # Shop details.
    shop_address = fields.Char(string="Shop Address")

    distribution_department_id = fields.Many2one(
        'hr.department', compute='_compute_distribution_department_id',
        help="The Distribution department; used to filter the default distributer.",
    )
    default_distributer_id = fields.Many2one(
        'hr.employee',
        string="Default Distributer",
        domain="[('department_id', '=', distribution_department_id)]",
        help="Distributer (employee of the Distribution department) assigned to this outlet. "
             "The mobile API derives the outlet from the authenticated distributer's portal "
             "token through this employee's user, so the distributer never needs to know the "
             "outlet id.",
    )

    @api.depends_context('uid')
    def _compute_distribution_department_id(self):
        department = self.env.ref(
            'wholesale_distribution.department_distribution', raise_if_not_found=False)
        for outlet in self:
            outlet.distribution_department_id = department.id if department else False

    @api.depends_context('uid')
    def _compute_umbrella_location_id(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'wholesale_distribution.default_distribution_location_id')
        location = self.env['stock.location'].browse(int(value)) if value else self.env['stock.location']
        umbrella = location if location.exists() else self.env['stock.location']
        for outlet in self:
            outlet.umbrella_location_id = umbrella.id

    @api.constrains('location_id')
    def _check_location_under_umbrella(self):
        for outlet in self:
            umbrella = outlet.umbrella_location_id
            if umbrella and outlet.location_id not in self.env['stock.location'].search(
                    [('id', 'child_of', umbrella.id)]):
                raise ValidationError(_(
                    "Outlet Stock Location must be a child of the distribution umbrella "
                    "location (%s).", umbrella.display_name))

    @api.constrains('distribution_type', 'truck_name', 'truck_number', 'shop_address')
    def _check_required_by_type(self):
        for outlet in self:
            if outlet.distribution_type == 'truck' and not (outlet.truck_name and outlet.truck_number):
                raise ValidationError(_(
                    "Truck Name and Truck Plate Number are required for a Mobile Outlet (Truck)."))
            if outlet.distribution_type == 'shop' and not outlet.shop_address:
                raise ValidationError(_(
                    "Shop Address is required for a Retail Outlet (Shop)."))

from odoo import models, fields,api
from werkzeug.security import generate_password_hash, check_password_hash

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    isdistributor = fields.Boolean(string='Is Distributor', default=False)
    distribution_region_id = fields.Many2one('distribution.region', string='Region')
    vehicle_id = fields.Many2one('distribution.vehicle', string='Vehicle')
    distributor_status = fields.Boolean(string='Status (Activated)', default=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Price List')
    emp_code=fields.Char('Distributor code')
    emp_password = fields.Char(
        string='Distributor Password',
        copy=False,  # Prevent password from copying during record duplication
       # groups='hr.group_hr_user',  # Restrict field access to HR admins
    )
    vehicle_location_id = fields.Many2one(
        'stock.location',
        related='vehicle_id.location_id',
        string='Vehicle Location',
        readonly=True,          # automatically follows the vehicle's location
        store=False             # set to True if you need to search/group on it frequently
    )


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('emp_password'):
                vals['emp_password'] = generate_password_hash(vals['emp_password'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('emp_password'):
            vals['emp_password'] = generate_password_hash(vals['emp_password'])
        return super().write(vals)

    def check_emp_password(self, password):
        """Helper method to authenticate/check plain text password against stored hash."""
        self.ensure_one()
        if not self.emp_password:
            return False
        return check_password_hash(self.emp_password, password)
    
    def authenticate_by_code(self, emp_code, password):
        """
        Validates an employee using distributor code and plain-text password.
        
        :param emp_code: str - The distributor code (emp_code)
        :param password: str - Plain-text password to check
        :return: str | False - Employee name if credentials match, else False
        """
        if not emp_code or not password:
            return False

        # Use sudo() in case the caller does not have full read access to hr.employee fields
        employee = self.sudo().search([('emp_code', '=', emp_code)], limit=1)

        if employee and employee.check_emp_password(password):
            rec=self.env['distribution.open.date.distributor'].search([('distributor_id.id','=',employee.id,),('open_date_id.status','!=','done'),('state','!=','done')], limit=1, order='id desc')
            if rec:
                return employee.id, employee.name,rec.open_date_id.id,rec.id

        return False
    
    def get_current_open_date(self,emp_id):
        rec=self.env['distribution.open.date.distributor'].search([('distributor_id.id','=',emp_id),('open_date_id.status','!=','done'),('state','!=','done')], limit=1, order='id desc')
        if len(rec):
            return rec
        else:
            return False
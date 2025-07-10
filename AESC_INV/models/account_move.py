from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    job_no = fields.Char(string="Job No/Delivery Number")
    customer_ref = fields.Char(string="Customer Reference Number")
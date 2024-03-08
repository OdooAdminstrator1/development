from odoo import models, fields, api, _


class HrEmployeeInherited(models.Model):
    _inherit = 'hr.employee'

    emp_sale_team_id = fields.Many2one('crm.team')
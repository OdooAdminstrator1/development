from odoo import fields, models


class ResConfigSettingsInhertiedHR(models.TransientModel):
    _inherit = 'res.config.settings'

    emps_vendor_id = fields.Many2one('res.partner',
                                      string='Vendor Of Payroll',
                                      config_parameter='aesp_overtime_hr.payroll_vendor')

from odoo import fields, models


class ResConfigSettingsInhertiedHR(models.TransientModel):
    _inherit = 'res.config.settings'

    vacation_per_month=fields.Float(string="Vacation Deserved per Month",config_parameter='hr_paid_dayoff.vacation_per_month')
    startup_date=fields.Datetime(string="Application Start Date",config_parameter='hr_paid_dayoff.startup_date')
    emps_vac_vendor_id = fields.Many2one('res.partner',
                                      string='Employee Vacation Vendor ',
                                      config_parameter='hr_paid_dayoff.emps_vac_vendor_id')


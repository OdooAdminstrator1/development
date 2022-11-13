from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OverheadProcedureAnalyticAccountLine(models.Model):
    _inherit = 'account.analytic.line'

    period_date = fields.Date(string='period date')

    @api.constrains('name', 'period_date')
    def check_period_date(self):
        oldest_opened_period = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')], order='date_start asc', limit=1)
        last_opened_period = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')], order='date_start desc', limit=1)
        for res in self:
            ict_analytic_account = self.env['ir.config_parameter'].sudo().get_param(
                'ict_overhead_expenses.ict_analytic_account')
            if res.account_id.id == int(ict_analytic_account) and not res.period_date:
                raise UserError('You have to define a period')

            if res.period_date and res.account_id and res.account_id.id == int(ict_analytic_account) \
                    and ((oldest_opened_period and oldest_opened_period.date_start > res.period_date) or
                         (last_opened_period and last_opened_period.date_stop < res.period_date)):
                raise UserError(_('You Cannot Insert Analytic Item In Closed Or Not Opened Period'))

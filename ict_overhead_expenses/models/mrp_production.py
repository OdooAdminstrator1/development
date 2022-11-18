from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError


class IctOverheadExpensesMrpProduction(models.Model):
    _inherit = 'mrp.production'

    sapps_is_real_time = fields.Boolean(string="Is Real Time", compute="_compute_is_real_time")
    costing_date = fields.Date(string='Costing Date')

    def _compute_is_real_time(self):
        for res in self:
            res.sapps_is_real_time = bool(
                self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))

    def _post_inventory(self, cancel_backorder=False):
        to_finish = False
        cost_date = False
        for order in self:
            to_finish = order.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))

            # check period is opened
            last_opened_period = self.env['ict_overhead_expenses.period'].search(
                [('state', '=', 'open')], order='date_start desc', limit=1)
            first_opened_period = self.env['ict_overhead_expenses.period'].search(
                [('state', '=', 'open')], order='date_start asc', limit=1)
            order._compute_is_real_time()
            if not order.sapps_is_real_time:
                if (order.bom_id.finishing_product_ok) and (not order.costing_date):
                    raise UserError(_('You should assign a costing date to all produced serials'))
                if (order.bom_id.finishing_product_ok) \
                        and (order.costing_date > last_opened_period.date_stop or order.costing_date < first_opened_period.date_start):
                    raise UserError(_('Please Insure that the current period is opened'))
                cost_date = order.costing_date
            else:
                if order.bom_id.finishing_product_ok :
                    if fields.date.today() > last_opened_period.date_stop or fields.date.today() < first_opened_period.date_start:
                        raise UserError(_('Please Insure that the current period is opened'))
                cost_date = fields.date.today()

        res = super(IctOverheadExpensesMrpProduction, self)._post_inventory(cancel_backorder)
        if to_finish:
            for f in to_finish.move_line_ids:
                f.cost_date = cost_date
        return res
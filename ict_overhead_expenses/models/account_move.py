from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OverheadProcedureAccountMove(models.Model):
    _inherit = 'account.move'

    sapps_is_real_time = fields.Boolean(string="Is Real Time", compute="_compute_is_real_time")

    def _compute_is_real_time(self):
        for res in self:
            res.sapps_is_real_time = bool(
                self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))

    # prevent reset to draft on journals already posted to closed period
    def button_draft(self):
        for elem in self:
            if any(item.product_cost_item_ok or item.is_overhead_journal for item in elem.line_ids):
                oldest_opened_period = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')],
                                                                                       order='date_start asc', limit=1)
                for line in elem.line_ids:
                    if oldest_opened_period and line.period_opened and oldest_opened_period.date_start > line.period_opened.date_stop:
                        raise UserError("You Cannot Reset A Costing Journal Already Posted To Closed Period")
        
        return super(OverheadProcedureAccountMove, self).button_draft()


class OverheadProcedureAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    period = fields.Selection(selection=[
        ('oldest', 'Oldest Period Not Closed'),
        ('first_next', 'Next Period 1'),
        ('second_next', 'Next Period 2')
    ], string='period')
    product_cost_item_ok = fields.Boolean(related='product_id.costing_item_ok')
    is_costing_jv = fields.Boolean('Is Costing', default=False)
    transfer_journal_cost = fields.Boolean("Transfer Journal Cost", default=False)
    is_overhead_journal = fields.Boolean('Is Overhead', compute='_compute_is_overhead_journal')
    created_by_user = fields.Boolean('created by user', default=False)
    overhead_container_account_id = fields.Integer('overhead', compute='compute_overhead_conatiner_id')
    parent_type = fields.Char('parent journal type', compute='_compute_aprent_journal_type')
    period_opened = fields.Many2one('ict_overhead_expenses.period', string="Period",  domain=[('state', '=', 'open')])
    sapps_is_real_time = fields.Boolean(string="Is Real Time", compute="_compute_is_real_time")

    def _compute_is_real_time(self):
        for res in self:
            res.sapps_is_real_time = bool(
                self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.sapps_is_real_time'))

    @api.depends('created_by_user')
    def _compute_aprent_journal_type(self):
        for res in self:
            res.parent_type = res.move_id.move_type

    @api.depends('is_overhead_journal')
    def compute_overhead_conatiner_id(self):
        for res in self:
            id = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_account'))
            res.overhead_container_account_id = id

    @api.depends('product_id', 'account_id', 'debit','is_costing_jv')
    def _compute_is_overhead_journal(self):
        # ict_rest_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
        #     'ict_overhead_expenses.ict_rest_account_id'))
        # analytic_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
        #         'ict_overhead_expenses.ict_analytic_account'))
        for res in self:
            if res.product_cost_item_ok:
                res.is_overhead_journal = True
            elif res.transfer_journal_cost:
                res.is_overhead_journal = True
            elif res.is_costing_jv and res.created_by_user and not res.product_id:
                res.is_overhead_journal = True
                res.onchange_product()
            else:
                res.is_overhead_journal = False

    @api.onchange('product_id', 'account_id','is_overhead_journal')
    def onchange_product(self):
        ict_rest_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_rest_account_id'))
        id = int(self.env['ir.config_parameter'].sudo().get_param('ict_overhead_expenses.ict_analytic_account'))
        overhead_container_account = self.env['account.analytic.account'].search([('id', '=', id)], limit=1)
        for res in self:
            if not res.is_overhead_journal:
                # res.period_opened = self.env['ict_overhead_expenses.period'].search([('state', '=', 'open')],
                #                                                             order='date_stop asc')[0] \
                #     if not res.period_opened else res.period_opened
                res.period_opened = False
                if res.analytic_account_id.id == res.overhead_container_account_id:
                    res.analytic_account_id = False
            else:
                res.analytic_account_id = overhead_container_account
                res.period_opened = self.env['ict_overhead_expenses.period'
                ].search([('state', '=', 'open')],
                         order='date_stop asc')[0] if not res.period_opened else res.period_opened

            res._compute_is_real_time()

            if res.sapps_is_real_time:
                res.period_opened = False

    @api.constrains('date')
    def check_costing_items(self):
        ict_analytic_account = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_analytic_account'))
        for res in self:
            res._compute_is_overhead_journal()
            if res.is_overhead_journal:
                res._compute_is_real_time()
                if not res.sapps_is_real_time and (not res.analytic_account_id or not res.period_opened or res.analytic_account_id.id != ict_analytic_account):
                    raise UserError(_('costing item must have the analytic account defined in setting and period is required'))
                if res.sapps_is_real_time:
                    period = self.env['ict_overhead_expenses.period'].search([('date_start', '<=', res.date),
                                                                              ('date_stop', '>=', res.date),
                                                                              ('state', '=', 'open')
                                                                              ], limit=1)
                    if not period:
                        raise UserError("Please Insure that the current period is opened")
                    res.period_opened = period.id

    def _prepare_analytic_line(self):
        elements = []
        ict_analytic_account = int(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_analytic_account'))
        for move_line in self:
            result = super(OverheadProcedureAccountMoveLine, move_line)._prepare_analytic_line()
            if move_line.is_overhead_journal:
                for r in result:
                    if move_line.sapps_is_real_time:
                        period = self.env['ict_overhead_expenses.period'].search([('date_start', '<=', move_line.date),
                                                                                  ('date_stop', '>=', move_line.date),
                                                                                  ('state', '=', 'open')
                                                                                  ], limit=1)
                        if not period:
                            raise UserError("Please Insure that the current period is opened")
                        r['period_date'] = str(period.date_stop)
                    elif not move_line.period_opened.date_stop:
                        raise UserError(_('Please Select Period for all overhead lines'))
                    else:
                        r['period_date'] = str(move_line.period_opened.date_stop)
            elements = elements + result
        return elements
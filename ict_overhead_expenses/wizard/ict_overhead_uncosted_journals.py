from odoo import api, fields, models, _
from odoo.exceptions import UserError
import xlwt
import base64
from io import BytesIO

import datetime
class ICTOverheadUncostedJournalsWizard(models.TransientModel):
    _name = 'ict_overhead.uncosted_journals'

    start_date = fields.Date('start date')
    end_date = fields.Date('end date')
    res_account_id = fields.Many2one('account.account',string='Rest Account')
    file_name = fields.Binary(string='File Name', readonly=True)
    summary_data = fields.Char('Name', size=256)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')

    # def process_overhead_any_way(self):
    #     res = self.with_context(process_any_way=True).env['ict_overhead_expenses.procedure.log'].create({})
    #     return {"type": "ir.actions.client", "tag": "reload"}

    def create(self, vals):
        res = super(ICTOverheadUncostedJournalsWizard, self).create(vals)
        lines = self.env['account.move.line'].search([('company_id', '=', self.env.company.id),
                                                      ('move_id.state', '!=', 'cancel'),
                                                      ('move_id.type', '=', 'entry'),
                                                      ('account_id', '=', res.res_account_id.id),
                                                      ('debit', '>', 0),
                                                      ('is_costing_jv', '=', False),
                                                      ('created_by_user', '=', True),
                                                      ])
        # company_name = self.company_id.name
        file_name = 'Journal_items.xls'
        workbook = xlwt.Workbook(encoding="UTF-8")
        format0 = xlwt.easyxf(
            'font:height 500,bold True;pattern: pattern solid, fore_colour gray25;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black,\
                              left thin, right thin, top thin, bottom thin;')
        formathead2 = xlwt.easyxf(
            'font:height 250,bold True;pattern: pattern solid, fore_colour gray25;align: horiz center; borders: top_color black, bottom_color black, right_color black, left_color black,\
                              left thin, right thin, top thin, bottom thin;')
        format1 = xlwt.easyxf('font:bold True;pattern: pattern solid, fore_colour gray25;align: horiz left; borders: top_color black, bottom_color black, right_color black, left_color black,\
                                     left thin, right thin, top thin, bottom thin;')
        format2 = xlwt.easyxf('font:bold True;align: horiz left;pattern: pattern solid, fore_colour yellow')
        format3 = xlwt.easyxf('align: horiz left; borders: top_color black, bottom_color black, right_color black, left_color black,\
                                     left thin, right thin, top thin, bottom thin;')
        sheet = workbook.add_sheet("Journal Items")
        sheet.col(0).width = int(7 * 260)
        sheet.col(1).width = int(30 * 260)
        sheet.col(2).width = int(40 * 260)
        sheet.col(3).width = int(20 * 260)
        sheet.row(0).height_mismatch = True
        sheet.row(0).height = 150 * 4
        sheet.row(1).height_mismatch = True
        sheet.row(1).height = 150 * 2
        sheet.row(2).height_mismatch = True
        sheet.row(2).height = 150 * 3
        sheet.write_merge(0, 0, 0, 13, 'Journal Items', format0)
        sheet.write(1, 0, 'Company', format1)
        sheet.write(1, 1, 'Date', format1)
        sheet.write(1, 2, 'Journal', format1)
        sheet.write(1, 3, 'Journal Entry', format1)
        sheet.write(1, 4, 'Account', format1)
        sheet.write(1, 5, 'Ref', format1)
        sheet.write(1, 6, 'Label', format1)
        sheet.write(1, 7, 'Credit', format1)
        sheet.write(1, 8, 'Debit', format1)
        sheet.write(1, 9, 'Amount Currency', format1)
        index = 2
        for line in lines:
            sheet.write(index, 0, line.company_id.name)
            sheet.write(index, 1, line.date)
            sheet.write(index, 2, line.journal_id.name)
            sheet.write(index, 3, line.move_id.name)
            sheet.write(index, 4, line.account_id.name)
            sheet.write(index, 5, line.ref)
            sheet.write(index, 6, line.name)
            sheet.write(index, 7, line.credit)
            sheet.write(index, 8, line.debit)
            sheet.write(index, 9, line.amount_currency)
            index = index + 1

        fp = BytesIO()
        workbook.save(fp)
        res.write(
            {'state': 'get', 'file_name': base64.encodestring(fp.getvalue()), 'summary_data': file_name})
        fp.close()
        return res
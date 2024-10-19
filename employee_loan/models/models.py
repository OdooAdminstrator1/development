import calendar

from odoo import models, fields, api, _
import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError

class AccountPaymentRegister(models.Model):
    _inherit = 'account.payment'

    loan_id = fields.One2many('hr.loan',inverse_name='payment_id')

    def action_post(self):
        if self.loan_id:
            self.loan_id.state= 'delivered'
        return super().action_post()


class HrLoan(models.Model):
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    @api.model
    def default_get(self, field_list):
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            ts_user_id = result['user_id']
        else:
            ts_user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search([('user_id', '=', ts_user_id)], limit=1).id
        return result

    def _compute_loan_amount(self):
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_lines:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid

            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid
            if  balance_amount==0:
                loan.state='refunded'

    def _compute_loan_rest_installment(self):
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_lines:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid
            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid

    name = fields.Char(string="Loan Name", default="/", readonly=True, help="Name of the loan")
    date = fields.Date(string="Delivery Date", default=fields.Date.today(), help="Date")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, help="Employee")
    rest_installment = fields.Integer(string="Rest Installments", default=1,compute='_compute_loan_rest_installment')
    installment = fields.Integer(string="No Of Installments",readonly=True, default=1, help="Number of installments")
    loan_lines = fields.One2many('hr.loan.line', 'loan_id', string="Loan Line",readonly=True, index=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, help="Company",
                                 default=lambda self: self.env.user.company_id,
                                 states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, help="Currency",
                                  default=lambda self: self.env.user.company_id.currency_id)
    installment_amount = fields.Integer(string="Installment Amount", readonly=True)
    last_installment_amount = fields.Integer(string="Installment Amount",readonly=True)
    loan_amount = fields.Float(string="Loan Amount", required=True, help="Loan amount")
    balance_amount = fields.Float(string="Balance Amount", store=True, compute='_compute_loan_amount', help="Balance amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True, compute='_compute_loan_amount',
                                     help="Total paid amount")

    start_refund_year = fields.Char( default=lambda self: fields.Date.today().year)
    start_refund_month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], default=lambda self: str((fields.Date.today() + relativedelta(months=+1)).month))

    apply_this_month= fields.Boolean(default=True)
    apply_month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], default=lambda self: str((fields.Date.today() + relativedelta(months=+1)).month))

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('cancel', 'Canceled'),
        ('delivered','Delivered'),
        ('refunded','Refunded'),
    ], string="State", default='draft', tracking=True, copy=False, )

    payment_id = fields.Many2one('account.payment')

    @api.model
    def create(self, values):

        values['name'] = self.env['ir.sequence'].get('hr.loan.seq') or ' '

        res = super(HrLoan, self).create(values)
        return res

    def compute_installment(self):
        """This automatically create the installment the employee need to pay to
        company based on payment start date and the no of installments.
            """
        for loan in self:
            loan.loan_lines.unlink()
            last_day = calendar.monthrange(int(loan.start_refund_year),int( loan.start_refund_month))[1]

            date_start = datetime.date(int(loan.start_refund_year),int( loan.start_refund_month), last_day)
            amount =round(loan.loan_amount / loan.installment, -2)
            last_amount=  loan.loan_amount-amount *(loan.installment-1)

            for i in range(1, loan.installment ):

                self.env['hr.loan.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
                last_day = calendar.monthrange(date_start.year, date_start.month)[1]

                date_start = datetime.date(date_start.year, date_start.month, last_day)


            self.env['hr.loan.line'].create({
                'date': date_start,
                'amount': last_amount,
                'employee_id': loan.employee_id.id,
                'loan_id': loan.id})

            loan._compute_loan_amount()
            loan.installment_amount = amount
        return True


    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_submit(self):
        self.write({'state': 'submit'})
        if self.loan_lines == False:
            self.compute_installment()

    def action_show_payment(self):
        self.ensure_one()
        return {
            'view_mode': 'form',
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.payment_id.id,
        }
    def action_create_payment(self):

        if not self.employee_id.customer_id:
            m= {
                'name': _('Register Payment'),
                'res_model': 'account.payment',
                'view_mode': 'form',
                'context': {

                    'default_amount': self.loan_amount,
                    'default_partner_id': self.env['res.partner'].create(
                        {'name': self.employee_id.name, 'company_id': self.company_id.id}).id,
                    'default_company_id': self.company_id.id,
                    'default_payment_type': 'outbound',
                    'default_partner_type': 'customer',
                    'default_date': self.date,
                    'default_loan_id': [(4,self.id)]

                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
            self.employee_id.customer_id = m['context']['default_partner_id']
            return  m

        else:
            p_id = self.employee_id.customer_id.id
            return {
                'name': _('Register Payment'),
                'res_model': 'account.payment',
                'view_mode': 'form',
                'context': {

                    'default_amount': self.loan_amount,
                    'default_partner_id': p_id,
                    'default_company_id': self.company_id.id,
                    'default_payment_type': 'outbound',
                    'default_partner_type': 'customer',
                    'default_date': self.date,
                    'default_loan_id': [(4,self.id)]

                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }






    def unlink(self):
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a loan which is not in draft or cancelled state')
        return super(HrLoan, self).unlink()


class InstallmentLine(models.Model):
    _name = "hr.loan.line"
    _description = "Installment Line"

    date = fields.Date(string="Installment Date", required=True, help="Date of the payment" ,readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", help="Employee",readonly=True)
    amount = fields.Float(string="Amount", required=True, help="Amount",readonly=True)
    paid = fields.Boolean(string="Paid", help="Paid",readonly=True)
    active = fields.Boolean(string="Active" ,default=True)
    loan_id = fields.Many2one('hr.loan', string="Loan Ref.", help="Loan",readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string="Payslip Ref.", help="Payslip",readonly=True)
    is_first = fields.Boolean(compute='_compute_first',default=False)


    def _compute_first(self):
        lines = self.env['hr.loan.line'].search([('loan_id', '=', self.loan_id.id), ('active', '=', True), ('paid', '=', False)])
        lines2 = self.env['hr.loan.line'].search(
            [('loan_id', '=', self.loan_id.id),'|', ('active', '=', False), ('paid', '=', True)])
        for l in lines2:

                l.is_first = False

        dates = [record.date for record in lines if record.date]

        # إذا كانت القائمة تحتوي على تواريخ، نستخدم max() للحصول على التاريخ الأقصى
        if dates:
            min_date = min(dates)
        else:
            min_date = None
        for l in lines:
            if l.date == min_date:
                l.is_first = True
            else:
                l.is_first = False


    def action_notapplay(self):
        for line in self:
            if line.paid:
                continue
            if line.active==True:
                line.active=False
                lines=self.env['hr.loan.line'].search([('loan_id','=',line.loan_id.id),('date','>',line.date)])
                dates = [record.date for record in lines if record.date]

                # إذا كانت القائمة تحتوي على تواريخ، نستخدم max() للحصول على التاريخ الأقصى
                if dates:
                    max_date = max(dates)
                else:
                    max_date = None
                for l in lines:
                    if l.date == max_date:
                        amn= l.amount
                        l.amount= l.loan_id.installment_amount
                        last_day = calendar.monthrange(l.date.year, l.date.month)[1]

                        self.env['hr.loan.line'].create({
                            'date': datetime.date(l.date.year, l.date.month, last_day),
                            'amount': amn,
                            'employee_id': l.loan_id.employee_id.id,
                            'loan_id': l.loan_id.id})


    def action_applay(self):
        for line in self:
            if line.paid:
                continue

            if line.active==False:
                line.active = True
                lines=self.env['hr.loan.line'].search([('loan_id','=',line.loan_id.id),('date','>',line.date)])
                dates = [record.date for record in lines if record.date]


                if dates:
                    max_date = max(dates)
                else:
                    max_date = None
                for l in lines:
                    if l.date == max_date+ relativedelta(months=-1):
                        l.amount= l.loan_id.last_installment_amount
                    if l.date == max_date:
                        l.unlink()






class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _compute_employee_loans(self):
        """This compute the loan amount and total loans count of an employee.
            """
        self.loan_count = self.env['hr.loan'].search_count([('employee_id', '=', self.id)])

    loan_count = fields.Integer(string="Loan Count", compute='_compute_employee_loans')
    customer_id = fields.Many2one('res.partner')


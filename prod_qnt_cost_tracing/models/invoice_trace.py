from odoo import models, fields, tools

class InvoiceTrace(models.Model):
    _name = "invoice.trace.report"
    _description = "Invoice Tracing Analysis"
    _auto = False   # <-- Important: no automatic table creation

    id= fields.Integer(string='Internal Id', readonly=True)
    name= fields.Char(string='Invoice', readonly=True)
    date = fields.Date(string='Date', readonly=True)

    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    display_name = fields.Char('Name', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    invoice_origin = fields.Char(string='Origin', readonly=True)
    cost_unit_value = fields.Float('Unit Cost', currency_field='currency_id', readonly=True)
    cost_system = fields.Float('System cost', currency_field='currency_id')
    qty_done = fields.Float('Done Quantity', digits='Product Unit of Measure', readonly=True)
    qty_new = fields.Float('New Quantity', digits='Product Unit of Measure', readonly=True)




    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
Select row_number() OVER() AS id,M.name,M.date,M.journal_id,M.product_id,M.display_name,M.quantity,M.price_unit,M.currency_id,M.partner_id,M.amount_currency,M.invoice_origin ,
S.cost_unit_value,S.cost_new_value,S.cost_system,S.qty_done,S.qty_new,S.stock_move_type from
(
	SELECT  A.name, A.date,   A.journal_id, D.Product_id,D.name as display_name,D.price_total,D.quantity,D.price_unit,  
A.currency_id, A.partner_id,   A.amount_untaxed, A.amount_tax, D.amount_currency ,A.invoice_origin, A.move_type ,
  row_number() OVER(partition by D.product_id,D.move_id order by D.id ) AS product_sql,A.id as invoice_id
    
	FROM public.account_move as A inner join public.account_move_line as D
	on A.id =D.Move_id
	
	where A.move_type in ('out_invoice','out_refund')  and state='posted' and D.exclude_from_invoice_tab=False and d.tax_line_id is null 
	and d.display_type is null 
                         ) as M
	left join ( select A.*,
	row_number() OVER(partition by  A.ref_value,A.stock_move_type, 
    A.product_id order by A.id ) AS product_sql
	from stock_product_trace as A)  S 
    on M.invoice_origin=S.ref_value
    and M.product_id=S.product_id
    and M.product_sql=S.product_sql
    and ((M.move_type='out_invoice' and S.stock_move_type='sdeliver') 
        or (M.move_type='out_refund' and S.stock_move_type='sreturn') )
	where S.stock_move_type  is null
	order by M.invoice_id desc, M.product_sql asc
    )
        """ % self._table)

from odoo import models, fields, tools,api, _

class InvoiceDetailed(models.Model):
    _name = "invoice.detailed.report"
    _description = "Detailed Invoices"
    _auto = False   # <-- Important: no automatic table creation
#     _sql_view = """


    id= fields.Integer(string='Internal Id', readonly=True)
    name= fields.Char(string='Invoice', readonly=True)
    date = fields.Date(string='Date', readonly=True)

    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    display_name = fields.Char('Name', readonly=True)

    quantity = fields.Float(string='Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price', readonly=True)
    discount = fields.Float(string='discount', digits='Product Price', readonly=True)
    subt_revenue = fields.Float(string='Subtotal Revenue', digits='Product Price', readonly=True)
    cost_unit = fields.Float(string='Unit Cost', digits='Product Price', readonly=True)
    subt_cost = fields.Float(string='Subtotal Cost', digits='Product Price', readonly=True)
    tax = fields.Float(string='Tax', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    invoice_origin = fields.Char(string='Origin', readonly=True)
    attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')
    product_num = fields.Char(string='Product ID', compute='_compute_dummy', search='_search_product_id')
    cost_account = fields.Many2one('account.account', 'Cost Account', readonly=True)
    revenue_account = fields.Many2one('account.account', 'Revenue Account', readonly=True)
    
    move_type  = fields.Selection([
        ('out_invoice','Sale'),
        ('out_refund', 'Return'),
    ], string='Move Type', required=False)

    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False
            record.product_num = False
            
    def _search_attribute(self, operator, value):
        """Search by product attribute values"""
        if operator == 'ilike' and value:
            return [('product_id.attribute_line_ids.value_ids.name', 'ilike', value)]
        return []
		
    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        """
        Override search method to use AND logic between search terms,
        including computed fields like attribute_search.
        """
        new_args = []
        search_terms = []

        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                if field =='attribute_search':
                    attrib=self.env['product.attribute.value'].search([('name', 'ilike', value)]).ids
                    search_terms.append(('product_id.product_template_attribute_value_ids.product_attribute_value_id', 'in', attrib))
                elif field == 'product_num':
                    search_terms.append(('product_id.id', '=', value))
                else:
                    new_args.append(domain)
            else:
                new_args.append(domain)

        # Combine search terms with AND (&) logic properly
        if search_terms:
            # Start with the first term
            combined_domain = [search_terms[0]]
            # For each next term, prepend an '&' and the new term
            for term in search_terms[1:]:
                combined_domain =combined_domain + [term]
            new_args += combined_domain  # extend, not append

        return super(InvoiceDetailed, self).search(new_args, offset=offset, limit=limit, order=order, count=count)




    def init(self):
        # """Initialize SQL view"""
        # tools.drop_view_if_exists(self._cr, self._table)
       # cost_account_ids = self.env['ir.config_parameter'].sudo().get_param('cost_account_ids.cost_account_ids')
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (

Select row_number() OVER() AS id,M.name,M.move_type,M.date,M.journal_id,M.product_id,M.display_name,M.quantity,M.price_unit,M.cost_unit,M.currency_id,M.partner_id,M.amount_currency,M.invoice_origin ,
M.price_total-M.price_subtotal as Tax,M.quantity*M.cost_unit as subt_cost,M.quantity*M.price_unit-M.discount as subt_revenue,M.discount
,M.revenue_account,M.cost_account
                         from
(
	SELECT  A.name, A.date, A.move_type,  A.journal_id, D.Product_id,D.name as display_name,D.price_total,D.price_subtotal,D.quantity,D.price_unit,pc.price_unit as cost_unit, 
A.currency_id, A.partner_id,   A.amount_untaxed, A.amount_tax, D.amount_currency ,A.invoice_origin,
  row_number() OVER(partition by D.product_id,D.move_id order by D.id ) AS product_sql,A.id as invoice_id,D.quantity*D.price_unit*D.discount/100 as discount
    ,D.account_id as revenue_account,pc.account_id as cost_account
	FROM public.account_move as A inner join public.account_move_line as D
	on A.id =D.Move_id
  left join (
                select product_id,move_id,account_id,sum(balance)/sum(quantity) as price_unit  from account_move_line where 
                account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_account_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
                and journal_id=any (
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_journal_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
                group by product_id,move_id,account_id     
                         
)    pc on D.product_id=pc.product_id and D.move_id=pc.move_id
	where A.move_type in ('out_invoice','out_refund')  and state='posted'  and d.tax_line_id is null 
) as M
order by invoice_id desc,product_sql asc
                         
        )
        """ % self._table)


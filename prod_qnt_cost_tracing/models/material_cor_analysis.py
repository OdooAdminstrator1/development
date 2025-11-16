from odoo import models, fields, tools,api, _
from lxml import etree
from datetime import date



class MaterialCorAnalysis(models.Model):
    _name = "material.cor.analysis"
    _description = "Material CoR analysis"
    _auto = False   # <-- Important: no automatic table creation

    id= fields.Integer(string='Product Id', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    revenue = fields.Float(string='Subtotal Revenue', digits='Product Price', readonly=True)
    discount = fields.Float(string='discount', digits='Product Price', readonly=True)
    cost = fields.Float(string='Subtotal Cost', digits='Product Price', readonly=True)
    tax = fields.Float(string='Tax', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')
    
    thisyear = fields.Boolean(string='this year', compute='_compute_dummy')

    lastyear = fields.Boolean(string='last year', compute='_compute_dummy')
    


    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False
            record.lastyear = False
            record.thisyear = False



    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
       # cost_account_ids = self.env['ir.config_parameter'].sudo().get_param('cost_account_ids.cost_account_ids')
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select M.product_id as id, M.product_id,M.currency_id,
sum(M.sign*M.quantity) as quantity,                        
sum(M.sign*(M.price_total-M.price_subtotal)) as Tax,
sum(M.sign*(M.quantity*M.cost_unit)) as cost,
sum(M.sign*(M.quantity*M.price_unit-M.discount)) as revenue,
sum(M.sign*(M.discount))  as discount              
from
(
	SELECT D.product_id, D.price_total,D.price_subtotal,D.quantity,D.price_unit,pc.price_unit as cost_unit, 
   A.currency_id, D.quantity*D.price_unit*D.discount/100 as discount,(CASE WHEN A.move_type='out_refund' THEN -1 ELSE 1 END) as sign
	FROM invoice_detailed_param p, account_move as A inner join account_move_line as D
	on A.id =D.Move_id
  FULL OUTER JOIN (
                select product_id,move_id,account_id,max(price_unit) as price_unit  from account_move_line where 
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
                and account_id in (select account_id from cost_param_account_account_rel)
                group by product_id,move_id,account_id     
                         
)    pc on D.product_id=pc.product_id and D.move_id=pc.move_id
	where A.move_type in ('out_invoice','out_refund')  and state='posted' and D.exclude_from_invoice_tab=False and d.tax_line_id is null 
       and  D.account_id=any (
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.revenue_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	and d.display_type is null
    and  D.account_id in (select account_id from revenue_param_account_account_rel)
    and (p.fromdate is null or A.date>=p.fromdate)
    and (p.todate is null or A.date<p.todate)                     
) as M
where M.product_id is not null
group by  M.product_id,M.currency_id
order by M.product_id
        )
        """ % self._table)


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search method to use AND logic between search terms,
        including computed fields like attribute_search.
        """
        new_args = []
        search_terms = []
        fromdate=False
        todate = False
        

        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                if field =='attribute_search':
                    attrib=self.env['product.attribute.value'].search([('name', 'ilike', value)]).ids
                    search_terms.append(('product_id.product_template_attribute_value_ids.product_attribute_value_id', 'in', attrib))
                else:
                    new_args.append(domain)

                if field=='lastyear':
                    fromdate=date.today().replace(year=date.today().year - 1).strftime('%Y-01-01')
                    todate = date.today().strftime('%Y-01-01')
                

                if field=='thisyear':
                    if (fromdate):
                        todate=False
                    else:
                        fromdate = date.today().strftime('%Y-01-01')
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


        param=self.env['invoice.detailed.param'].sudo().search([], limit=1)
        param.prepare_for_datequery(fromdate,todate)
        self.env.cr.commit()
        return super(MaterialCorAnalysis, self).search(new_args, offset=offset, limit=limit, order=order, count=count)


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialCorAnalysis, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        # param = self.env['invoice.detailed.param'].sudo().search([], limit=1)
        # param._create_default_record()
        if view_type == 'search':
            print(res['arch'])
            arch = etree.fromstring(res['arch'])
            item=etree.Element('filter', name='this_financial', string='This financial',domain="[('thisyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
            item=etree.Element('filter', name='last_financial_year', string='Last financial year',domain="[('lastyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
            res['arch'] = etree.tostring(arch, encoding='unicode')
        return res
        

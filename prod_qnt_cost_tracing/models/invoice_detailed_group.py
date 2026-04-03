from odoo import models, fields, tools,api, _
from lxml import etree
import json
import ast

class InvoiceDetailed(models.Model):
    _name = "invoice.detailed.group"
    _description = "Invoices Summary"
    _auto = False   # <-- Important: no automatic table creation

    id= fields.Integer(string='Internal Id', readonly=True)
    name= fields.Char(string='Invoice', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    move_type  = fields.Selection([
        ('out_invoice','Sale'),
        ('out_refund', 'Return'),
    ], string='Move Type', required=False)

    revenue = fields.Float(string='Revenue', digits='Product Price', readonly=True)
    discount = fields.Float(string='discount', digits='Product Price', readonly=True)
    cost = fields.Float(string='Cost', digits='Product Price', readonly=True)
    tax = fields.Float(string='Tax', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    invoice_origin = fields.Char(string='Origin', readonly=True)
    revenue_account = fields.Char(string='revenue account', readonly=True)
    cost_account = fields.Char(string='cost account', readonly=True)
    # attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')
    # date_from = fields.Date(string="From Date")
    # date_to = fields.Date(string="To Date")


    def _compute_dummy(self):
        pass



    def init(self):
        """Initialize SQL view"""
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
			select tt.* from (
select M.id,M.name,M.move_type,M.date,M.currency_id,M.partner_id,M.invoice_origin ,
sum(M.price_total-M.price_subtotal) as Tax,sum(M.quantity*M.cost_unit) as cost,
(CASE WHEN M.move_type='out_refund' THEN -1 ELSE 1 END)*sum(M.quantity*M.price_unit-M.discount) as revenue,
sum(M.discount) as discount ,
STRING_AGG(DISTINCT CAST(M.revenue_account AS VARCHAR) , ', ')||','  as revenue_account,
STRING_AGG(DISTINCT CAST(M.cost_account AS VARCHAR) , ', ')||','  as cost_account
                                                
                         from
(
	SELECT A.id, A.name, A.date, A.move_type,D.price_total,D.price_subtotal,D.quantity,D.price_unit,pc.price_unit as cost_unit, 
   A.currency_id, A.partner_id   ,A.invoice_origin,
   D.quantity*D.price_unit*D.discount/100 as discount
    ,D.account_id as revenue_account,pc.account_id as cost_account
                         
	FROM public.account_move as A inner join public.account_move_line as D
	on A.id =D.Move_id
  FULL OUTER JOIN (
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
                and account_id in (select account_id from cost_param_account_account_rel)
                group by product_id,move_id,account_id     
                         
)    pc on D.product_id=pc.product_id and D.move_id=pc.move_id
	where A.move_type in ('out_invoice','out_refund')  and state='posted'  and d.tax_line_id is null 
       and  D.account_id=any (
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.revenue_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
    and  D.account_id in (select account_id from revenue_param_account_account_rel)

) as M
group by M.id, M.name,M.move_type,M.date,M.currency_id,M.partner_id,M.invoice_origin 
order by M.date desc 
) as tt
        )
        """ % self._table)


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search method to use AND logic between search terms,
        including computed fields like attribute_search.
        """
        costs = []
        revs = []
        all_revs,all_costs=self.getAccounts()
        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                if field =='cost_account':
                    costs.append(int(value.replace('%','').replace(',','')))
                if field =='revenue_account':
                    revs.append(int(value.replace('%','').replace(',','')))
        if (len(costs)==0):
            costs=all_costs
        if (len(revs)==0):
            revs=all_revs

        param=self.env['invoice.detailed.param'].sudo().search([], limit=1)
        param.prepare_for_query(revs,costs)
        self.env.cr.commit()
        return super(InvoiceDetailed, self).search(args, offset=offset, limit=limit, order=order, count=count)


    def _get_view(self, view_id=None, view_type='form', **options):
        # 1. Call the parent method first to get the original view architecture
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'search':
            
            newFilters=self.get_categorized_filters()
            conf=newFilters['Cost of revenue accounts']
            if conf:
                parent=arch.xpath("//filter[@name='All_rev']")
                for acc in conf:
                    item=etree.Element('filter', name=acc['name'], string=acc['string'],domain=acc['domain'],context="{'group_by': False}")
                    parent[0].addnext(item)

            conf=newFilters['Cost of revenue journals']
            if conf:
                parent=arch.xpath("//filter[@name='All_costs']")
                for acc in conf:
                    item=etree.Element('filter', name=acc['name'], string=acc['string'],domain=acc['domain'],context="{'group_by': False}")
                    parent[0].addnext(item)



        return arch, view

	
    # @api.model
    # def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
    #     res = super(InvoiceDetailed, self).fields_view_get(
    #         view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
    #     )
    #     # param = self.env['invoice.detailed.param'].sudo().search([], limit=1)
    #     # param._create_default_record()
    #     if view_type == 'search':
    #         arch = etree.fromstring(res['arch'])
    #         newFilters=self.get_categorized_filters()
    #         conf=newFilters['Cost of revenue accounts']
    #         if conf:
    #             parent=arch.xpath("//filter[@name='All_rev']")
    #             for acc in conf:
    #                 item=etree.Element('filter', name=acc['name'], string=acc['string'],domain=acc['domain'],context="{'group_by': False}")
    #                 parent[0].addnext(item)

    #         conf=newFilters['Cost of revenue journals']
    #         if conf:
    #             parent=arch.xpath("//filter[@name='All_costs']")
    #             for acc in conf:
    #                 item=etree.Element('filter', name=acc['name'], string=acc['string'],domain=acc['domain'],context="{'group_by': False}")
    #                 parent[0].addnext(item)



    #         # parent filter only, no children in XML
    #     #    parent = etree.Element('filter', name='filter_by_dates', string='Filter by Dates')
    #      #   arch.append(parent)

    #         res['arch'] = etree.tostring(arch, encoding='unicode')
    #     return res
        

    def get_categorized_filters(self):
        """Return filters organized by categories"""
        categorized_filters = {}
        revenus,costs=self.getAccounts()
        conf=revenus
        if conf:
            categorized_filters['Cost of revenue accounts']=[]
            accs=self.env['account.account'].search([('id','in',conf)])
            for config in accs:
                categorized_filters['Cost of revenue accounts'].append({
                'name': f'cos_{config.id}',
                'string': config.name,
                'domain' : f"[('revenue_account', 'ilike', '%{str(config.id)},%')]",
                })

        conf=costs
        if conf:
            categorized_filters['Cost of revenue journals']=[]
            accs=self.env['account.account'].search([('id','in',conf)])
            for config in accs:
                categorized_filters['Cost of revenue journals'].append({
                'name': f'rev_{config.id}',
                'string': config.name,
                'domain' : f"[('cost_account', 'ilike', '%{str(config.id)},%')]",
                })

        return categorized_filters
    

    def getAccounts(self):
        distinct_revenus = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.revenue_ids')
        distinct_costs = self.env['ir.config_parameter'].sudo().get_param('prod_qnt_cost_tracing.cost_account_ids')
      
        return ast.literal_eval(distinct_revenus),ast.literal_eval(distinct_costs)
    
    
    def getSummary(self):
        SQL= """
select COALESCE(sum(revenue),0) as s_revenue,
COALESCE(sum(cost),0) as s_cost
from %s
"""% self._table
        self._cr.execute(SQL)
        query_res = self._cr.fetchone()
        if query_res:
            return {
                's_revenue' :format( int(query_res[0]),','),
                's_cost' :  format( int(query_res[1]),','),
            }
        else:
            return {
                's_revenue' : 0,
                's_cost' : 0,
            }
    @api.model
    def getSummary2(self,domain):
        # if (not domain):
        #     domain=[]
        result = self.env['invoice.detailed.group'].read_group(domain, 
            ['revenue:sum',  'cost:sum'],[])
       
        s_revenue = '0'
        s_cost= '0'
        if result:
            totals = result[0]
            s_revenue = format(int(totals.get('revenue', 0) or 0),',')
            s_cost= format(int(totals.get('cost', 0) or 0),',')
        return {
                's_revenue' : s_revenue,
                's_cost' : s_cost,
            }

                

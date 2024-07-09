from odoo import models, fields, tools


class FinishedProductReport(models.Model):
    _name = "finished.product.report"
    _auto = False

    product = fields.Char(string='Product')
    product_id = fields.Many2one(comodel_name="product.product")
    stock_move_line_id = fields.Many2one(comodel_name='stock.move.line')
    lot_name = fields.Char(related="stock_move_line_id.lot_id.name", readonly=True)
    cost_date = fields.Date(related="stock_move_line_id.cost_date", readonly=True)


    def init(self):
        query = """
        SELECT stock_move_line.id as id, stock_move_line.id as stock_move_line_id, product_product.id as product_id, product_template."name" as product
        FROM PUBLIC.mrp_production
        join public.stock_move on mrp_production.id = stock_move.production_id
        join public.stock_move_line on stock_move.id = stock_move_line.move_id
        join public.mrp_bom on mrp_bom.id = mrp_production.bom_id
        join public.product_product on mrp_production.product_id = product_product.id
        join public.product_template on product_template.id = product_product.product_tmpl_id
        where 1=1
        and mrp_bom.finishing_product_ok = True
        and stock_move.state = 'done'
"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, query))

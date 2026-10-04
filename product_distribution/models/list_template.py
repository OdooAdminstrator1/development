from odoo import api, fields, models

class ListTemplate(models.Model):
    _name = 'list.template'
    _description = 'List Template'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    line_ids = fields.One2many(
        'list.template.line',
        'template_id',
        string='Lines',
        copy=True,
    )
    line_count = fields.Integer(compute='_compute_line_count')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_confirm(self):
        # Placeholder action - add your business logic
        for rec in self:
            rec.name = rec.name  # no-op, keeps method for UI
        return True



class ListTemplateLine(models.Model):
    _name = 'list.template.line'
    _description = 'List Template Line'
    _order = 'template_id, id'

    template_id = fields.Many2one(
        'list.template',
        string='List Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    max_quantity = fields.Float(
        string='Max Quantity',
        default=1.0,
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True,
    )

from odoo import fields,api, models, _


class ProductLabelLayoutInherited(models.TransientModel):
    _inherit = 'product.label.layout'

    color_picker = fields.Char(string="Color")

    def _prepare_report_data(self):
        xml_id, data = super(ProductLabelLayoutInherited, self)._prepare_report_data()
        data['color_picker'] = self.color_picker
        return xml_id, data
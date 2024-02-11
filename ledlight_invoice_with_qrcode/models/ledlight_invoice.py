from odoo import models, fields, api, _
import qrcode
import base64
import io


class SaleOrderInherited(models.Model):
    _inherit = 'sale.order'

    emp_sale_id = fields.Many2one('hr.employee')


class LedLightResPartner(models.Model):
    _inherit = 'res.partner'

class LedLightAccountMove(models.Model):
    _inherit = 'account.move'

    qr_code_generated = fields.Char('QR Code', compute='_compute_qr_code_generated')

    def _compute_qr_code_generated(self):
        for res in self:
            res.qr_code_generated = res.get_qr_code(res.partner_id.name, res.partner_id.vat if res.partner_id.vat else "", str(res.date), str(res.amount_total), str(res.amount_tax))

    @api.model
    def get_qr_code(self, customer_name, registration_tax, invoice_date, invoice_with_vat, vat_amount):
        t1 = self.get_tlv_for_value(1, customer_name)
        t2 = self.get_tlv_for_value(2, registration_tax)
        t3 = self.get_tlv_for_value(3, invoice_date)
        t4 = self.get_tlv_for_value(4, invoice_with_vat)
        t5 = self.get_tlv_for_value(5, vat_amount)
        res = t1 + t2 + t3 + t4 + t5
        bas = base64.b64encode(bytes.fromhex(res))
        if bas != "":
            img = qrcode.make(bas)
            result = io.BytesIO()
            img.save(result, format='PNG')
            result.seek(0)
            img_bytes = result.read()
            base64_encoded_result_bytes = base64.b64encode(img_bytes)
            base64_encoded_result_str = base64_encoded_result_bytes.decode('ascii')
            return base64_encoded_result_str

    def get_tlv_for_value(self, tag_num, tag_value):
        tag_buf = hex(tag_num)[2:].zfill(2)  # [item.encode('hex') for item in str(tag_num)]
        tag_value_length_buf = hex(len(tag_value))[2:].zfill(2)  # str(len(tag_value)).encode('hex')
        tag_value_buff = "".join("{:02x}".format(ord(c)) for c in tag_value)  # str(tag_value).encode('hex')
        return tag_buf + tag_value_length_buf + tag_value_buff
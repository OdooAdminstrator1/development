# models/purchase_order.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        self.send_validation_notification()
        return res
    
    def send_validation_notification(self):
        config = self.env['purchase.notification.config'].search([], limit=1)
        if not config or not config.user_ids:
            return
            
        template = self.env.ref('purchase.email_template_edi_purchase', False)
        if not template:
            raise UserError(_("Email template not found"))
            
        for user in config.user_ids:
            if user.email:
                template.with_context(
                    email_to=user.email,
                    user_name=user.name
                ).send_mail(self.id, force_send=True)
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
        config = self.env['purchase.notification.config'].sudo().search([], limit=1)
        if not config or not config.user_ids:
            return
            
        #template = self.env.ref('iy_po_notify.po_approval_notification_email_tem', False)
        #if not template:
        #    raise UserError(_("Email template not found"))
            
        for user in config.user_ids:
            if user.email:
                self.send_custom_email(user)
           #     template.with_context(
           #         email_to=user.email,
           #         user_name=user.name
           #     ).sudo().send_mail(self.id, force_send=True)



    def send_custom_email(self,userr):
        str_body=f"""
            <div>
                <p>Dear {userr.name} ,</p>
                <p>The following purchase order has been validated by {self.env.user.name}:</p>
                <p>Order Reference: {self.name}</p>
                <p>Vendor: {self.partner_id.name}</p>
                <p>Amount: {self.amount_total}</p>
                <p>Order Date: {self.date_order}</p>
                <p>You can view the order here: 
                    <a href='https://odooadminstrator1-development.odoo.com/web#id={self.id}&amp;model=purchase.order&amp;view_type=form' >
                        View Purchase Order
                    </a>
                </p>
            </div>
        """

        mail_values = {
            'subject': 'PO is confirmed',
            'body_html': str_body,
            'email_from': self.env.user.email,
            'email_to': userr.email,
            'model': self._name,
            'res_id': self.id,
        }
        # Create and send email
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()



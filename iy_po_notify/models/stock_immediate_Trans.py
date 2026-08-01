from odoo import _, api, fields, models
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # 1. Call super to perform the standard validation logic.
        # Odoo 17 handles the immediate transfer/backorder logic internally here.
        res = super(StockPicking, self).button_validate()

        # 2. Check if the validation was successful. 
        # Usually, if res is True or None, it succeeded. 
        # If it returns a dict, it's likely opening a wizard (like a backorder confirmation).
        if res is True or res is None:
            for picking in self:
                # In Odoo 17, 'done' is the state for a validated picking
                if picking.state == 'done' and  picking.picking_type_code not in ('internal', 'mrp_operation'):
                    self.send_validation_notification(picking)
        return res 

# class StockImmediateTransferEmail(models.TransientModel):
#     _inherit = 'stock.immediate.transfer'
    

#     def process(self):
#         pickings_to_do = self.env['stock.picking']
#         for line in self.immediate_transfer_line_ids:
#             if line.to_immediate is True:
#                 pickings_to_do |= line.picking_id

#         res = super(StockImmediateTransferEmail, self).process()
#         if res:
#            for line in pickings_to_do:
#                 if line.state == 'assigned':
#                         self.send_validation_notification(self,line)

#         return res
    
    def send_validation_notification(self,picking):
        config = self.env['purchase.notification.config'].search([], limit=1)
        if not config or not config.user_ids:
            return
            
            
        for user in config.user_ids:
            self.send_custom_email(user,picking)

    
    def send_custom_email(self,userr,picking):#partner_id
        str_body=f"""
            <div>
                <p>Dear {userr.name} ,</p>
                <p>The following inventory receipt has been validated by {self.env.user.name}:</p>
                <p>Inventory Reference: {picking.name}</p>
                <p>Vendor: {picking.partner_id.name}</p>
                <p>Receipt Date: {picking.date_done}</p>
                <p>You can view the receipt here: 
                    <a href='/web#id={picking.id}&amp;model=stock.picking&amp;view_type=form' >
                        View Inventory Receipt
                    </a>
                </p>
            </div>
        """

        mail_values = {
            'subject': 'Receipt is confirmed',
            'body_html': str_body,
            'email_from': self.env.user.email,
            'email_to': userr.email,
            'model': 'stock.picking',
            'res_id': picking.id,
        }
        # Create and send email
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()



    

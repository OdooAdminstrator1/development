# models/notification_config.py
from odoo import models, fields

class PurchaseNotificationConfig(models.Model):
    _name = 'purchase.notification.config'
    _description = 'Purchase Order Notification Configuration'
    
    name = fields.Char('Name', required=True)
    user_ids = fields.Many2many(
        'res.users',
        string='Users to Notify',
        help='Users who will receive email notifications when a PO is validated'
    )
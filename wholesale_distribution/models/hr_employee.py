from odoo import _, models
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _is_distribution_distributer(self):
        """True when this employee belongs to the Distribution department."""
        self.ensure_one()
        department = self.env.ref(
            'wholesale_distribution.department_distribution', raise_if_not_found=False)
        return bool(department) and self.department_id == department

    def action_create_user(self):
        """For distributers, create a PORTAL user carrying the distributer access
        right (no internal seat) instead of the standard internal user form."""
        self.ensure_one()
        if self._is_distribution_distributer():
            if self.user_id:
                raise ValidationError(_("This employee already has a user."))
            login = self.work_email or self.private_email
            if not login:
                raise UserError(_(
                    "Set a Work Email on %s before creating a portal user.", self.name))
            portal_group = self.env.ref('base.group_portal')
            distributer_group = self.env.ref('wholesale_distribution.group_distribution_portal')
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': self.name,
                'login': login,
                'email': self.work_email,
                'group_ids': [(6, 0, [portal_group.id, distributer_group.id])],
            })
            self.user_id = user.id
            return self.action_open_user()
        return super().action_create_user()

    def action_open_user(self):
        self.ensure_one()
        if not self.user_id:
            raise UserError(_("This employee has no related user."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Related User"),
            'res_model': 'res.users',
            'res_id': self.user_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class filter_with_and_instead_of_or(models.Model):
#     _name = 'filter_with_and_instead_of_or.filter_with_and_instead_of_or'
#     _description = 'filter_with_and_instead_of_or.filter_with_and_instead_of_or'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

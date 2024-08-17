# -*- coding: utf-8 -*-
{
    'name': "aesp_overtime_hr",

    'summary': """
        Allow to create multiple transfers for multiple mos""",

    'description': """
        Allow to create multiple transfers for multiple mos
    """,

    'author': "Ali Haitham Ali",
    'website': "https://www.abo-ayman.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Manufacturing/Manufacturing',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['mrp', 'base', 'hr', 'hr_contract', 'hr_work_entry_contract_enterprise', 'hr_holidays'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/res_config_view.xml',
    ],
}

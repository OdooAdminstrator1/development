# -*- coding: utf-8 -*-
{
    'name': "Rest of day off",


    'author': "Iyad Husary",
    'category': 'Human Resources/Employees',
    'version': '17.0.1.0',

    'depends': ['hr', 'hr_payroll',  'hr_contract','hr_holidays'],

    # always loaded
    'data': [
       # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/res_config_view.xml',
    ],
}

# -*- coding: utf-8 -*-
{
    "name": """Web Widget Colorpicker""",
    "summary": """Added Color Picker for From""",
    "category": "web",
    "images": ['static/description/icon.png'],
    "version": "17.0.25.07.24",
    "description": """

            For Form View - added = widget="colorpicker"
            
            ...
            <field name="arch" type="xml">
                <form string="View name">
                    ...
                    <field name="colorpicker" widget="colorpicker"/>
                    ...
                </form>
            </field>
            ...

    """,

    "author": "Viktor Vorobjov",
    "license": "LGPL-3",
    "website": "https://straga.github.io",
    "support": "vostraga@gmail.com",
    "price": 0.00,
    "currency": "EUR",

    "depends": [
        "web"
    ],
    "external_dependencies": {"python": [], "bin": []},
    "data": [
    ],

    'assets': {

        'web.assets_backend': [
            
            # Using Pickr - modern color picker with RGBA support
            '/web_widget_colorpicker/static/src/lib/pickr/classic.min.css',
            '/web_widget_colorpicker/static/src/lib/pickr/pickr.min.js',

            '/web_widget_colorpicker/static/src/css/widget.css',
            '/web_widget_colorpicker/static/src/js/color_picker_field.xml',
            '/web_widget_colorpicker/static/src/js/color_picker_field.js',

        ]
    },


    "qweb": [
    ],
    "demo": [],

    "post_load": None,
    "pre_init_hook": None,
    "post_init_hook": None,
    "installable": True,
    "auto_install": False,
    "application": False,
}

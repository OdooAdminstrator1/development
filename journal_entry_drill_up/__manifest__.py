
{
    "name": "Journal Entry drill up",
    "version": "1",
    'summary': "to go from journal entry to the object that created this JE",

    'description': "",
    "depends": ["stock_account","stock","mrp","account"],
    "author": "MHD_ALI",

    "installable": True,
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",

        "views/stock_move_view.xml",
    ],
}

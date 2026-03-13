{
    "name": "Global Command Palette",
    "summary": "Ctrl+K global search for menus, actions, and records",
    "description": """
        Global command palette for Odoo backend.
        - Ctrl + K trigger
        - Search menus
        - Search actions
        - Search records across accessible models
    """,
    "author": "mgite",
    # "price": 19.0,
    # "currency": "EUR",
    "support": "matemana2608@gmail.com",
    "license": "OPL-1",
    "category": "Productivity",
    "version": "19.0.1.0.0",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "mg_command_palette/static/src/js/search_service.js",
            "mg_command_palette/static/src/js/palette.js",
        ],
    },
    "installable": True,
    "application": False,
}

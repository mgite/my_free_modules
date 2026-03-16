{
    "name": "Session Replay",
    "summary": "Configure and store backend session replay captures",
    "description": """
        Initial backend scaffold for session replay support in Odoo.
        - Settings entry for pre-error recording duration
        - Capture model for replay payloads
        - Technical views to inspect saved captures
    """,
    "author": "mgite",
    "support": "matemana2608@gmail.com",
    "license": "OPL-1",
    "category": "Tools",
    "version": "19.0.1.0.0",
    "images": ["static/description/wallpaper.png"],
    "depends": [
        "base_automation",
        "base_setup",
        "mg_openai_integration",
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/debug_session_capture_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mg_session_replay/static/src/js/session_replay_service.js",
        ],
    },
    "installable": True,
    "application": False,
}

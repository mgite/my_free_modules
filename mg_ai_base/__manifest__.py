{
    "name": "AI Base",
    "summary": "Common AI integrations base module",
    "description": """
        Shared AI integration foundation:
        - generic AI model registry
        - common AI settings entry in Settings
        - reusable base for provider-specific modules
    """,
    "author": "mgite",
    "support": "matemana2608@gmail.com",
    "license": "OPL-1",
    "category": "Tools",
    "version": "19.0.1.0.0",
    "depends": [
        "base_setup",
    ],
    "data": [
        "data/ai_provider_data.xml",
        "security/ir.model.access.csv",
        "views/ai_helper_views.xml",
        "views/ai_model_views.xml",
        "views/ai_provider_views.xml",
        "views/ai_type_views.xml",
        "views/ir_actions_server_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}

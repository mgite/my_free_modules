from odoo import fields, models


class MgAIProvider(models.Model):
    _name = "mg.ai.provider"
    _description = "AI Provider"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    is_active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "The AI provider code must be unique.",
    )

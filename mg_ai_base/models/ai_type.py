from odoo import fields, models


class MgAIType(models.Model):
    _name = "mg.ai.type"
    _description = "AI Type"
    _order = "name"

    name = fields.Char(required=True)
    ai_provider_ids = fields.Many2many(
        comodel_name="mg.ai.provider",
        relation="mg_ai_type_provider_rel",
        column1="type_id",
        column2="provider_id",
        string="AI Providers",
        required=True,
    )
    is_active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "The AI type name must be unique.",
    )

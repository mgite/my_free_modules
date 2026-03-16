from odoo import fields, models


class MgAIModel(models.Model):
    _name = "mg.ai.model"
    _description = "AI Model"
    _order = "ai_provider_id, ai_type_id, name"

    name = fields.Char(required=True)
    provider_model_id = fields.Char(required=True, index=True)
    ai_provider_id = fields.Many2one(
        comodel_name="mg.ai.provider",
        string="AI Provider",
        required=True,
        index=True,
    )
    ai_type_id = fields.Many2one(
        comodel_name="mg.ai.type",
        string="AI Type",
        required=True,
        index=True,
    )
    owned_by = fields.Char()
    is_active = fields.Boolean(default=True)
    synced_at = fields.Datetime(readonly=True)
    raw_payload = fields.Text(readonly=True)

    _provider_model_id_unique = models.Constraint(
        "UNIQUE(provider_model_id)",
        "The AI model id must be unique.",
    )

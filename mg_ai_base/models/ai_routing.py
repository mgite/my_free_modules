from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MgAIRouting(models.Model):
    _name = "mg.ai.routing"
    _description = "AI Routing"
    _order = "company_id, ai_type_id"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
    )
    ai_type_id = fields.Many2one(
        comodel_name="mg.ai.type",
        string="AI Type",
        required=True,
        index=True,
    )
    available_ai_provider_ids = fields.Many2many(
        comodel_name="mg.ai.provider",
        related="ai_type_id.ai_provider_ids",
        string="Available AI Providers",
        readonly=True,
    )
    ai_provider_id = fields.Many2one(
        comodel_name="mg.ai.provider",
        string="AI Provider",
        required=True,
        index=True,
    )
    ai_model_id = fields.Many2one(
        comodel_name="mg.ai.model",
        string="AI Model",
        required=True,
        index=True,
    )

    _company_type_unique = models.Constraint(
        "UNIQUE(company_id, ai_type_id)",
        "Only one AI model can be configured per AI type and company.",
    )
    _company_type_provider_model_unique = models.Constraint(
        "UNIQUE(company_id, ai_type_id, ai_provider_id, ai_model_id)",
        "This AI routing combination already exists for the selected company.",
    )

    @api.onchange("ai_type_id")
    def _onchange_ai_type_id(self):
        for rec in self:
            rec.ai_provider_id = False
            rec.ai_model_id = False

    @api.onchange("ai_provider_id")
    def _onchange_ai_provider_id(self):
        for rec in self:
            rec.ai_model_id = False

    @api.constrains("ai_type_id", "ai_provider_id", "ai_model_id")
    def _check_routing_consistency(self):
        for rec in self:
            if rec.ai_type_id and rec.ai_provider_id and rec.ai_provider_id not in rec.ai_type_id.ai_provider_ids:
                raise ValidationError("The selected AI provider is not allowed for this AI type.")
            if rec.ai_model_id:
                if rec.ai_type_id and rec.ai_model_id.ai_type_id != rec.ai_type_id:
                    raise ValidationError("The selected AI model does not match the selected AI type.")
                if rec.ai_provider_id and rec.ai_model_id.ai_provider_id != rec.ai_provider_id:
                    raise ValidationError("The selected AI model does not match the selected AI provider.")

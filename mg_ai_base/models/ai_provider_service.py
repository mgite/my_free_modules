from odoo import _, api, models
from odoo.exceptions import UserError


class MgAIProviderService(models.AbstractModel):
    _name = "mg.ai.provider.service"
    _description = "AI Provider Service"

    @api.model
    def run_ai_helper(self, helper, record, routing, rendered):
        raise UserError(
            _("The AI provider service for %(provider)s does not implement AI Helper execution.",
              provider=routing.ai_provider_id.display_name)
        )

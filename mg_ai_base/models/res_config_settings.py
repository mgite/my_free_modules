from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mg_ai_routing_ids = fields.One2many(
        related="company_id.mg_ai_routing_ids",
        readonly=False,
        string="AI Routing",
    )

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mg_ai_routing_ids = fields.One2many(
        comodel_name="mg.ai.routing",
        inverse_name="company_id",
        string="AI Routing",
    )

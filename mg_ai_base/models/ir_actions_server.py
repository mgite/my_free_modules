from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    state = fields.Selection(
        selection_add=[("ai_helper", "AI Helper")],
        ondelete={"ai_helper": "cascade"},
    )
    available_ai_helper_type_ids = fields.Many2many(
        comodel_name="mg.ai.type",
        compute="_compute_available_ai_helper_type_ids",
        string="Available AI Types",
        readonly=True,
    )
    ai_helper_type_id = fields.Many2one(
        comodel_name="mg.ai.type",
        string="AI Type",
        ondelete="restrict",
    )
    available_ai_helper_provider_ids = fields.Many2many(
        comodel_name="mg.ai.provider",
        compute="_compute_available_ai_helper_provider_ids",
        string="Available AI Providers",
        readonly=True,
    )
    ai_helper_provider_id = fields.Many2one(
        comodel_name="mg.ai.provider",
        string="AI Provider",
        ondelete="restrict",
    )
    ai_helper_id = fields.Many2one(
        comodel_name="mg.ai.helper",
        string="AI Helper",
        compute="_compute_ai_helper_id",
        readonly=True,
    )
    ai_helper_target_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Target Field",
        compute="_compute_ai_helper_target_field_id",
        readonly=True,
    )

    @api.depends_context("company")
    def _compute_available_ai_helper_type_ids(self):
        routing_env = self.env["mg.ai.routing"].sudo()
        type_ids = routing_env.search(
            [("company_id", "=", self.env.company.id)]
        ).mapped("ai_type_id").ids
        for action in self:
            action.available_ai_helper_type_ids = [(6, 0, type_ids)]

    @api.depends("ai_helper_type_id")
    def _compute_available_ai_helper_provider_ids(self):
        routing_env = self.env["mg.ai.routing"].sudo()
        for action in self:
            provider_ids = []
            if action.ai_helper_type_id:
                provider_ids = routing_env.search(
                    [
                        ("company_id", "=", self.env.company.id),
                        ("ai_type_id", "=", action.ai_helper_type_id.id),
                    ]
                ).mapped("ai_provider_id").ids
            action.available_ai_helper_provider_ids = [(6, 0, provider_ids)]

    @api.depends("model_id", "ai_helper_type_id")
    def _compute_ai_helper_id(self):
        for action in self:
            action.ai_helper_id = action._find_ai_helper()

    @api.depends("model_id", "ai_helper_type_id")
    def _compute_ai_helper_target_field_id(self):
        for action in self:
            action.ai_helper_target_field_id = action._find_ai_helper().target_field_id

    @api.onchange("ai_helper_type_id")
    def _onchange_ai_helper_type_id(self):
        for action in self:
            if action.ai_helper_provider_id and action.ai_helper_provider_id not in action.available_ai_helper_provider_ids:
                action.ai_helper_provider_id = False

    @api.constrains("state", "model_id", "ai_helper_type_id", "ai_helper_provider_id", "ai_helper_id")
    def _check_ai_helper_configuration(self):
        for action in self.filtered(lambda record: record.state == "ai_helper"):
            helper = action._find_ai_helper()
            if not action.ai_helper_type_id:
                raise ValidationError(_("An AI type is required for AI Helper actions."))
            if action.ai_helper_type_id not in action.available_ai_helper_type_ids:
                raise ValidationError(_("The selected AI type is not configured in AI Routing for the current company."))
            if not action.ai_helper_provider_id:
                raise ValidationError(_("An AI provider is required for AI Helper actions."))
            if not helper:
                raise ValidationError(_("An AI helper configuration is required for AI Helper actions."))
            if action.model_id != helper.model_id:
                raise ValidationError(_("The selected AI helper must target the same model as the server action."))
            if action.ai_helper_type_id != helper.ai_type_id:
                raise ValidationError(_("The selected AI helper must match the selected AI type."))
            if action.ai_helper_provider_id not in action.available_ai_helper_provider_ids:
                raise ValidationError(_("The selected AI provider is not routed for the selected AI type."))

    def _find_ai_helper(self):
        self.ensure_one()
        if not self.model_id or not self.ai_helper_type_id:
            return self.env["mg.ai.helper"]
        return self.env["mg.ai.helper"].search(
            [
                ("model_id", "=", self.model_id.id),
                ("ai_type_id", "=", self.ai_helper_type_id.id),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _get_ai_helper_routing(self, record):
        self.ensure_one()
        company = self.env.company
        if "company_id" in record._fields and record.company_id:
            company = record.company_id
        routing = self.env["mg.ai.routing"].sudo().search(
            [
                ("company_id", "=", company.id),
                ("ai_type_id", "=", self.ai_helper_type_id.id),
                ("ai_provider_id", "=", self.ai_helper_provider_id.id),
            ],
            limit=1,
        )
        if not routing:
            raise UserError(
                _("No AI routing is configured for type %(type)s and provider %(provider)s in company %(company)s.",
                  type=self.ai_helper_type_id.display_name,
                  provider=self.ai_helper_provider_id.display_name,
                  company=company.display_name)
            )
        return routing

    def _get_ai_provider_service(self, provider):
        self.ensure_one()
        service_model_name = f"mg.ai.provider.service.{provider.code}"
        if not self.env.registry.get(service_model_name):
            raise UserError(
                _("No installed AI integration can execute provider %(provider)s.",
                  provider=provider.display_name)
            )
        return self.env[service_model_name].sudo()

    def _create_ai_helper_attachment(self, record, helper, result):
        self.ensure_one()
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": result.get("filename") or f"{helper.name or helper.target_field_id.name or 'ai_file'}-{record.id}",
                "type": "binary",
                "datas": result["base64"],
                "mimetype": result.get("mime_type") or "application/octet-stream",
                "res_model": record._name,
                "res_id": record.id,
            }
        )
        if "message_ids" in record._fields and hasattr(record, "message_post"):
            record.message_post(
                body=result.get("message") or _("AI generated file attached."),
                attachment_ids=[attachment.id],
            )
        return attachment

    def _prepare_ai_helper_write_value(self, helper, result):
        self.ensure_one()
        field_type = helper.target_field_id.ttype
        if field_type == "binary":
            if result.get("kind") != "image":
                raise UserError(_("The AI provider did not return an image for the selected binary target field."))
            return result["base64"]
        if field_type == "html":
            return result.get("html") or result.get("text") or ""
        if field_type in ("char", "text"):
            return result.get("text") or ""
        if field_type == "json":
            return result.get("raw") or result
        raise UserError(_("Target field type %(type)s is not supported by the current AI Helper action.", type=field_type))

    def _run_single_ai_helper(self, record):
        self.ensure_one()
        helper = self._find_ai_helper()
        if not helper:
            raise UserError(_("No active AI helper is configured for model %(model)s and AI type %(type)s.",
                              model=self.model_id.display_name,
                              type=self.ai_helper_type_id.display_name))
        rendered = helper.render_prompt(record)
        if helper.target_field_id.ttype == "binary":
            rendered = helper.render_image_prompt(record)
        routing = self._get_ai_helper_routing(record)
        service = self._get_ai_provider_service(routing.ai_provider_id)
        result = service.run_ai_helper(helper, record, routing, rendered)
        record.write({helper.target_field_id.name: self._prepare_ai_helper_write_value(helper, result)})
        if helper.target_field_id.ttype == "binary":
            self._create_ai_helper_attachment(record, helper, result)

    def _run_action_ai_helper_multi(self, eval_context=None):
        records = (
            eval_context.get("records")
            or eval_context.get("record")
            or self.env[self.model_id.model]
        )
        records = records.exists()
        for action in self:
            for record in records:
                action._run_single_ai_helper(record)

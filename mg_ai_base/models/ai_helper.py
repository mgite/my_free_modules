import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext, html_sanitize


TEXT_TARGET_TYPES = ("char", "text", "html", "json")
IMAGE_TARGET_TYPES = ("binary",)
SOURCE_FIELD_TYPES = (
    "binary",
    "boolean",
    "char",
    "date",
    "datetime",
    "float",
    "html",
    "integer",
    "json",
    "many2one",
    "monetary",
    "selection",
    "text",
)


class MgAIHelper(models.Model):
    _name = "mg.ai.helper"
    _description = "AI Helper"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        domain=[("abstract", "=", False), ("transient", "=", False)],
        ondelete="cascade",
        index=True,
    )
    ai_type_id = fields.Many2one(
        comodel_name="mg.ai.type",
        string="AI Type",
        required=True,
        ondelete="restrict",
        index=True,
    )
    field_line_ids = fields.One2many(
        comodel_name="mg.ai.helper.field",
        inverse_name="helper_id",
        string="Source Fields",
        copy=True,
    )
    prompt_template = fields.Text(
        required=True,
        help="Instruction template used later by the AI action. Source field placeholders are defined on the Source Fields tab.",
    )
    target_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Target Field",
        required=True,
        ondelete="cascade",
    )
    notes = fields.Text()

    _name_model_unique = models.Constraint(
        "UNIQUE(name, model_id)",
        "An AI helper with the same name already exists for this model.",
    )
    _model_type_unique = models.Constraint(
        "UNIQUE(model_id, ai_type_id)",
        "Only one AI helper can exist per model and AI type.",
    )

    def _normalize_text_value(self, value):
        return (value or "").replace("\u00a0", " ").strip()

    def _serialize_record_value(self, record, model_field):
        self.ensure_one()
        value = record[model_field.name]
        if model_field.ttype == "many2one":
            return value.display_name if value else ""
        if model_field.ttype == "binary":
            return "[binary content omitted]"
        if model_field.ttype == "html":
            return self._normalize_text_value(html2plaintext(html_sanitize(value or "")))
        if model_field.ttype in ("one2many", "many2many"):
            return ", ".join(value.mapped("display_name"))
        if model_field.ttype == "boolean":
            return "true" if value else "false"
        if model_field.ttype in ("date", "datetime"):
            return value.isoformat() if value else ""
        if model_field.ttype == "json":
            return json.dumps(value or {}, ensure_ascii=False, indent=2)
        return self._normalize_text_value("" if value in (False, None) else str(value))

    def build_prompt_values(self, record):
        self.ensure_one()
        values = {}
        for line in self.field_line_ids.sorted(key=lambda field_line: (field_line.sequence, field_line.id)):
            values[line.placeholder] = self._serialize_record_value(record, line.field_id)
        return values

    def render_prompt(self, record):
        self.ensure_one()
        values = self.build_prompt_values(record)
        rendered_prompt = self.prompt_template or ""
        for placeholder, value in values.items():
            rendered_prompt = rendered_prompt.replace(f"{{{{ {placeholder} }}}}", value)
            rendered_prompt = rendered_prompt.replace(f"{{{{{placeholder}}}}}", value)
            rendered_prompt = rendered_prompt.replace(f"{{{placeholder}}}", value)
        return {
            "prompt": rendered_prompt.strip(),
            "values": values,
            "values_json": json.dumps(values, ensure_ascii=False, indent=2),
        }

    def render_image_prompt(self, record):
        self.ensure_one()
        rendered = self.render_prompt(record)
        prompt = rendered["prompt"]
        if rendered["values"]:
            context_block = (
                "Use the following record field context when generating the image.\n"
                "Field values:\n"
                f"{rendered['values_json']}"
            )
            prompt = f"{prompt}\n\n{context_block}".strip() if prompt else context_block
        return {
            **rendered,
            "prompt": prompt,
        }

    @api.constrains("target_field_id", "model_id", "ai_type_id")
    def _check_target_field(self):
        for rec in self:
            if not rec.target_field_id or not rec.model_id:
                continue
            if rec.target_field_id.model_id != rec.model_id:
                raise ValidationError("The target field must belong to the selected model.")

            target_type = rec.target_field_id.ttype
            type_name = (rec.ai_type_id.name or "").strip().lower()
            if "image" in type_name and target_type not in IMAGE_TARGET_TYPES:
                raise ValidationError("Image AI helpers must write to a binary field.")
            if "image" not in type_name and target_type not in TEXT_TARGET_TYPES:
                raise ValidationError("This AI helper type must write to a char, text, html, or json field.")


class MgAIHelperField(models.Model):
    _name = "mg.ai.helper.field"
    _description = "AI Helper Source Field"
    _order = "sequence, id"

    helper_id = fields.Many2one(
        comodel_name="mg.ai.helper",
        string="AI Helper",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Source Field",
        required=True,
        ondelete="cascade",
    )
    placeholder = fields.Char(
        required=True,
        help="Variable name to use in the prompt template, for example product_name or description.",
    )
    field_description = fields.Char(related="field_id.field_description", readonly=True)
    field_type = fields.Selection(related="field_id.ttype", readonly=True)

    _helper_field_unique = models.Constraint(
        "UNIQUE(helper_id, field_id)",
        "The same source field cannot be added twice to one AI helper.",
    )
    _helper_placeholder_unique = models.Constraint(
        "UNIQUE(helper_id, placeholder)",
        "The placeholder must be unique inside one AI helper.",
    )

    @api.onchange("field_id")
    def _onchange_field_id(self):
        for rec in self:
            if rec.field_id and not rec.placeholder:
                rec.placeholder = rec.field_id.name

    @api.constrains("field_id", "helper_id")
    def _check_field_model(self):
        for rec in self:
            if rec.field_id and rec.helper_id and rec.field_id.model_id != rec.helper_id.model_id:
                raise ValidationError("Source fields must belong to the selected model.")
            if rec.field_id and rec.field_id.ttype not in SOURCE_FIELD_TYPES:
                raise ValidationError("This source field type is not supported for AI helper input.")

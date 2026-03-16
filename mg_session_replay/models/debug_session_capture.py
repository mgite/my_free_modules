import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

MAX_RECORDING_LENGTH = 1000000


class DebugSessionCapture(models.Model):
    _name = "debug.session.capture"
    _description = "Debug Session Capture"
    _order = "captured_at desc, id desc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    captured_at = fields.Datetime(
        string="Captured At",
        required=True,
        readonly=True,
        copy=False,
        default=fields.Datetime.now,
        help="Stored in UTC by Odoo and converted to each user's timezone in the interface.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        index=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    duration_seconds = fields.Integer(
        string="Duration (seconds)",
        required=True,
        default=lambda self: self._default_duration_seconds(),
        help="Number of buffered seconds included in this capture.",
    )
    recording = fields.Text(
        string="Recording",
        required=True,
        help="Serialized session replay payload captured from the browser.",
    )
    ai_analysis_html = fields.Html(string="AI Analysis", readonly=True, sanitize=False)

    @api.model
    def _default_duration_seconds(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "mg_session_replay.recording_duration_seconds",
            default="35",
        )
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            return 35

    @api.depends("captured_at", "user_id")
    def _compute_name(self):
        for record in self:
            if record.captured_at:
                timestamp = fields.Datetime.to_string(record.captured_at)
            else:
                timestamp = "pending"
            user_name = record.user_id.name or "Unknown User"
            record.name = f"{user_name} - {timestamp}"

    @api.constrains("duration_seconds")
    def _check_duration_seconds(self):
        for record in self:
            if record.duration_seconds <= 0:
                raise ValidationError("Capture duration must be greater than zero.")

    @api.model
    def action_raise_test_error(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError("This action is only available to administrators.")
        raise RuntimeError("Session Replay test error triggered manually.")

    @api.model
    def create_capture_from_payload(self, payload):
        payload = payload or {}
        duration_seconds = payload.get("duration_seconds", self._default_duration_seconds())
        try:
            duration_seconds = max(int(duration_seconds), 1)
        except (TypeError, ValueError):
            duration_seconds = self._default_duration_seconds()

        recording_payload = payload.get("recording") or {}
        if isinstance(recording_payload, str):
            recording = recording_payload
        else:
            recording = json.dumps(recording_payload, ensure_ascii=True, default=str)

        if len(recording) > MAX_RECORDING_LENGTH:
            recording = json.dumps(
                {
                    "truncated": True,
                    "excerpt": recording[: MAX_RECORDING_LENGTH - 100],
                },
                ensure_ascii=True,
            )

        values = {
            "user_id": self.env.user.id,
            "duration_seconds": duration_seconds,
            "recording": recording,
        }

        return self.sudo().create(
            values
        )

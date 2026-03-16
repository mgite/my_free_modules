from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mg_session_replay_recording_duration_seconds = fields.Integer(
        string="Recording Duration Before Error (seconds)",
        default=35,
        config_parameter="mg_session_replay.recording_duration_seconds",
        help="Number of seconds kept in the client-side rolling replay buffer before an error is saved.",
    )

    @api.constrains("mg_session_replay_recording_duration_seconds")
    def _check_mg_session_replay_recording_duration_seconds(self):
        for record in self:
            if record.mg_session_replay_recording_duration_seconds <= 0:
                raise ValidationError("Recording duration before error must be greater than zero.")

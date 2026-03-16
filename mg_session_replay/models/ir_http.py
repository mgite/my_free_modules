from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        duration = self.env["ir.config_parameter"].sudo().get_param(
            "mg_session_replay.recording_duration_seconds",
            default="35",
        )
        try:
            duration = max(int(duration), 1)
        except (TypeError, ValueError):
            duration = 35

        result["mg_session_replay"] = {
            "recording_duration_seconds": duration,
        }
        return result

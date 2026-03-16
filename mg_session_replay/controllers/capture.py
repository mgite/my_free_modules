from odoo import http
from odoo.http import request


class SessionReplayController(http.Controller):
    @http.route("/mg_session_replay/capture", type="jsonrpc", auth="user", methods=["POST"])
    def create_capture(self, recording=None, duration_seconds=None):
        record = request.env["debug.session.capture"].create_capture_from_payload(
            {
                "recording": recording,
                "duration_seconds": duration_seconds,
            }
        )
        return {"id": record.id}

from odoo import http
from odoo.http import request


class CommandPaletteController(http.Controller):
    @http.route("/command_palette/search", type="jsonrpc", auth="user", methods=["POST"])
    def command_palette_search(self, query="", limit=8, current_model=None):
        return request.env["command_palette.search_index"].with_context(
            debug=request.session.debug
        ).palette_search(query=query, limit=limit, current_model=current_model)

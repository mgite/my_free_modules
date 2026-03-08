from odoo import models
from odoo.exceptions import AccessError


class CommandPaletteSearchIndex(models.AbstractModel):
    _name = "command_palette.search_index"
    _description = "Command Palette Search Index"

    MIN_QUERY_LENGTH = 2
    MAX_QUERY_LENGTH = 120
    DEFAULT_LIMIT = 8
    MAX_LIMIT = 25
    MAX_RECORD_MODELS = 16
    PER_MODEL_RECORD_LIMIT = 2
    MAX_DEFAULT_ACTIONS = 160
    ACTION_TYPES = [
        "ir.actions.act_window",
        "ir.actions.client",
        "ir.actions.server",
        "ir.actions.report",
        "ir.actions.act_url",
    ]

    def palette_search(self, query="", limit=DEFAULT_LIMIT, current_model=None):
        query = self._normalize_query(query)
        limit = self._normalize_limit(limit)
        current_model = self._normalize_model(current_model)
        if len(query) < self.MIN_QUERY_LENGTH:
            return {"menus": [], "actions": [], "records": []}

        menus_data = self._load_visible_menus()
        menus, menu_models = self._search_menus(query, limit, menus_data)
        actions, action_models = self._search_actions(query, limit, menus_data)

        preferred_models = dict(action_models)
        for model_name, action_id in menu_models.items():
            preferred_models.setdefault(model_name, action_id)

        model_action_map = self._build_record_model_action_map(
            menus_data,
            preferred_models,
            max_models=self.MAX_RECORD_MODELS,
            current_model=current_model,
        )
        records = self._search_records(query, model_action_map, limit)

        return {
            "menus": menus,
            "actions": actions,
            "records": records,
        }

    def _normalize_query(self, query):
        return (query or "").strip()[: self.MAX_QUERY_LENGTH]

    def _normalize_limit(self, limit):
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            parsed_limit = self.DEFAULT_LIMIT
        return max(1, min(parsed_limit, self.MAX_LIMIT))

    def _normalize_model(self, current_model):
        normalized_model = (current_model or "").strip()
        return normalized_model or None

    def _load_visible_menus(self):
        return self.env["ir.ui.menu"].load_web_menus(bool(self.env.context.get("debug")))

    def _search_menus(self, query, limit, menus_data):
        query_l = query.lower()
        parent_map = self._build_parent_map(menus_data)
        matches = []
        window_action_ids = []

        for menu_id, menu in menus_data.items():
            if menu_id == "root":
                continue

            action_id = menu.get("actionID")
            if not action_id:
                continue

            path = self._menu_path(menu_id, menus_data, parent_map)
            score = self._match_score(query_l, menu.get("name") or "", path)
            if score <= 0:
                continue

            matches.append(
                (
                    score,
                    path.lower(),
                    {
                        "id": menu_id,
                        "name": menu.get("name"),
                        "path": path,
                        "action_id": action_id,
                        "action_path": menu.get("actionPath"),
                    },
                )
            )

            if menu.get("actionModel") == "ir.actions.act_window":
                window_action_ids.append(action_id)

        matches.sort(key=lambda item: (-item[0], item[1]))
        menus = [item[2] for item in matches[:limit]]

        model_by_action = self._window_action_models(window_action_ids)
        model_action_map = {}
        for menu in menus:
            action_id = menu["action_id"]
            model_name = model_by_action.get(action_id)
            if model_name and model_name not in model_action_map:
                model_action_map[model_name] = action_id

        return menus, model_action_map

    def _search_actions(self, query, limit, menus_data):
        action_ids = self._visible_action_ids(menus_data)
        if not action_ids:
            return [], {}

        rows = self.env["ir.actions.actions"].sudo().search_read(
            [("id", "in", action_ids), ("name", "ilike", query), ("type", "in", self.ACTION_TYPES)],
            ["name", "type", "path"],
            limit=limit,
            order="name",
        )

        window_ids = [row["id"] for row in rows if row.get("type") == "ir.actions.act_window"]
        model_by_action = self._window_action_models(window_ids)
        model_action_map = {}
        actions = []

        for row in rows:
            action_id = row["id"]
            model_name = model_by_action.get(action_id)
            actions.append(
                {
                    "id": action_id,
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "path": row.get("path"),
                    "res_model": model_name,
                }
            )
            if model_name and model_name not in model_action_map:
                model_action_map[model_name] = action_id

        return actions, model_action_map

    def _build_record_model_action_map(
        self, menus_data, preferred_models, max_models, current_model=None
    ):
        model_action_map = {}
        if current_model:
            model_action_map[current_model] = preferred_models.get(current_model)
        for model_name, action_id in preferred_models.items():
            if model_name not in model_action_map:
                model_action_map[model_name] = action_id
        if len(model_action_map) >= max_models:
            return model_action_map

        action_ids = []
        for menu_id, menu in menus_data.items():
            if menu_id == "root":
                continue
            if menu.get("actionModel") != "ir.actions.act_window":
                continue
            action_id = menu.get("actionID")
            if action_id:
                action_ids.append(action_id)
                if len(action_ids) >= self.MAX_DEFAULT_ACTIONS:
                    break

        model_by_action = self._window_action_models(action_ids)
        for action_id in action_ids:
            model_name = model_by_action.get(action_id)
            if model_name and model_name not in model_action_map:
                model_action_map[model_name] = action_id
            if len(model_action_map) >= max_models:
                break

        return model_action_map

    def _search_records(self, query, model_action_map, limit):
        if not model_action_map:
            return []

        results = []
        for model_name, action_id in model_action_map.items():
            if len(results) >= limit:
                break
            if model_name not in self.env:
                continue

            model = self.env[model_name]
            if model._abstract or model._transient:
                continue
            if not model.check_access_rights("read", raise_exception=False):
                continue

            fetch_limit = min(self.PER_MODEL_RECORD_LIMIT, limit - len(results))
            if fetch_limit <= 0:
                break

            try:
                names = model.name_search(name=query, operator="ilike", limit=fetch_limit)
            except (AccessError, ValueError):
                continue
            except Exception:
                continue

            if not names:
                continue

            model_label = model._description or model_name
            for record_id, display_name in names:
                results.append(
                    {
                        "id": record_id,
                        "name": display_name,
                        "model": model_name,
                        "model_label": model_label,
                        "action_id": action_id,
                    }
                )
                if len(results) >= limit:
                    break

        return results

    def _window_action_models(self, action_ids):
        unique_ids = list(dict.fromkeys(int(action_id) for action_id in action_ids if action_id))
        if not unique_ids:
            return {}
        actions = self.env["ir.actions.act_window"].sudo().browse(unique_ids).exists()
        return {action.id: action.res_model for action in actions if action.res_model}

    @staticmethod
    def _visible_action_ids(menus_data):
        return list(
            dict.fromkeys(
                menu.get("actionID")
                for menu_id, menu in menus_data.items()
                if menu_id != "root" and menu.get("actionID")
            )
        )

    @staticmethod
    def _build_parent_map(menus_data):
        parent_map = {}
        for menu_id, menu in menus_data.items():
            if menu_id == "root":
                continue
            for child_id in menu.get("children", []):
                parent_map[child_id] = menu_id
        return parent_map

    @staticmethod
    def _menu_path(menu_id, menus_data, parent_map):
        labels = []
        current_id = menu_id
        seen = set()
        while current_id and current_id != "root" and current_id not in seen:
            seen.add(current_id)
            menu = menus_data.get(current_id)
            if not menu:
                break
            label = menu.get("name")
            if label:
                labels.append(label)
            current_id = parent_map.get(current_id)
        return " / ".join(reversed(labels))

    @staticmethod
    def _match_score(query_l, name, path):
        name_l = (name or "").lower()
        path_l = (path or "").lower()
        if name_l.startswith(query_l):
            return 300
        if f" / {query_l}" in path_l:
            return 260
        if query_l in name_l:
            return 220
        if query_l in path_l:
            return 160
        return 0

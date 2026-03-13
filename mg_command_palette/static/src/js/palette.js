/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const commandCategoryRegistry = registry.category("command_categories");
const commandProviderRegistry = registry.category("command_provider");

function getCurrentModel(actionService) {
    const currentController = actionService.currentController;
    return (
        currentController?.props?.resModel ||
        currentController?.action?.res_model ||
        actionService.currentAction?.res_model ||
        null
    );
}

commandCategoryRegistry.add("command_palette_menu", { name: _t("Menus") }, { sequence: 30 });
commandCategoryRegistry.add("command_palette_action", { name: _t("Actions") }, { sequence: 40 });
commandCategoryRegistry.add("command_palette_record", { name: _t("Records") }, { sequence: 50 });

commandProviderRegistry.add("command_palette.global_search", {
    async provide(env, options = {}) {
        const query = (options.searchValue || "").trim();
        if (query.length < 2) {
            return [];
        }

        const searchService = env.services.command_palette_search;
        const menuService = env.services.menu;
        const actionService = env.services.action;
        const { menus, actions, records } = await searchService.search(query, {
            currentModel: getCurrentModel(actionService),
        });
        const commands = [];

        for (const menu of menus) {
            commands.push({
                name: menu.path || menu.name,
                category: "command_palette_menu",
                href: menu.action_path ? `/odoo/${menu.action_path}` : undefined,
                action() {
                    const loadedMenu = menuService.getMenu(menu.id);
                    if (loadedMenu) {
                        return menuService.selectMenu(loadedMenu);
                    }
                    if (menu.action_id) {
                        return actionService.doAction(menu.action_id, { clearBreadcrumbs: true });
                    }
                },
            });
        }

        for (const item of actions) {
            commands.push({
                name: item.name,
                category: "command_palette_action",
                href: item.path ? `/odoo/${item.path}` : `/odoo/action-${item.id}`,
                action() {
                    return actionService.doAction(item.id, { clearBreadcrumbs: true });
                },
            });
        }

        for (const record of records) {
            commands.push({
                name: `${record.name} (${record.model_label})`,
                category: "command_palette_record",
                action() {
                    return actionService.doAction({
                        type: "ir.actions.act_window",
                        res_model: record.model,
                        res_id: record.id,
                        views: [[false, "form"]],
                        target: "current",
                    });
                },
            });
        }

        return commands;
    },
});

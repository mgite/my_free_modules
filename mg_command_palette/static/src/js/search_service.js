/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

const CACHE_SIZE = 40;
const DEFAULT_LIMIT = 8;
const MIN_QUERY_LENGTH = 2;

function emptyResult() {
    return {
        menus: [],
        actions: [],
        records: [],
    };
}

export const commandPaletteSearchService = {
    start() {
        const cache = new Map();
        const pending = new Map();

        function pruneCache() {
            while (cache.size > CACHE_SIZE) {
                const firstKey = cache.keys().next().value;
                cache.delete(firstKey);
            }
        }

        async function search(query, limitOrOptions = DEFAULT_LIMIT) {
            const normalizedQuery = (query || "").trim();
            if (normalizedQuery.length < MIN_QUERY_LENGTH) {
                return emptyResult();
            }

            const options =
                typeof limitOrOptions === "object" && limitOrOptions !== null
                    ? limitOrOptions
                    : { limit: limitOrOptions };
            const normalizedLimit = Math.max(
                1,
                Math.min(Number(options.limit) || DEFAULT_LIMIT, 25)
            );
            const normalizedModel = (options.currentModel || "").trim();
            const cacheKey = `${normalizedLimit}:${normalizedModel}:${normalizedQuery.toLowerCase()}`;

            if (cache.has(cacheKey)) {
                return cache.get(cacheKey);
            }
            if (pending.has(cacheKey)) {
                return pending.get(cacheKey);
            }

            const request = rpc("/command_palette/search", {
                query: normalizedQuery,
                limit: normalizedLimit,
                current_model: normalizedModel || false,
            })
                .then((result) => {
                    const normalizedResult = {
                        menus: Array.isArray(result?.menus) ? result.menus : [],
                        actions: Array.isArray(result?.actions) ? result.actions : [],
                        records: Array.isArray(result?.records) ? result.records : [],
                    };
                    cache.set(cacheKey, normalizedResult);
                    pruneCache();
                    pending.delete(cacheKey);
                    return normalizedResult;
                })
                .catch(() => {
                    pending.delete(cacheKey);
                    return emptyResult();
                });

            pending.set(cacheKey, request);
            return request;
        }

        return {
            search,
            clearCache() {
                cache.clear();
                pending.clear();
            },
        };
    },
};

registry.category("services").add("command_palette_search", commandPaletteSearchService);

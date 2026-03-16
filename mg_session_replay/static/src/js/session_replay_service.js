/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { rpc, rpcBus } from "@web/core/network/rpc";
import { session } from "@web/session";

const DEFAULT_DURATION_SECONDS = 35;
const MAX_EVENTS = 500;
const MAX_RPCS = 25;
const MAX_STRING_LENGTH = 300;
const MAX_VALUE_LENGTH = 120;
const SCROLL_THROTTLE_MS = 200;
const MOUSEMOVE_THROTTLE_MS = 250;
const UPLOAD_COOLDOWN_MS = 5000;
const SENSITIVE_FIELD_PATTERN = /(pass|password|token|secret|key|credit|card|iban|api)/i;

function now() {
    return Date.now();
}

function truncate(value, maxLength = MAX_STRING_LENGTH) {
    if (value === undefined || value === null) {
        return value;
    }
    const normalized = String(value);
    return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}...` : normalized;
}

function safeSerialize(value, depth = 0, seen = new WeakSet()) {
    if (value === null || value === undefined) {
        return value;
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return truncate(value);
    }
    if (typeof value === "bigint") {
        return value.toString();
    }
    if (typeof value === "function") {
        return `[Function ${value.name || "anonymous"}]`;
    }
    if (value instanceof Error) {
        return {
            name: value.name,
            message: truncate(value.message),
            stack: truncate(value.stack, 1000),
        };
    }
    if (value instanceof Element) {
        return buildElementSelector(value);
    }
    if (depth >= 2) {
        return truncate(Object.prototype.toString.call(value));
    }
    if (Array.isArray(value)) {
        return value.slice(0, 10).map((item) => safeSerialize(item, depth + 1, seen));
    }
    if (typeof value === "object") {
        if (seen.has(value)) {
            return "[Circular]";
        }
        seen.add(value);
        const result = {};
        for (const [key, item] of Object.entries(value).slice(0, 10)) {
            result[key] = safeSerialize(item, depth + 1, seen);
        }
        seen.delete(value);
        return result;
    }
    return truncate(String(value));
}

function buildElementSelector(target) {
    if (!(target instanceof Element)) {
        return "";
    }
    const parts = [];
    let current = target;
    let depth = 0;

    while (current && depth < 4) {
        let part = current.tagName.toLowerCase();
        if (current.id) {
            part += `#${truncate(current.id, 40)}`;
            parts.unshift(part);
            break;
        }
        const classNames = Array.from(current.classList || []).filter(Boolean).slice(0, 2);
        if (classNames.length) {
            part += `.${classNames.join(".")}`;
        }
        if (current.getAttribute("name")) {
            part += `[name="${truncate(current.getAttribute("name"), 30)}"]`;
        }
        parts.unshift(part);
        current = current.parentElement;
        depth += 1;
    }

    return parts.join(" > ");
}

function isSensitiveField(target) {
    if (!(target instanceof HTMLElement)) {
        return false;
    }
    const fieldName = [
        target.getAttribute("name"),
        target.getAttribute("autocomplete"),
        target.getAttribute("id"),
    ]
        .filter(Boolean)
        .join(" ");
    return target.type === "password" || SENSITIVE_FIELD_PATTERN.test(fieldName);
}

function readInputValue(target) {
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement)) {
        return undefined;
    }
    if (isSensitiveField(target)) {
        return "[masked]";
    }
    if (target instanceof HTMLInputElement) {
        if (target.type === "checkbox" || target.type === "radio") {
            return Boolean(target.checked);
        }
        if (target.type === "file") {
            return `[files:${target.files?.length || 0}]`;
        }
    }
    return truncate(target.value, MAX_VALUE_LENGTH);
}

function throttle(callback, delay) {
    let lastExecution = 0;
    return (...args) => {
        const timestamp = now();
        if (timestamp - lastExecution < delay) {
            return;
        }
        lastExecution = timestamp;
        callback(...args);
    };
}

function extractMutationSummary(mutations) {
    const summary = {
        added: 0,
        removed: 0,
        attributes: 0,
        text: 0,
        targets: [],
    };
    const targets = new Set();

    for (const mutation of mutations) {
        summary.added += mutation.addedNodes?.length || 0;
        summary.removed += mutation.removedNodes?.length || 0;
        if (mutation.type === "attributes") {
            summary.attributes += 1;
        }
        if (mutation.type === "characterData") {
            summary.text += 1;
        }
        const target = mutation.target instanceof Element ? mutation.target : mutation.target?.parentElement;
        const selector = buildElementSelector(target);
        if (selector) {
            targets.add(selector);
        }
    }

    summary.targets = Array.from(targets).slice(0, 5);
    return summary;
}

function serializeCapturedError(error, originalError) {
    return {
        name: error?.name || "Error",
        message: truncate(error?.message || originalError?.message || "Unknown error", 500),
        traceback: truncate(error?.traceback || originalError?.stack || "", 4000),
        original: safeSerialize(originalError),
    };
}

export const sessionReplayService = {
    dependencies: ["menu", "title"],
    start(env, { menu, title }) {
        const configuredDuration = Number(
            session.mg_session_replay?.recording_duration_seconds || DEFAULT_DURATION_SECONDS
        );
        const state = {
            durationSeconds: Math.max(1, configuredDuration || DEFAULT_DURATION_SECONDS),
            events: [],
            recentRPCs: [],
            uploadInProgress: false,
            lastUploadAt: 0,
            lastFingerprint: "",
        };

        const originalConsoleError = browser.console.error.bind(browser.console);

        function pruneEvents() {
            const cutoff = now() - state.durationSeconds * 1000;
            while (state.events.length && state.events[0].timestamp < cutoff) {
                state.events.shift();
            }
            while (state.events.length > MAX_EVENTS) {
                state.events.shift();
            }
        }

        function pushEvent(type, payload = {}) {
            state.events.push({
                timestamp: now(),
                type,
                payload,
            });
            pruneEvents();
        }

        function rememberRPCRequest(detail) {
            const entry = {
                id: detail.data.id,
                timestamp: now(),
                url: detail.url,
                model: detail.data.params?.model || "",
                method: detail.data.params?.method || "",
            };
            state.recentRPCs.push(entry);
            while (state.recentRPCs.length > MAX_RPCS) {
                state.recentRPCs.shift();
            }
        }

        function rememberRPCResponse(detail) {
            const entry = [...state.recentRPCs].reverse().find((item) => item.id === detail.data.id);
            if (!entry) {
                return;
            }
            entry.completedAt = now();
            entry.durationMs = entry.completedAt - entry.timestamp;
            if (detail.error) {
                entry.error = safeSerialize(detail.error);
            } else {
                entry.result = "ok";
            }
        }

        function buildRecordingPayload(error, originalError) {
            const currentApp = menu.getCurrentApp ? menu.getCurrentApp() : null;
            return {
                version: 1,
                captured_at_client: new Date().toISOString(),
                duration_seconds: state.durationSeconds,
                location: {
                    href: browser.location.href,
                    pathname: browser.location.pathname,
                    hash: browser.location.hash,
                    title: title.current,
                },
                viewport: {
                    width: browser.innerWidth,
                    height: browser.innerHeight,
                    scroll_x: window.scrollX,
                    scroll_y: window.scrollY,
                },
                browser: {
                    user_agent: browser.navigator.userAgent,
                    language: browser.navigator.language,
                    platform: browser.navigator.platform,
                    online: browser.navigator.onLine,
                },
                menu: currentApp
                    ? {
                          id: currentApp.id,
                          name: currentApp.name,
                          xmlid: currentApp.xmlid,
                      }
                    : null,
                error: serializeCapturedError(error, originalError),
                recent_rpc: state.recentRPCs.slice(-MAX_RPCS),
                events: state.events.slice(),
            };
        }

        async function captureError(error, originalError) {
            const fingerprint = [
                error?.name || "",
                error?.message || "",
                originalError?.name || "",
                originalError?.message || "",
            ].join("|");
            const timestamp = now();

            if (state.uploadInProgress) {
                return;
            }
            if (
                state.lastFingerprint === fingerprint &&
                timestamp - state.lastUploadAt < UPLOAD_COOLDOWN_MS
            ) {
                return;
            }

            state.uploadInProgress = true;
            state.lastUploadAt = timestamp;
            state.lastFingerprint = fingerprint;
            pushEvent("capture_requested", { fingerprint: truncate(fingerprint, 120) });

            try {
                await rpc(
                    "/mg_session_replay/capture",
                    {
                        recording: buildRecordingPayload(error, originalError),
                        duration_seconds: state.durationSeconds,
                    },
                    { silent: true }
                );
            } catch (captureError) {
                originalConsoleError("Session Replay capture upload failed", captureError);
            } finally {
                state.uploadInProgress = false;
            }
        }

        const onClick = (event) => {
            pushEvent("click", {
                target: buildElementSelector(event.target),
                x: event.clientX,
                y: event.clientY,
            });
        };
        const onInput = (event) => {
            pushEvent("input", {
                target: buildElementSelector(event.target),
                value: readInputValue(event.target),
            });
        };
        const onChange = (event) => {
            pushEvent("change", {
                target: buildElementSelector(event.target),
                value: readInputValue(event.target),
            });
        };
        const onScroll = throttle(() => {
            pushEvent("scroll", {
                x: window.scrollX,
                y: window.scrollY,
            });
        }, SCROLL_THROTTLE_MS);
        const onMouseMove = throttle((event) => {
            pushEvent("mousemove", {
                x: event.clientX,
                y: event.clientY,
            });
        }, MOUSEMOVE_THROTTLE_MS);

        document.addEventListener("click", onClick, true);
        document.addEventListener("input", onInput, true);
        document.addEventListener("change", onChange, true);
        document.addEventListener("scroll", onScroll, true);
        document.addEventListener("mousemove", onMouseMove, true);

        const mutationObserver = new MutationObserver((mutations) => {
            const summary = extractMutationSummary(mutations);
            if (summary.added || summary.removed || summary.attributes || summary.text) {
                pushEvent("dom_mutation", summary);
            }
        });
        mutationObserver.observe(document.documentElement, {
            subtree: true,
            childList: true,
            attributes: true,
            characterData: true,
        });

        rpcBus.addEventListener("RPC:REQUEST", (event) => rememberRPCRequest(event.detail));
        rpcBus.addEventListener("RPC:RESPONSE", (event) => rememberRPCResponse(event.detail));

        browser.console.error = (...args) => {
            pushEvent("console_error", { args: safeSerialize(args) });
            originalConsoleError(...args);
        };

        pushEvent("session_replay_started", {
            duration_seconds: state.durationSeconds,
        });

        return {
            captureError,
            getDurationSeconds() {
                return state.durationSeconds;
            },
        };
    },
};

registry.category("services").add("mg_session_replay", sessionReplayService);

function sessionReplayErrorHandler(env, error, originalError) {
    env.services.mg_session_replay?.captureError(error, originalError);
    return false;
}

registry
    .category("error_handlers")
    .add("mg_session_replay.capture_error_handler", sessionReplayErrorHandler, { sequence: 10 });

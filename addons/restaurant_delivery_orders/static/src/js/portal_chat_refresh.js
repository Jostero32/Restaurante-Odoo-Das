/** @odoo-module **/

import { registry } from "@web/core/registry";

const REFRESH_INTERVAL_MS = 8000;

const portalChatRefreshService = {
    start(env) {
        if (typeof document === "undefined") {
            return;
        }
        const chatterContainer = document.getElementById("discussion");
        if (!chatterContainer) {
            return;
        }
        if (chatterContainer.dataset.res_model !== "restaurant.delivery.order") {
            return;
        }
        let stopped = false;
        const tick = () => {
            if (stopped) {
                return;
            }
            if (document.hidden) {
                return;
            }
            env.bus.trigger("reload_chatter_content", {});
        };
        const intervalId = window.setInterval(tick, REFRESH_INTERVAL_MS);
        window.addEventListener("beforeunload", () => {
            stopped = true;
            window.clearInterval(intervalId);
        });
    },
};

registry.category("services").add("restaurant_delivery_chat_refresh", portalChatRefreshService);

/** @odoo-module **/

/**
 * FloorScreen kitchen-status integration — Odoo 18 compatible.
 *
 * Odoo 18 removed the standalone Table OWL component; tables are now rendered
 * inline inside the FloorScreen template. Patching Table.prototype no longer
 * works. Instead we:
 *   1. Patch FloorScreen to start the kitchen service polling.
 *   2. Add helpers (kitchenStatusForTable / kitchenStatusLabelForTable) directly
 *      on FloorScreen so templates or DOM code can call them.
 *   3. Apply kitchen-status badges via direct DOM manipulation — the same
 *      approach used by restaurant_table_reservations for reservation badges.
 *      This sidesteps the need for a separate XML template that inherits
 *      `pos_restaurant.Table` (which no longer exists).
 */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { FloorScreen } from "@pos_restaurant/app/floor_screen/floor_screen";

const BADGE_ID = "kitchen-status-badge";

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);

        this.kitchen = useService("kitchen");
        this.kitchenState = useState(this.kitchen.state);

        // Start polling so badges refresh even when the user never opens an order
        this.kitchen.startPolling(12_000);

        // Re-apply badges whenever kitchen state changes or after every Owl render
        onMounted(() => this._applyKitchenBadges());
        onPatched(() => this._applyKitchenBadges());

        // Also re-apply on every kitchen refresh so the badge animates in real time
        // without waiting for the next Owl render cycle.
        this._kitchenUnsubscribe = this.kitchen.onReady(() => this._applyKitchenBadges());

        onWillUnmount(() => {
            if (this._kitchenUnsubscribe) {
                this._kitchenUnsubscribe();
                this._kitchenUnsubscribe = null;
            }
        });
    },

    // ------------------------------------------------------------------
    // Helpers — available on FloorScreen for any caller
    // ------------------------------------------------------------------

    kitchenStatusForTable(table) {
        if (!table) return null;
        const tableId = table.id ?? table;
        const orders = this.kitchenState.byTable?.[tableId] || [];
        if (orders.some((o) => o.state === "ready"))     return "ready";
        if (orders.some((o) => o.state === "preparing")) return "preparing";
        if (orders.some((o) => o.state === "new"))       return "new";
        return null;
    },

    kitchenStatusLabelForTable(table) {
        const status = this.kitchenStatusForTable(table);
        return { ready: "Lista", preparing: "En preparacion", new: "Nueva" }[status] || "";
    },

    // ------------------------------------------------------------------
    // DOM badge — applied after every render and every kitchen refresh
    // ------------------------------------------------------------------

    _applyKitchenBadges() {
        if (!this.map?.el) return;

        // Each table element carries the class "tableId-{id}" (Odoo 18 template)
        for (const el of this.map.el.querySelectorAll("[class*='tableId-']")) {
            const tableId = this._kitchenTableIdFromElement(el);
            if (!tableId) continue;

            const status = this.kitchenStatusForTable(tableId);
            const label  = this.kitchenStatusLabelForTable(tableId);

            // Remove stale badge first
            el.querySelector(`[data-${BADGE_ID}]`)?.remove();

            if (!status) continue;

            // Ensure the table div is position:relative so the badge stays in corner
            if (getComputedStyle(el).position === "static") {
                el.style.position = "relative";
            }

            const badge = document.createElement("span");
            badge.setAttribute(`data-${BADGE_ID}`, "1");
            badge.className = `kitchen-table-status ${status}`;
            badge.title = `Cocina: ${label}`;
            badge.innerHTML = '<i class="fa fa-cutlery" aria-hidden="true"></i>';
            el.appendChild(badge);
        }
    },

    _kitchenTableIdFromElement(el) {
        const cls = [...el.classList].find((c) => c.startsWith("tableId-"));
        if (cls) {
            const v = Number(cls.split("-")[1]);
            if (!Number.isNaN(v)) return v;
        }
        return null;
    },
});

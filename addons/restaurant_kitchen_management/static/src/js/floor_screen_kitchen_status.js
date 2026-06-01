/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { FloorScreen } from "@pos_restaurant/app/floor_screen/floor_screen";

/**
 * Patch al FloorScreen: agrega utilidades reactivas para que la UI
 * muestre si una mesa tiene ordenes nuevas / en preparacion / listas.
 *
 * El template t-inherit en kitchen_floor_badges.xml usa estas helpers
 * para pintar un indicador visual sobre cada mesa.
 */
patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useService("kitchen");
        this.kitchenState = useState(this.kitchen.state);
        // Aseguramos que el polling este activo aunque el usuario haya
        // entrado directo al FloorScreen sin pasar por ProductScreen.
        this.kitchen.startPolling(12000);
    },

    /**
     * Devuelve el estado de cocina mas relevante para una mesa.
     * Prioridad: ready > preparing > new > null
     */
    kitchenStatusForTable(table) {
        if (!table) return null;
        const tableId = table.id || table;
        const orders = (this.kitchenState.byTable && this.kitchenState.byTable[tableId]) || [];
        if (orders.some((o) => o.state === "ready")) return "ready";
        if (orders.some((o) => o.state === "preparing")) return "preparing";
        if (orders.some((o) => o.state === "new")) return "new";
        return null;
    },

    kitchenStatusClassForTable(table) {
        const status = this.kitchenStatusForTable(table);
        return {
            ready: "kitchen-table-status ready",
            preparing: "kitchen-table-status preparing",
            new: "kitchen-table-status new",
        }[status] || "";
    },

    kitchenStatusLabelForTable(table) {
        const status = this.kitchenStatusForTable(table);
        return {
            ready: "Lista",
            preparing: "En preparacion",
            new: "Nueva",
        }[status] || "";
    },
});

/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { FloorScreen } from "@pos_restaurant/app/floor_screen/floor_screen";
import { Table } from "@pos_restaurant/app/floor_screen/table";

/**
 * Patch al FloorScreen: solo arranca el polling del servicio kitchen
 * para que este activo aunque el usuario entre directo al FloorScreen
 * sin pasar por ProductScreen.
 */
patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useService("kitchen");
        this.kitchen.startPolling(12000);
    },
});

/**
 * Patch al componente Table: inyecta el servicio kitchen y expone los
 * helpers que usa kitchen_floor_badges.xml para pintar el badge de estado.
 *
 * El template hereda pos_restaurant.Table, por lo que su contexto "this"
 * es la instancia de Table, NO de FloorScreen. Los metodos deben vivir aqui.
 */
patch(Table.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useService("kitchen");
        this.kitchenState = useState(this.kitchen.state);
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

    kitchenStatusLabelForTable(table) {
        const status = this.kitchenStatusForTable(table);
        return {
            ready: "Lista",
            preparing: "En preparacion",
            new: "Nueva",
        }[status] || "";
    },
});

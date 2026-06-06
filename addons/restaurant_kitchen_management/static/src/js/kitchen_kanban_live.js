/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";

const KITCHEN_MODEL = "restaurant.kitchen.order";
const KITCHEN_BUS_CHANNEL = "restaurant_kitchen_management.kitchen";
const KITCHEN_BUS_NOTIFICATION = "restaurant_kitchen_management.kitchen_changed";

/**
 * Suscribe el controlador (Kanban o List) de ordenes de cocina al canal del
 * bus para recargar los datos en tiempo real cuando llegan o cambian ordenes
 * desde POS, delivery o el propio backend.
 *
 * Solo actua cuando el modelo del controlador es restaurant.kitchen.order, por
 * lo que no afecta a las demas vistas Kanban/List del sistema.
 */
function setupKitchenLiveReload() {
    if (this.props.resModel !== KITCHEN_MODEL) {
        return;
    }
    const busService = useService("bus_service");
    let reloadTimer = null;

    const scheduleReload = () => {
        if (reloadTimer) {
            clearTimeout(reloadTimer);
        }
        // Debounce: si llegan varias senales seguidas (p.ej. un POS enviando
        // varias lineas) recargamos una sola vez.
        reloadTimer = setTimeout(() => {
            reloadTimer = null;
            try {
                const res = this.model.load();
                if (res && typeof res.catch === "function") {
                    res.catch((e) => console.warn("[kitchen] kanban reload failed:", e));
                }
            } catch (e) {
                console.warn("[kitchen] kanban reload error:", e);
            }
        }, 400);
    };

    const onKitchenChanged = () => scheduleReload();

    try {
        busService.addChannel(KITCHEN_BUS_CHANNEL);
        busService.subscribe(KITCHEN_BUS_NOTIFICATION, onKitchenChanged);
    } catch (e) {
        console.warn("[kitchen] bus channel setup failed:", e);
    }

    onWillUnmount(() => {
        if (reloadTimer) {
            clearTimeout(reloadTimer);
        }
        try {
            busService.unsubscribe(KITCHEN_BUS_NOTIFICATION, onKitchenChanged);
        } catch (e) {
            /* noop */
        }
    });
}

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        setupKitchenLiveReload.call(this);
    },
});

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        setupKitchenLiveReload.call(this);
    },
});

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

const KITCHEN_BUS_CHANNEL = "restaurant_kitchen_management.kitchen";
const KITCHEN_BUS_NOTIFICATION = "restaurant_kitchen_management.kitchen_changed";

/**
 * Servicio de cocina para el POS.
 *
 * Expone:
 *  - Llamadas RPC a restaurant.kitchen.order:
 *      sendToKitchen, fetchActiveOrders, markServed
 *  - Un store reactivo con las ordenes activas (new / preparing / ready)
 *      state.orders         -> lista plana de ordenes
 *      state.readyOrders    -> solo state='ready'
 *      state.byTable        -> { table_id: [orders] }
 *      state.lastRefresh    -> timestamp del ultimo refresh exitoso
 *  - Polling automatico (startPolling / stopPolling / refreshNow)
 *
 * Los componentes OWL del POS pueden hacer `useState` sobre `state`
 * para actualizarse cuando llegue una orden lista.
 */
export const kitchenService = {
    dependencies: ["orm", "pos", "bus_service", "notification"],

    start(env, { orm, pos, bus_service, notification }) {
        const state = reactive({
            orders: [],
            readyOrders: [],
            byTable: {},
            lastRefresh: null,
            polling: false,
        });

        let pollTimer = null;
        let lastReadyIds = new Set();
        let firstIndex = true;
        const readyListeners = new Set();

        function _indexOrders(orders) {
            // Mutar in-place para preservar las referencias de los objetos
            // reactivos. Si reasignamos `state.orders = ...` los componentes
            // que hicieron useState sobre una sub-propiedad pueden no
            // re-renderizar.
            state.orders.splice(0, state.orders.length, ...orders);
            state.readyOrders.splice(
                0,
                state.readyOrders.length,
                ...orders.filter((o) => o.state === "ready"),
            );

            // Limpiar byTable manteniendo la misma referencia de objeto.
            for (const key of Object.keys(state.byTable)) {
                delete state.byTable[key];
            }
            for (const o of orders) {
                if (!o.table_id) continue;
                if (!state.byTable[o.table_id]) {
                    state.byTable[o.table_id] = [];
                }
                state.byTable[o.table_id].push(o);
            }
            state.lastRefresh = Date.now();

            // Detectar ordenes que pasaron a ready desde el ultimo refresh
            const currentReadyIds = new Set(state.readyOrders.map((o) => o.id));
            const newlyReady = state.readyOrders.filter((o) => !lastReadyIds.has(o.id));
            lastReadyIds = currentReadyIds;
            if (firstIndex) {
                // Primer refresco al abrir el POS: solo sembramos el estado,
                // sin avisar de ordenes que ya estaban listas de antes.
                firstIndex = false;
            } else if (newlyReady.length > 0) {
                // Notificacion centralizada en el servicio: aparece sin importar
                // en que pantalla del POS este el cajero.
                for (const order of newlyReady) {
                    const tableLabel = order.table_name ? ` · ${order.table_name}` : "";
                    notification.add(
                        _t("Cocina lista para servir: ") + order.name + tableLabel,
                        { type: "success", sticky: false },
                    );
                }
                for (const listener of readyListeners) {
                    try {
                        listener(newlyReady);
                    } catch (e) {
                        console.warn("[kitchen] listener error:", e);
                    }
                }
            }
        }

        async function refreshNow() {
            const sessionId = pos.session && pos.session.id;
            try {
                const orders = await orm.call(
                    "restaurant.kitchen.order",
                    "get_orders_for_pos",
                    [sessionId || false, ["new", "preparing", "ready"]],
                );
                _indexOrders(orders || []);
                return orders;
            } catch (e) {
                console.warn("[kitchen] refresh failed:", e);
                return [];
            }
        }

        function startPolling(intervalMs = 12000) {
            if (pollTimer) return;
            state.polling = true;
            // Primer refresh inmediato
            refreshNow();
            pollTimer = setInterval(refreshNow, intervalMs);
        }

        function stopPolling() {
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
            state.polling = false;
        }

        /**
         * Permite suscribirse a "nuevas ordenes que pasaron a ready".
         * Retorna funcion de unsubscribe.
         */
        function onReady(callback) {
            readyListeners.add(callback);
            return () => readyListeners.delete(callback);
        }

        // Suscripcion al bus: cuando el backend (o el POS) emite un cambio en
        // una orden de cocina, refrescamos al instante en vez de esperar el
        // polling. El polling queda como red de seguridad por si se pierde la
        // conexion del bus.
        function _setupBusSubscription() {
            try {
                bus_service.addChannel(KITCHEN_BUS_CHANNEL);
                bus_service.subscribe(KITCHEN_BUS_NOTIFICATION, () => {
                    refreshNow();
                });
            } catch (e) {
                console.warn("[kitchen] bus subscription failed:", e);
            }
        }
        _setupBusSubscription();

        // Arrancar el polling de respaldo desde el propio servicio, para que el
        // refresco ocurra aunque el cajero nunca abra la pantalla de producto.
        // El bus sigue siendo el camino principal en tiempo real.
        startPolling(30000);

        return {
            state,

            async sendToKitchen(linesData, contextData = {}) {
                const posOrderId = contextData.pos_order_id || false;
                const result = await orm.call(
                    "restaurant.kitchen.order",
                    "create_from_pos",
                    [posOrderId, linesData, contextData],
                );
                // Refresco oportunista
                refreshNow();
                return result;
            },

            async fetchActiveOrders(sessionId, states) {
                return await orm.call(
                    "restaurant.kitchen.order",
                    "get_orders_for_pos",
                    [sessionId || false, states || ["new", "preparing", "ready"]],
                );
            },

            async markServed(kitchenOrderId) {
                const res = await orm.call(
                    "restaurant.kitchen.order",
                    "mark_served_from_pos",
                    [[kitchenOrderId]],
                );
                refreshNow();
                return res;
            },

            startPolling,
            stopPolling,
            refreshNow,
            onReady,
        };
    },
};

registry.category("services").add("kitchen", kitchenService);

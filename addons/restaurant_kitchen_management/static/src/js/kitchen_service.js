/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

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
    dependencies: ["orm", "pos"],

    start(env, { orm, pos }) {
        const state = reactive({
            orders: [],
            readyOrders: [],
            byTable: {},
            lastRefresh: null,
            polling: false,
        });

        let pollTimer = null;
        let lastReadyIds = new Set();
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
            if (newlyReady.length > 0) {
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

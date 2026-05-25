/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Servicio de cocina para el POS.
 *
 * Centraliza las llamadas RPC al modelo restaurant.kitchen.order para:
 *  - enviar productos a cocina desde el POS
 *  - consultar ordenes en preparacion / listas
 *  - marcar una orden como servida
 *
 * Se inyecta como `kitchen` en los componentes OWL del POS.
 */
export const kitchenService = {
    dependencies: ["orm", "pos"],

    start(env, { orm, pos }) {
        return {
            /**
             * Envia las lineas preparables del pedido actual a cocina.
             * @param {Array} linesData - lista de {product_id, quantity, line_note, source_pos_line_uuid}
             * @param {Object} contextData - {table_id, partner_id, session_id, pos_order_id}
             */
            async sendToKitchen(linesData, contextData = {}) {
                const posOrderId = contextData.pos_order_id || false;
                return await orm.call(
                    "restaurant.kitchen.order",
                    "create_from_pos",
                    [posOrderId, linesData, contextData],
                );
            },

            /**
             * Devuelve las ordenes de cocina activas para esta sesion POS.
             */
            async fetchActiveOrders(sessionId, states) {
                return await orm.call(
                    "restaurant.kitchen.order",
                    "get_orders_for_pos",
                    [sessionId || false, states || ["new", "preparing", "ready"]],
                );
            },

            /**
             * Marca una orden de cocina como servida desde el POS.
             */
            async markServed(kitchenOrderId) {
                return await orm.call(
                    "restaurant.kitchen.order",
                    "mark_served_from_pos",
                    [[kitchenOrderId]],
                );
            },
        };
    },
};

registry.category("services").add("kitchen", kitchenService);

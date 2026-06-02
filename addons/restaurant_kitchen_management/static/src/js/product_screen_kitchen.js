/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { KitchenReadyPopup } from "@restaurant_kitchen_management/js/kitchen_ready_popup";

/**
 * Extiende los botones de control de la pantalla de producto del POS para:
 *  - "Enviar a cocina":  manda las lineas preparables al backend.
 *  - "Cocina":           abre el popup con el estado de la cocina.
 *
 * Tambien arranca el polling del servicio kitchen al montar el componente
 * para que el resto de la UI reaccione a cambios (badges en mesas, contador
 * de listos, etc.).
 */
patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useService("kitchen");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        // Estado reactivo del servicio cocina para mostrar el badge
        this.kitchenState = useState(this.kitchen.state);

        // El refresco y las notificaciones de "cocina lista" los gestiona el
        // servicio kitchen (ver kitchen_service.js), de forma independiente de
        // la pantalla en la que este el cajero. El servicio ya arranca su propio
        // polling de respaldo; esta llamada es idempotente y solo refuerza que
        // este activo mientras se usa la pantalla de producto.
        this.kitchen.startPolling(30000);
    },

    /**
     * Construye los datos de las lineas a partir del pedido POS actual.
     */
    _buildKitchenLinesData(order) {
        const lines = order.get_orderlines ? order.get_orderlines() : (order.lines || []);
        const preparable = lines.filter((l) => {
            const product = l.get_product ? l.get_product() : l.product_id;
            return product && product.kitchen_preparable;
        });
        return preparable.map((l) => {
            const product = l.get_product ? l.get_product() : l.product_id;
            const qty = l.get_quantity ? l.get_quantity() : l.qty;
            const note = (l.get_customer_note && l.get_customer_note())
                || (l.customer_note || "")
                || product.kitchen_default_note
                || "";
            const uuid = l.uuid
                || `pos-${order.uuid || order.id || "x"}-line-${l.id || l.cid || Math.random().toString(36).slice(2)}`;
            return {
                product_id: product.id,
                quantity: qty,
                line_note: note,
                source_pos_line_uuid: uuid,
            };
        });
    },

    async onClickSendToKitchen() {
        const order = this.pos.get_order();
        if (!order) {
            this.notification.add(_t("No hay un pedido activo."), { type: "warning" });
            return;
        }

        const linesData = this._buildKitchenLinesData(order);
        if (linesData.length === 0) {
            this.notification.add(
                _t("Ningun producto del pedido esta marcado como preparable en cocina."),
                { type: "warning" }
            );
            return;
        }

        const contextData = {
            pos_order_id: order.server_id || order.backendId || false,
            session_id: this.pos.session && this.pos.session.id,
            table_id: (order.table_id && (order.table_id.id || order.table_id)) || false,
            partner_id: order.get_partner && order.get_partner()
                ? order.get_partner().id
                : (order.partner_id && (order.partner_id.id || order.partner_id)) || false,
        };

        try {
            const result = await this.kitchen.sendToKitchen(linesData, contextData);
            if (result && result.warning) {
                this.notification.add(result.warning, { type: "warning" });
                return;
            }
            const msg = result.appended
                ? _t("Se agregaron %(n)s productos a la orden de cocina %(name)s.")
                : _t("Orden de cocina %(name)s creada con %(n)s productos.");
            this.notification.add(
                msg.replace("%(name)s", result.name).replace("%(n)s", result.line_count),
                { type: "success" }
            );
        } catch (error) {
            const message = (error && error.data && error.data.message)
                || (error && error.message)
                || _t("Error desconocido");
            this.notification.add(
                _t("No se pudo enviar a cocina: ") + message,
                { type: "danger" }
            );
        }
    },

    /**
     * Abre el popup con el estado de cocina (nuevas / en preparacion / listas).
     */
    onClickShowKitchenStatus() {
        this.dialog.add(KitchenReadyPopup, {});
    },

    /**
     * Numero de ordenes listas para mostrar en el badge del boton.
     */
    get kitchenReadyCount() {
        return (this.kitchenState.readyOrders && this.kitchenState.readyOrders.length) || 0;
    },
});

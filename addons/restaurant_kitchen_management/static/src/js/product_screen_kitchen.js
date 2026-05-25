/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Extiende los botones de control de la pantalla de producto del POS para
 * agregar "Enviar a cocina".
 *
 * Toma las lineas preparables del pedido actual, construye el payload con
 * UUIDs de linea (anti-duplicacion) y dispara el servicio kitchen.
 */
patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useService("kitchen");
        this.notification = useService("notification");
    },

    /**
     * Construye los datos de las lineas a partir del pedido POS actual.
     * Filtra por product.kitchen_preparable y genera UUID estable por linea.
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

    /**
     * Handler del boton "Enviar a cocina".
     */
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
});

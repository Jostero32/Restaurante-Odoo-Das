/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Popup que muestra las ordenes de cocina activas para esta sesion POS,
 * agrupadas por estado. Permite al mesero marcar como servida una orden
 * lista sin salir del POS.
 *
 * Se abre desde el boton "Cocina" en la barra de control.
 */
export class KitchenReadyPopup extends Component {
    static template = "restaurant_kitchen_management.KitchenReadyPopup";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
    };

    setup() {
        this.kitchen = useService("kitchen");
        this.notification = useService("notification");
        // El servicio kitchen expone un objeto reactivo; lo envolvemos en
        // useState para que el componente se re-renderice cuando cambie.
        this.state = useState(this.kitchen.state);
        // Plain object (no Set) para que la reactividad de OWL detecte cambios.
        this.busy = useState({ ids: {} });
    }

    isBusy(orderId) {
        return Boolean(this.busy.ids[orderId]);
    }

    get hasOrders() {
        return this.state.orders && this.state.orders.length > 0;
    }

    get readyOrders() {
        return this.state.readyOrders || [];
    }

    get preparingOrders() {
        return (this.state.orders || []).filter((o) => o.state === "preparing");
    }

    get newOrders() {
        return (this.state.orders || []).filter((o) => o.state === "new");
    }

    stateBadgeClass(stateValue) {
        return {
            new: "text-bg-info",
            preparing: "text-bg-warning",
            ready: "text-bg-success",
        }[stateValue] || "text-bg-secondary";
    }

    stateLabel(stateValue) {
        return {
            new: _t("Nueva"),
            preparing: _t("En preparacion"),
            ready: _t("Lista"),
        }[stateValue] || stateValue;
    }

    async onClickRefresh() {
        await this.kitchen.refreshNow();
    }

    async onClickMarkServed(order) {
        if (this.isBusy(order.id)) return;
        this.busy.ids[order.id] = true;
        try {
            await this.kitchen.markServed(order.id);
            this.notification.add(
                _t("Orden %s marcada como servida.").replace("%s", order.name),
                { type: "success" }
            );
        } catch (e) {
            const msg = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notification.add(
                _t("No se pudo marcar como servida: ") + msg,
                { type: "danger" }
            );
        } finally {
            delete this.busy.ids[order.id];
        }
    }

    onClickClose() {
        this.props.close();
    }
}

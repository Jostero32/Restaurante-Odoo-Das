/** @odoo-module **/

import { onMounted, onPatched, useExternalListener, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";

const RESERVATION_EVENT = "restaurant-reservation-snapshot";

function tableIdFromElement(element) {
    const className = [...element.classList].find((classItem) => classItem.startsWith("tableId-"));
    return className ? Number(className.split("-")[1]) : null;
}

function getArrangementText(tableInfo) {
    if (!tableInfo) {
        return "";
    }
    return tableInfo.arrangement_label || "";
}

patch(PosStore.prototype, {
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        await this._refreshReservationSnapshot();
        return result;
    },

    async syncAllOrders() {
        const result = await super.syncAllOrders(...arguments);
        const pendingOrders = Array.isArray(result) ? result : [];
        for (const order of pendingOrders) {
            if (!order?.finalized || !order?.table_id?.id) {
                continue;
            }
            await this.data.call(
                "restaurant.table.reservation",
                "finalize_pos_reservation_for_table",
                [order.table_id.id]
            );
        }
        await this._refreshReservationSnapshot();
        return result;
    },

    async _refreshReservationSnapshot() {
        try {
            const snapshot = await this.data.call(
                "restaurant.table.reservation",
                "get_pos_reservation_snapshot",
                [this.config.id]
            );
            this.reservationSnapshot = snapshot || {};
            window.dispatchEvent(new CustomEvent(RESERVATION_EVENT, { detail: this.reservationSnapshot }));
            return this.reservationSnapshot;
        } catch {
            this.reservationSnapshot = this.reservationSnapshot || {};
            return this.reservationSnapshot;
        }
    },
});

patch(ReceiptHeader.prototype, {
    get tableName() {
        const table = this.order.table_id || this.order.self_ordering_table_id;
        if (!table) {
            return "";
        }
        const snapshot = this.pos?.reservationSnapshot?.[table.id];
        const arrangementText = getArrangementText(snapshot);
        const baseLabel = this.order.customer_count
            ? _t("Table %(number)s, Guests: %(count)s", {
                  number: table.table_number,
                  count: this.order.customer_count,
              })
            : _t("Table %(number)s", { number: table.table_number });
        return arrangementText ? `${baseLabel} · ${arrangementText}` : baseLabel;
    },
});

patch(TicketScreen.prototype, {
    getTableTag(order) {
        const tableNumber = order.table_id?.table_number;
        if (!tableNumber) {
            return super.getTableTag(...arguments);
        }
        const snapshot = this.pos?.reservationSnapshot?.[order.table_id.id];
        const arrangementText = getArrangementText(snapshot);
        return arrangementText ? `${tableNumber} · ${arrangementText}` : tableNumber;
    },

    getTable(order) {
        const tableLabel = super.getTable(...arguments);
        if (!order?.table_id) {
            return tableLabel;
        }
        const snapshot = this.pos?.reservationSnapshot?.[order.table_id.id];
        const arrangementText = getArrangementText(snapshot);
        return arrangementText ? `${tableLabel} · ${arrangementText}` : tableLabel;
    },
});

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.reservationUiState = useState({ revision: 0 });

        const applySnapshot = () => {
            this.applyReservationSnapshotToFloor();
        };

        useExternalListener(window, RESERVATION_EVENT, (event) => {
            this.pos.reservationSnapshot = event.detail || {};
            this.reservationUiState.revision += 1;
            applySnapshot();
        });

        onMounted(async () => {
            if (!this.pos.reservationSnapshot) {
                await this.pos._refreshReservationSnapshot?.();
            }
            applySnapshot();
        });

        onPatched(() => {
            applySnapshot();
        });
    },

    applyReservationSnapshotToFloor() {
        const snapshot = this.pos?.reservationSnapshot || {};
        if (!this.map?.el) {
            return;
        }
        for (const element of this.map.el.querySelectorAll(".table")) {
            const tableId = tableIdFromElement(element);
            const tableInfo = tableId ? snapshot[tableId] : null;
            element.classList.toggle("o_reservation_reserved", Boolean(tableInfo));
            if (tableInfo) {
                element.dataset.reservationLabel = tableInfo.arrangement_label || _t("Reserved");
            } else {
                delete element.dataset.reservationLabel;
            }
        }
    },
});
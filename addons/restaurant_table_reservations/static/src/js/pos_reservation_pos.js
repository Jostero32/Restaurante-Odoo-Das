/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount, useExternalListener, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";

const RESERVATION_EVENT = "restaurant-reservation-snapshot";
const RESERVATION_BUS_CHANNEL = "restaurant_table_reservations.snapshot";
const RESERVATION_BUS_NOTIFICATION = "restaurant_table_reservations.snapshot_changed";

function tableIdFromElement(element) {
    if (!element) return null;
    if (element.dataset?.tableId) {
        const v = Number(element.dataset.tableId);
        if (!Number.isNaN(v)) return v;
    }
    if (element.dataset?.id) {
        const v = Number(element.dataset.id);
        if (!Number.isNaN(v)) return v;
    }
    if (element.id) {
        const m = element.id.match(/(?:tableId|table)-?(\d+)/i);
        if (m?.[1]) return Number(m[1]);
    }
    const cls = [...element.classList].find((c) => c.startsWith("tableId-"));
    if (cls) {
        const v = Number(cls.split("-")[1]);
        if (!Number.isNaN(v)) return v;
    }
    return null;
}

function getArrangementText(tableInfo) {
    return tableInfo?.arrangement_label || "";
}

patch(PosStore.prototype, {
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        await this._ensureReservationBusSubscription();
        await this._refreshReservationSnapshot();
        return result;
    },

    async syncAllOrders() {
        const result = await super.syncAllOrders(...arguments);
        const pendingOrders = Array.isArray(result) ? result : [];
        for (const order of pendingOrders) {
            if (!order?.finalized || !order?.table_id?.id) continue;
            try {
                await this.data.call(
                    "restaurant.table",
                    "mark_reservation_charged_for_table",
                    [order.table_id.id]
                );
            } catch {
                // ignore — order finalization must not block
            }
            try {
                await this.data.call(
                    "restaurant.table.reservation",
                    "finalize_pos_reservation_for_table",
                    [order.table_id.id]
                );
            } catch {
                // ignore
            }
        }
        await this._refreshReservationSnapshot();
        return result;
    },

    async _refreshReservationSnapshot() {
        try {
            const snapshot = await this.data.call(
                // proxy method added on restaurant.table.reservation delegates here
                "restaurant.table.reservation",
                "get_pos_reservation_snapshot",
                [this.config.id]
            );
            this.reservationSnapshot = snapshot || {};
            window.dispatchEvent(
                new CustomEvent(RESERVATION_EVENT, { detail: this.reservationSnapshot })
            );
            return this.reservationSnapshot;
        } catch {
            this.reservationSnapshot = this.reservationSnapshot || {};
            return this.reservationSnapshot;
        }
    },

    /**
     * Pull any draft pos.orders that were created server-side (e.g. from a web
     * reservation) into the POS local model store so the floor map shows them.
     *
     * In Odoo 17 PosData.searchRead automatically upserts results into the
     * reactive model registry, which triggers Owl re-renders.
     */
    async _loadNewServerOrders() {
        try {
            const sessionId =
                this.session?.id || this.config?.current_session_id?.id;
            if (!sessionId) return;
            await this.data.searchRead("pos.order", [
                ["session_id", "=", sessionId],
                ["state", "=", "draft"],
            ]);
        } catch {
            // silent — visual fallback via snapshot polling still works
        }
    },

    async _ensureReservationBusSubscription() {
        if (this._reservationBusSubscriptionReady) return;

        // Odoo 17: the bus is exposed as an env service, NOT as this.bus.
        // Fall back to this.bus for forward-compatibility just in case.
        const busService =
            this.env?.services?.bus_service || this.env?.services?.["bus_service"] || this.bus;
        if (!busService) return;

        // addChannel is async in some versions
        if (busService.addChannel) {
            await Promise.resolve(busService.addChannel(RESERVATION_BUS_CHANNEL)).catch(() => {});
        }

        busService.subscribe(RESERVATION_BUS_NOTIFICATION, async () => {
            await this._refreshReservationSnapshot();
            await this._loadNewServerOrders();
        });

        this._reservationBusSubscriptionReady = true;
    },
});

// ---------------------------------------------------------------------------
// ReceiptHeader: show arrangement label next to table number on the ticket
// ---------------------------------------------------------------------------
patch(ReceiptHeader.prototype, {
    get tableName() {
        const table = this.order.table_id || this.order.self_ordering_table_id;
        if (!table) return "";
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

// ---------------------------------------------------------------------------
// TicketScreen: show arrangement label in the order list
// ---------------------------------------------------------------------------
patch(TicketScreen.prototype, {
    getTableTag(order) {
        const tableNumber = order.table_id?.table_number;
        if (!tableNumber) return super.getTableTag(...arguments);
        const snapshot = this.pos?.reservationSnapshot?.[order.table_id.id];
        const arrangementText = getArrangementText(snapshot);
        return arrangementText ? `${tableNumber} · ${arrangementText}` : tableNumber;
    },

    getTable(order) {
        const tableLabel = super.getTable(...arguments);
        if (!order?.table_id) return tableLabel;
        const snapshot = this.pos?.reservationSnapshot?.[order.table_id.id];
        const arrangementText = getArrangementText(snapshot);
        return arrangementText ? `${tableLabel} · ${arrangementText}` : tableLabel;
    },
});

// ---------------------------------------------------------------------------
// FloorScreen: apply reservation CSS classes + polling fallback
// ---------------------------------------------------------------------------
patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.reservationUiState = useState({ revision: 0 });
        this.reservationSnapshotRefreshInterval = null;

        const applySnapshot = () => this.applyReservationSnapshotToFloor();

        const refreshSnapshot = async () => {
            if (this.pos?._refreshReservationSnapshot) {
                await this.pos._refreshReservationSnapshot();
            }
        };

        // React to snapshot updates dispatched by PosStore
        useExternalListener(window, RESERVATION_EVENT, (event) => {
            this.pos.reservationSnapshot = event.detail || {};
            this.reservationUiState.revision += 1;
            applySnapshot();
        });

        onMounted(async () => {
            await refreshSnapshot();
            applySnapshot();

            // Polling fallback: refresh every 10 s in case the bus misses an event.
            // 10 s keeps the UI snappy without hammering the server.
            if (!this.reservationSnapshotRefreshInterval) {
                this.reservationSnapshotRefreshInterval = setInterval(async () => {
                    await refreshSnapshot();
                    // Also pull any new server-side orders on each poll tick
                    if (this.pos?._loadNewServerOrders) {
                        await this.pos._loadNewServerOrders();
                    }
                }, 10_000);
            }
        });

        onWillUnmount(() => {
            if (this.reservationSnapshotRefreshInterval) {
                clearInterval(this.reservationSnapshotRefreshInterval);
                this.reservationSnapshotRefreshInterval = null;
            }
        });

        onPatched(() => applySnapshot());
    },

    /**
     * Stamp each table element on the DOM with the CSS class
     * `o_reservation_reserved` and a `data-reservation-label` attribute when a
     * confirmed/seated reservation exists for that table.
     *
     * This is a lightweight DOM pass that does NOT cause Owl re-renders; it runs
     * after every render via onPatched and on explicit snapshot updates.
     */
    applyReservationSnapshotToFloor() {
        const snapshot = this.pos?.reservationSnapshot || {};
        if (!this.map?.el) return;

        const selector =
            ".table, [data-table-id], [data-id], [id^='table-'], [class*='tableId-']";
        for (const el of this.map.el.querySelectorAll(selector)) {
            const tableId = tableIdFromElement(el);
            const info = tableId ? snapshot[tableId] : null;
            el.classList.toggle("o_reservation_reserved", Boolean(info));
            if (info) {
                el.dataset.reservationLabel = info.arrangement_label || _t("Reserved");
            } else {
                delete el.dataset.reservationLabel;
            }
        }
    },
});

/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount, useExternalListener, useState, reactive } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";

const RESERVATION_EVENT = "restaurant-reservation-snapshot";
const RESERVATION_BUS_CHANNEL = "restaurant_table_reservations.snapshot";
const RESERVATION_BUS_NOTIFICATION = "restaurant_table_reservations.snapshot_changed";

function tableIdFromElement(element) {
    if (!element) return null;
    // 1) data-table-id attribute (preferred)
    if (element.dataset && element.dataset.tableId) {
        const v = Number(element.dataset.tableId);
        if (!Number.isNaN(v)) return v;
    }
    // 2) generic data-id
    if (element.dataset && element.dataset.id) {
        const v = Number(element.dataset.id);
        if (!Number.isNaN(v)) return v;
    }
    // 3) id attribute like 'table-123' or 'tableId-123'
    if (element.id) {
        const m = element.id.match(/(?:tableId|table)-?(\d+)/i);
        if (m && m[1]) return Number(m[1]);
    }
    // 4) class like 'tableId-123'
    const className = [...element.classList].find((classItem) => classItem.startsWith("tableId-"));
    if (className) {
        const parts = className.split("-");
        const v = Number(parts[1]);
        if (!Number.isNaN(v)) return v;
    }
    return null;
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
        await this._ensureReservationBusSubscription();
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
            // Ensure any arrangement is charged (and attached to the POS order) before finalizing the reservation
            try {
                await this.data.call("restaurant.table", "mark_reservation_charged_for_table", [order.table_id.id]);
            } catch (err) {
                // ignore failures — finalization should still proceed
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

    async _ensureReservationBusSubscription() {
        if (this._reservationBusSubscriptionReady) {
            return;
        }
        if (!this.bus) {
            return;
        }
        await this.bus.addChannel(RESERVATION_BUS_CHANNEL);
        this.bus.subscribe(RESERVATION_BUS_NOTIFICATION, () => {
            this._refreshReservationSnapshot();
        });
        this._reservationBusSubscriptionReady = true;
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
        this.reservationSnapshotRefreshInterval = null;

        const applySnapshot = () => {
            this.applyReservationSnapshotToFloor();
        };

        const refreshSnapshot = async () => {
            if (this.pos?._refreshReservationSnapshot) {
                await this.pos._refreshReservationSnapshot();
            }
        };

        useExternalListener(window, RESERVATION_EVENT, (event) => {
            this.pos.reservationSnapshot = event.detail || {};
            this.reservationUiState.revision += 1;
            applySnapshot();
        });

        onMounted(async () => {
            await refreshSnapshot();
            applySnapshot();

            if (!this.reservationSnapshotRefreshInterval) {
                this.reservationSnapshotRefreshInterval = setInterval(refreshSnapshot, 5000);
            }

            // Attach click handler to floor map to add arrangement product to current order
            try {
                if (this.map?.el) {
                    this.map.el.addEventListener("click", async (ev) => {
                        const tableEl = ev.target.closest?.(".table") || ev.target.closest(".table");
                        if (!tableEl) return;
                        const tableId = tableIdFromElement(tableEl);
                        if (!tableId) return;
                        const snapshot = this.pos?.reservationSnapshot?.[tableId];
                        if (!snapshot) return;
                        if (!snapshot.arrangement_product_id || snapshot.arrangement_charged) return;

                        // Try to get product from POS models
                        const productModel = this.pos.models && this.pos.models["product.product"];
                        const product = productModel && (productModel.getBy ? productModel.getBy("id", snapshot.arrangement_product_id) : productModel.get(snapshot.arrangement_product_id));
                        try {
                            if (product) {
                                await reactive(this.pos).addLineToCurrentOrder({ product_id: product }, {});
                            } else {
                                // Fallback: try to load product by id into POS models
                                if (this.pos._loadMissingProducts) {
                                    try {
                                        await this.pos._loadMissingProducts([snapshot.arrangement_product_id]);
                                    } catch (e) {
                                        // ignore
                                    }
                                }
                                let product2 = productModel && (productModel.getBy ? productModel.getBy("id", snapshot.arrangement_product_id) : productModel.get(snapshot.arrangement_product_id));
                                if (product2) {
                                    await reactive(this.pos).addLineToCurrentOrder({ product_id: product2 }, {});
                                } else {
                                    // Last resort: create a minimal in-memory product record so POS can add it
                                    try {
                                        const prodData = {
                                            id: snapshot.arrangement_product_id || Math.floor(Math.random() * 1000000000),
                                            name: snapshot.arrangement_label || "Arreglo",
                                            display_name: snapshot.arrangement_label || "Arreglo",
                                            list_price: snapshot.arrangement_price || 0.0,
                                            taxes_id: [],
                                            type: "service",
                                        };
                                        if (productModel && productModel.create) {
                                            product2 = productModel.create(prodData);
                                        } else if (this.pos.models && this.pos.models["product.product"] && this.pos.models["product.product"].create) {
                                            product2 = this.pos.models["product.product"].create(prodData);
                                        }
                                        if (product2) {
                                            await reactive(this.pos).addLineToCurrentOrder({ product_id: product2 }, {});
                                        } else {
                                            console.warn("Unable to create in-memory arrangement product for POS", prodData);
                                            return;
                                        }
                                    } catch (err) {
                                        console.error("Fallback: failed to create temporary product:", err);
                                        return;
                                    }
                                }
                            }
                            // Mark reservation as charged on server
                            await this.pos.data.call("restaurant.table", "mark_reservation_charged_for_table", [tableId]);
                            this.pos.reservationSnapshot[tableId].arrangement_charged = true;
                            this.reservationUiState.revision += 1;
                        } catch (err) {
                            console.error("Failed to add arrangement line:", err);
                        }
                    });
                }
            } catch (err) {
                console.error("Error attaching table click handler:", err);
            }
        });

        onWillUnmount(() => {
            if (this.reservationSnapshotRefreshInterval) {
                clearInterval(this.reservationSnapshotRefreshInterval);
                this.reservationSnapshotRefreshInterval = null;
            }
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
        // Find table elements using multiple heuristics to support different floor map templates
        const selector = ".table, [data-table-id], [data-id], [id^=table-], [class*='tableId-']";
        for (const element of this.map.el.querySelectorAll(selector)) {
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
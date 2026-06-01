/** @odoo-module **/

const AVAILABILITY_URL = "/reservas/availability";

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function formatDateTimeLabel(value) {
    if (!value) {
        return "";
    }
    const date = new Date(value.replace(" ", "T"));
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat("es-EC", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(date);
}

function formatMoney(amount) {
    const numericAmount = Number(amount || 0);
    return numericAmount.toFixed(2);
}

function populateTimeOptionsFallback() {
    const timeSelect = document.getElementById("time");
    const dateInput = document.getElementById("date");
    if (!timeSelect || !dateInput) {
        return;
    }

    const preSelectedTime = timeSelect.value || timeSelect.getAttribute("data-selected");
    const selectedDate = dateInput.value;

    const now = new Date();
    const localToday = new Date(now);
    localToday.setMinutes(localToday.getMinutes() - localToday.getTimezoneOffset());
    const todayString = localToday.toISOString().split("T")[0];
    const isToday = selectedDate === todayString;

    timeSelect.innerHTML = '<option value="">Selecciona...</option>';

    for (let h = 8; h <= 22; h += 1) {
        for (let m = 0; m < 60; m += 15) {
            if (isToday && (h < now.getHours() || (h === now.getHours() && m <= now.getMinutes()))) {
                continue;
            }
            const timeValue = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
            const option = document.createElement("option");
            option.value = timeValue;
            option.textContent = timeValue;
            if (preSelectedTime === timeValue) {
                option.selected = true;
            }
            timeSelect.appendChild(option);
        }
    }
}

function initReservationPage() {
    const form = document.getElementById("reservation_form");
    const tableResults = document.getElementById("table_results");
    if (!form || !tableResults) {
        return;
    }

    populateTimeOptionsFallback();

    const fields = {
        date: document.getElementById("date"),
        time: document.getElementById("time"),
        zone: document.getElementById("zone"),
        partySize: document.getElementById("party_size"),
        tableId: document.getElementById("table_id"),
        summary: document.getElementById("reservation_summary"),
        feedback: document.getElementById("availability_feedback"),
        windowFeedback: document.getElementById("reservation_window_feedback"),
        submitBtn: document.getElementById("btn_submit_reservation"),
        preOrderPayload: document.getElementById("pre_order_payload"),
        preOrderTotalText: document.getElementById("pre_order_total_text"),
    };

    const state = {
        tables: [],
        selectedTableId: fields.tableId.value ? Number(fields.tableId.value) : null,
        preOrder: {},
        preOrderCurrencySymbol: "$",
    };
    if (fields.preOrderTotalText?.textContent) {
        const symbolMatch = fields.preOrderTotalText.textContent.trim().match(/^[^0-9.-]+/);
        if (symbolMatch) {
            state.preOrderCurrencySymbol = symbolMatch[0];
        }
    }

    function updateSummaryText() {
        if (!fields.summary) {
            return;
        }
        const selectedCount = Object.values(state.preOrder).reduce((acc, row) => acc + Number(row.qty || 0), 0);
        let summaryText = "Duracion de mesa: 60 minutos + 15 minutos de margen.";
        if (selectedCount > 0) {
            summaryText += ` Pre-orden: ${selectedCount} item(s).`;
        }
        fields.summary.textContent = summaryText;
    }

    function getPartySize() {
        return Math.max(1, Number(fields.partySize?.value || 0) || 1);
    }

    function updatePreOrderState() {
        const payload = [];
        let total = 0;
        let totalItems = 0;
        for (const row of Object.values(state.preOrder)) {
            if (!row.qty || row.qty <= 0) {
                continue;
            }
            payload.push({
                product_id: row.product_id,
                qty: row.qty,
                notes: row.notes || "",
            });
            total += Number(row.price || 0) * Number(row.qty || 0);
            totalItems += Number(row.qty || 0);
        }
        if (fields.preOrderPayload) {
            fields.preOrderPayload.value = JSON.stringify(payload);
        }
        if (fields.preOrderTotalText) {
            fields.preOrderTotalText.textContent = `${state.preOrderCurrencySymbol}${formatMoney(total)}`;
        }
        const totalBar = document.getElementById("pre_order_sticky_total");
        if (totalBar) {
            totalBar.style.display = totalItems > 0 ? "" : "none";
        }
        updateSummaryText();
    }

    function initializePreOrderCatalog() {
        const cards = document.querySelectorAll(".o_preorder_card");
        if (!cards.length) {
            return;
        }

        cards.forEach((card) => {
            const productId = Number(card.dataset.productId);
            const productName = card.dataset.productName || "";
            const productPrice = Number(card.dataset.productPrice || 0);
            const followsParty = card.dataset.productFollowsParty === "1";
            const qtyNode = card.querySelector("[data-role='qty']");
            const notesWrap = card.querySelector("[data-role='notes-wrap']");
            const notesInput = card.querySelector("[data-role='notes']");

            const increaseButton = card.querySelector("[data-action='increase']");
            const decreaseButton = card.querySelector("[data-action='decrease']");

            const writeRow = (qty) => {
                const safeQty = Math.max(0, Number(qty || 0));
                if (!safeQty) {
                    delete state.preOrder[productId];
                } else {
                    const existing = state.preOrder[productId] || {};
                    state.preOrder[productId] = {
                        product_id: productId,
                        name: productName,
                        price: productPrice,
                        qty: safeQty,
                        notes: existing.notes || (notesInput ? notesInput.value : ""),
                        followsParty,
                    };
                }
                qtyNode.textContent = String(safeQty);
                if (notesWrap) {
                    notesWrap.style.display = safeQty > 0 ? "" : "none";
                }
                updatePreOrderState();
            };

            const incrementBy = followsParty ? getPartySize() : 1;

            if (increaseButton) {
                increaseButton.addEventListener("click", () => {
                    const current = state.preOrder[productId]?.qty || 0;
                    if (followsParty && current === 0) {
                        writeRow(getPartySize());
                    } else {
                        writeRow(current + incrementBy);
                    }
                });
            }
            if (decreaseButton) {
                decreaseButton.addEventListener("click", () => {
                    const current = state.preOrder[productId]?.qty || 0;
                    writeRow(Math.max(0, current - incrementBy));
                });
            }
            if (notesInput) {
                notesInput.addEventListener("input", () => {
                    if (state.preOrder[productId]) {
                        state.preOrder[productId].notes = notesInput.value;
                        updatePreOrderState();
                    }
                });
            }
        });

        // Reajustar qty automatica de "por persona" cuando cambia el numero de personas.
        if (fields.partySize) {
            fields.partySize.addEventListener("change", () => {
                const partySize = getPartySize();
                document.querySelectorAll(".o_preorder_card").forEach((card) => {
                    if (card.dataset.productFollowsParty !== "1") {
                        return;
                    }
                    const productId = Number(card.dataset.productId);
                    const row = state.preOrder[productId];
                    if (!row) {
                        return;
                    }
                    row.qty = partySize;
                    const qtyNode = card.querySelector("[data-role='qty']");
                    if (qtyNode) {
                        qtyNode.textContent = String(partySize);
                    }
                });
                updatePreOrderState();
            });
        }

        updatePreOrderState();
    }

    function initializeArrangementCatalog() {
        const catalog = document.getElementById("arrangement_catalog");
        const hiddenInput = document.getElementById("arrangement_product_id");
        if (!catalog || !hiddenInput) {
            return;
        }
        const cards = catalog.querySelectorAll(".o_arrangement_card");

        const setSelected = (selectedId) => {
            cards.forEach((card) => {
                const cardId = card.dataset.productId || "0";
                const isSelected = cardId === String(selectedId);
                card.dataset.selected = isSelected ? "1" : "0";
                card.classList.toggle("is-selected", isSelected);
            });
            hiddenInput.value = String(selectedId);
        };

        setSelected(hiddenInput.value || "0");

        cards.forEach((card) => {
            card.addEventListener("click", () => {
                setSelected(card.dataset.productId || "0");
            });
        });
    }

    function renderTables() {
        if (!state.tables.length) {
            tableResults.innerHTML = '<div class="alert alert-warning mb-0">No hay mesas disponibles con esos filtros.</div>';
            fields.tableId.value = "";
            state.selectedTableId = null;
            return;
        }

        tableResults.innerHTML = state.tables
            .map((table) => {
                const selectedClass = state.selectedTableId === table.id ? "is-selected" : "";
                const tableName = `Mesa ${table.name || table.id}`;
                return `
                    <button type="button" class="o_table_card ${selectedClass}" data-table-id="${table.id}">
                        <span class="o_table_card_name">${escapeHtml(tableName)}</span>
                        <span class="o_table_card_meta">${escapeHtml(table.zone_label)} - ${table.capacity} personas</span>
                        <span class="o_table_card_notes">${escapeHtml(table.notes || "Mesa disponible")}</span>
                    </button>`;
            })
            .join("");

        tableResults.querySelectorAll("[data-table-id]").forEach((button) => {
            button.addEventListener("click", () => {
                state.selectedTableId = Number(button.dataset.tableId);
                fields.tableId.value = String(state.selectedTableId);
                renderTables();
            });
        });
    }

    async function updateAvailability() {
        const date = fields.date.value;
        const time = fields.time.value;
        const zone = fields.zone.value;
        const partySize = fields.partySize.value || 2;
        if (!date || !time) {
            fields.feedback.textContent = "Selecciona fecha y hora para ver mesas disponibles.";
            tableResults.innerHTML = "";
            return;
        }

        const url = `${AVAILABILITY_URL}?date=${encodeURIComponent(date)}&time=${encodeURIComponent(time)}&zone=${encodeURIComponent(zone)}&party_size=${encodeURIComponent(partySize)}`;
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        const payload = await response.json();

        state.tables = payload.available_tables || [];
        if (!state.tables.some((table) => table.id === state.selectedTableId)) {
            state.selectedTableId = null;
            fields.tableId.value = "";
        }

        if (payload.schedule_is_open === false && payload.schedule_message) {
            fields.feedback.textContent = payload.schedule_message;
        } else {
            fields.feedback.textContent = state.tables.length
                ? `${state.tables.length} mesa(s) disponible(s) para tu seleccion.`
                : "No hay mesas disponibles para esa fecha, hora o zona.";
        }

        fields.windowFeedback.textContent = payload.reservation_window_end
            ? `La mesa queda reservada hasta ${formatDateTimeLabel(payload.reservation_window_end)}.`
            : "";

        if (payload.available_time_options && fields.time) {
            const selectedTime = fields.time.value;
            fields.time.innerHTML = '<option value="">Selecciona...</option>';
            for (const timeValue of payload.available_time_options) {
                const option = document.createElement("option");
                option.value = timeValue;
                option.textContent = timeValue;
                if (timeValue === selectedTime || timeValue === fields.time.getAttribute("data-selected")) {
                    option.selected = true;
                }
                fields.time.appendChild(option);
            }
        }

        renderTables();
    }

    let timeoutId = null;
    function scheduleUpdate() {
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => {
            updateAvailability().catch(() => {
                fields.feedback.textContent = "No se pudo actualizar la disponibilidad.";
            });
        }, 150);
    }

    ["change", "input"].forEach((eventType) => {
        if (fields.date) {
            fields.date.addEventListener(eventType, () => {
                populateTimeOptionsFallback();
                scheduleUpdate();
            });
        }
    });

    [fields.time, fields.zone, fields.partySize].forEach((input) => {
        if (input) {
            input.addEventListener("change", scheduleUpdate);
            input.addEventListener("input", scheduleUpdate);
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!state.selectedTableId) {
            window.alert("Por favor, selecciona una mesa disponible antes de reservar.");
            return;
        }

        fields.submitBtn.disabled = true;
        fields.submitBtn.textContent = "Verificando...";

        const url = `${AVAILABILITY_URL}?date=${encodeURIComponent(fields.date.value)}&time=${encodeURIComponent(fields.time.value)}&zone=${encodeURIComponent(fields.zone.value)}&party_size=${encodeURIComponent(fields.partySize.value)}`;

        try {
            const response = await fetch(url, { headers: { Accept: "application/json" } });
            const payload = await response.json();
            const latestTables = payload.available_tables || [];

            const isStillAvailable = latestTables.some((table) => table.id === state.selectedTableId);
            if (!isStillAvailable) {
                window.alert("Esta mesa acaba de ser reservada. Selecciona otra mesa o cambia la hora.");
                state.tables = latestTables;
                state.selectedTableId = null;
                fields.tableId.value = "";
                renderTables();
                fields.submitBtn.disabled = false;
                fields.submitBtn.textContent = "Reservar ahora";
                return;
            }

            updatePreOrderState();
            form.submit();
        } catch {
            window.alert("Error de conexion al verificar la mesa. Intenta nuevamente.");
            fields.submitBtn.disabled = false;
            fields.submitBtn.textContent = "Reservar ahora";
        }
    });

    initializePreOrderCatalog();
    initializeArrangementCatalog();
    renderTables();
    updateAvailability().catch(() => {
        fields.feedback.textContent = "No se pudo cargar disponibilidad inicial.";
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReservationPage);
} else {
    initReservationPage();
}

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

function initReservationPage() {
    const form = document.getElementById("reservation_form");
    const tableResults = document.getElementById("table_results");
    if (!form || !tableResults) {
        return;
    }

    const fields = {
        date: document.getElementById("date"),
        time: document.getElementById("time"),
        zone: document.getElementById("zone"),
        partySize: document.getElementById("party_size"),
        tableId: document.getElementById("table_id"),
        summary: document.getElementById("reservation_summary"),
        feedback: document.getElementById("availability_feedback"),
        windowFeedback: document.getElementById("reservation_window_feedback"),
    };

    const state = {
        tables: [],
        selectedTableId: fields.tableId.value ? Number(fields.tableId.value) : null,
    };

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
                const tableName = table.name || `Mesa ${table.id}`;
                return `
                    <button type="button" class="o_table_card ${selectedClass}" data-table-id="${table.id}">
                        <span class="o_table_card_name">${escapeHtml(tableName)}</span>
                        <span class="o_table_card_meta">${escapeHtml(table.zone_label)} · Capacidad ${table.capacity}</span>
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

        fields.feedback.textContent = state.tables.length
            ? `${state.tables.length} mesa(s) disponible(s) para tu selección.`
            : "No hay mesas disponibles para esa fecha, hora o zona.";

        fields.windowFeedback.textContent = payload.reservation_window_end
            ? `La mesa queda reservada hasta ${formatDateTimeLabel(payload.reservation_window_end)}.`
            : "";

        if (fields.summary) {
            fields.summary.textContent = `Duración de mesa: ${payload.reservation_duration_minutes || 60} minutos + ${payload.reservation_buffer_minutes || 15} minutos de margen.`;
        }

        renderTables();
    }

    let timeoutId = null;
    function scheduleUpdate() {
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(updateAvailability, 150);
    }

    [fields.date, fields.time, fields.zone, fields.partySize].forEach((input) => {
        input.addEventListener("change", scheduleUpdate);
        input.addEventListener("input", scheduleUpdate);
    });

    renderTables();
    updateAvailability();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReservationPage);
} else {
    initReservationPage();
}
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

// Función: 15 mins
function populateTimeOptions() {
    const timeSelect = document.getElementById("time");
    if (!timeSelect) return;

    const preSelectedTime = timeSelect.getAttribute("data-selected");
    const selectedDate = document.getElementById("date")?.value;
    const today = new Date();
    today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    const todayString = today.toISOString().split("T")[0];

    timeSelect.innerHTML = '<option value="">Selecciona...</option>';

    const baseOptions = [];
    for (let h = 8; h <= 22; h++) {
        for (let m = 0; m < 60; m += 15) {
            baseOptions.push(`${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`);
        }
    }

    const allowedOptions = selectedDate === todayString
        ? baseOptions.filter((timeStr) => {
            const [hour, minute] = timeStr.split(":").map((value) => Number(value));
            const candidate = new Date(today);
            candidate.setHours(hour, minute, 0, 0);
            return candidate >= new Date();
        })
        : baseOptions;

    for (const timeStr of allowedOptions) {
        const option = document.createElement("option");
        option.value = timeStr;
        option.textContent = timeStr;
        if (preSelectedTime === timeStr) {
            option.selected = true;
        }
        timeSelect.appendChild(option);
    }
}

function initReservationPage() {
    const form = document.getElementById("reservation_form");
    const tableResults = document.getElementById("table_results");
    if (!form || !tableResults) {
        return;
    }

    populateTimeOptions();

    const fields = {
        date: document.getElementById("date"),
        time: document.getElementById("time"),
        zone: document.getElementById("zone"),
        partySize: document.getElementById("party_size"),
        tableId: document.getElementById("table_id"),
        phone: document.getElementById("customer_phone"),
        summary: document.getElementById("reservation_summary"),
        feedback: document.getElementById("availability_feedback"),
        windowFeedback: document.getElementById("reservation_window_feedback"),
        submitBtn: document.getElementById("btn_submit_reservation")
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
                const tableName = `Mesa ${table.name || table.id}`;
                return `
                    <button type="button" class="o_table_card ${selectedClass}" data-table-id="${table.id}">
                        <span class="o_table_card_name">${escapeHtml(tableName)}</span>
                        <span class="o_table_card_meta">${escapeHtml(table.zone_label)} · ${table.capacity} personas</span>
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
        const arrangementTypeEl = document.getElementById('arrangement_type');
        const arrangementType = arrangementTypeEl ? arrangementTypeEl.value : 'none';

        if (!date || !time) {
            fields.feedback.textContent = "Selecciona fecha y hora para ver mesas disponibles.";
            tableResults.innerHTML = "";
            return;
        }

        const url = `${AVAILABILITY_URL}?date=${encodeURIComponent(date)}&time=${encodeURIComponent(time)}&zone=${encodeURIComponent(zone)}&party_size=${encodeURIComponent(partySize)}&arrangement_type=${encodeURIComponent(arrangementType)}`;
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        const payload = await response.json();

        populateTimeOptions();
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

        if (fields.summary) {
            let summaryText = `Duración de mesa: ${payload.reservation_duration_minutes || 60} minutos + ${payload.reservation_buffer_minutes || 15} minutos de margen.`;
            if (arrangementType && arrangementType !== 'none') {
                const selectedLabel = arrangementTypeEl.options[arrangementTypeEl.selectedIndex].textContent;
                summaryText += `\nArreglo seleccionado: ${selectedLabel}`;
            }
            fields.summary.textContent = summaryText;
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

    // --- CONTROL DE RESERVAR ---
    form.addEventListener("submit", async function(event) {
        event.preventDefault(); 

        if (fields.phone.value.length !== 10) {
            alert('El número de teléfono debe tener exactamente 10 dígitos.');
            return;
        }
        if (!state.selectedTableId) {
            alert('Por favor, selecciona una mesa disponible antes de reservar.');
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
                alert("¡Lo sentimos! Esta mesa acaba de ser reservada por otra persona en este momento. Por favor, selecciona otra mesa o cambia la hora.");
                state.tables = latestTables;
                state.selectedTableId = null;
                fields.tableId.value = "";
                renderTables();
                
                fields.submitBtn.disabled = false;
                fields.submitBtn.textContent = "Reservar ahora";
                return;
            }

            form.submit();

        } catch (error) {
            alert("Error de conexión al verificar la mesa. Intente nuevamente.");
            fields.submitBtn.disabled = false;
            fields.submitBtn.textContent = "Reservar ahora";
        }
    });

    renderTables();
    updateAvailability();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReservationPage);
} else {
    initReservationPage();
}
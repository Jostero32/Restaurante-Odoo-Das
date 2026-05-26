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

// Función: Genera las horas de 15 en 15 mins y bloquea las horas pasadas del día actual
function populateTimeOptions() {
    const timeSelect = document.getElementById("time");
    const dateInput = document.getElementById("date");
    if (!timeSelect || !dateInput) return;

    const preSelectedTime = timeSelect.value || timeSelect.getAttribute("data-selected");
    const selectedDate = dateInput.value;

    const now = new Date();
    // Ajustar zona horaria local para comparar correctamente
    const localToday = new Date(now);
    localToday.setMinutes(localToday.getMinutes() - localToday.getTimezoneOffset());
    const todayString = localToday.toISOString().split("T")[0];

    const isToday = (selectedDate === todayString);
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();

    timeSelect.innerHTML = '<option value="">Selecciona...</option>';

    for (let h = 8; h <= 22; h++) {
        for (let m = 0; m < 60; m += 15) {
            
            // CONTROL: Si es hoy, saltarse las horas que ya pasaron
            if (isToday) {
                if (h < currentHour || (h === currentHour && m <= currentMinute)) {
                    continue; 
                }
            }

            const hourStr = h.toString().padStart(2, "0");
            const minStr = m.toString().padStart(2, "0");
            const timeStr = `${hourStr}:${minStr}`;

            const option = document.createElement("option");
            option.value = timeStr;
            option.textContent = timeStr;

            if (preSelectedTime === timeStr) {
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

        // Repopular siempre para mantener las horas correctas antes de cualquier override
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

    // --- SEPARACIÓN DE EVENTOS (NUEVO) ---
    
    // Si cambia la fecha, primero validamos las horas (para quitar las del pasado si es 'hoy') y luego actualizamos
    ["change", "input"].forEach(eventType => {
        if(fields.date) {
            fields.date.addEventListener(eventType, () => {
                populateTimeOptions(); 
                scheduleUpdate();      
            });
        }
    });

    // Si cambian los otros campos, solo buscamos mesas disponibles
    [fields.time, fields.zone, fields.partySize].forEach((input) => {
        if(input) {
            input.addEventListener("change", scheduleUpdate);
            input.addEventListener("input", scheduleUpdate);
        }
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
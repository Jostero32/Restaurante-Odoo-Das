/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

function debounce(fn, wait) {
    let t = null;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}

async function loadWindow(state) {
    const data = await rpc("/shop/delivery_schedule/window", {});
    state.daysByDate = {};
    data.days.forEach((d) => {
        state.daysByDate[d.date] = d;
    });
    state.isOpenNow = data.is_open_now;
    state.currentSelection = data.current_selection || { is_scheduled: false };
    return data;
}

function populateDays(daySelect, days) {
    daySelect.innerHTML = "";
    if (!days.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No hay slots disponibles";
        daySelect.appendChild(opt);
        daySelect.disabled = true;
        return;
    }
    daySelect.disabled = false;
    days.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.date;
        opt.textContent = d.label;
        daySelect.appendChild(opt);
    });
}

function populateSlots(slotSelect, slots) {
    slotSelect.innerHTML = "";
    if (!slots.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Sin horarios este dia";
        slotSelect.appendChild(opt);
        slotSelect.disabled = true;
        return;
    }
    slotSelect.disabled = false;
    slots.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.datetime;
        opt.textContent = s.label;
        slotSelect.appendChild(opt);
    });
}

function applyNowDisabled(nowRadio, laterRadio, hintEl, isOpenNow) {
    if (isOpenNow) {
        nowRadio.disabled = false;
        hintEl.textContent = "Coordinamos la salida en el menor tiempo posible.";
        return;
    }
    nowRadio.disabled = true;
    nowRadio.checked = false;
    laterRadio.checked = true;
    hintEl.textContent = "El restaurante esta cerrado en este momento. Programa una hora.";
}

async function sendSelection(state, isScheduled, scheduledFor, feedbackEl) {
    feedbackEl.textContent = "Guardando...";
    const payload = { is_scheduled: isScheduled };
    if (isScheduled) {
        payload.scheduled_for = scheduledFor;
    }
    const result = await rpc("/shop/delivery_schedule/set", payload);
    if (result.error) {
        feedbackEl.textContent = "No se pudo guardar el horario. Recarga la pagina.";
        feedbackEl.classList.add("text-danger");
        return false;
    }
    feedbackEl.classList.remove("text-danger");
    if (result.is_scheduled) {
        feedbackEl.textContent = `Entrega programada para ${result.scheduled_label}.`;
    } else {
        feedbackEl.textContent = "Entrega lo antes posible.";
    }
    state.currentSelection = result;
    return true;
}

async function init() {
    const block = document.getElementById("o_delivery_schedule_block");
    if (!block) return;
    const nowRadio = block.querySelector("#o_delivery_schedule_now");
    const laterRadio = block.querySelector("#o_delivery_schedule_later");
    const picker = block.querySelector("#o_delivery_schedule_picker");
    const daySelect = block.querySelector("#o_delivery_schedule_day");
    const slotSelect = block.querySelector("#o_delivery_schedule_slot");
    const hintEl = block.querySelector("#o_delivery_schedule_now_hint");
    const feedbackEl = block.querySelector("#o_delivery_schedule_feedback");

    const state = { daysByDate: {}, isOpenNow: false, currentSelection: null };

    let data;
    try {
        data = await loadWindow(state);
    } catch (err) {
        feedbackEl.textContent = "No se pudo cargar el horario de entregas.";
        feedbackEl.classList.add("text-danger");
        return;
    }

    populateDays(daySelect, data.days);
    if (data.days.length) {
        populateSlots(slotSelect, data.days[0].slots);
    }
    applyNowDisabled(nowRadio, laterRadio, hintEl, state.isOpenNow);

    if (state.currentSelection && state.currentSelection.is_scheduled) {
        laterRadio.checked = true;
        nowRadio.checked = false;
        const target = state.currentSelection.scheduled_for;
        const targetDate = target ? target.slice(0, 10) : null;
        if (targetDate && state.daysByDate[targetDate]) {
            daySelect.value = targetDate;
            populateSlots(slotSelect, state.daysByDate[targetDate].slots);
            slotSelect.value = target;
        }
        feedbackEl.textContent = state.currentSelection.scheduled_label
            ? `Entrega programada para ${state.currentSelection.scheduled_label}.`
            : "Entrega programada.";
    }

    function refreshPickerVisibility() {
        if (laterRadio.checked) {
            picker.classList.remove("d-none");
        } else {
            picker.classList.add("d-none");
        }
    }
    refreshPickerVisibility();

    const debouncedSubmit = debounce(async () => {
        if (laterRadio.checked) {
            const slotValue = slotSelect.value;
            if (!slotValue) {
                feedbackEl.textContent = "Selecciona un horario disponible.";
                feedbackEl.classList.add("text-danger");
                return;
            }
            await sendSelection(state, true, slotValue, feedbackEl);
        } else {
            await sendSelection(state, false, null, feedbackEl);
        }
    }, 250);

    nowRadio.addEventListener("change", () => {
        refreshPickerVisibility();
        debouncedSubmit();
    });
    laterRadio.addEventListener("change", () => {
        refreshPickerVisibility();
        debouncedSubmit();
    });
    daySelect.addEventListener("change", () => {
        const day = state.daysByDate[daySelect.value];
        if (day) {
            populateSlots(slotSelect, day.slots);
        }
        debouncedSubmit();
    });
    slotSelect.addEventListener("change", () => {
        debouncedSubmit();
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}

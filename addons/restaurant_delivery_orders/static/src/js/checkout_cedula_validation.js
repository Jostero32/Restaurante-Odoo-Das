/** @odoo-module **/

// ── Cédula (CI) ──────────────────────────────────────────────────────────────
function _validateCI(v) {
    const province = parseInt(v.substring(0, 2), 10);
    if (province < 1 || province > 24)
        return { valid: false, message: "Cédula inválida: código de provincia incorrecto (01–24)." };
    if (parseInt(v[2], 10) >= 6)
        return { valid: false, message: "Cédula inválida: tercer dígito debe ser 0–5." };
    const coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2];
    let sum = 0;
    for (let i = 0; i < 9; i++) {
        let val = parseInt(v[i], 10) * coefs[i];
        if (val >= 10) val -= 9;
        sum += val;
    }
    const verifier = (10 - (sum % 10)) % 10;
    if (verifier !== parseInt(v[9], 10))
        return { valid: false, message: "Cédula inválida: dígito verificador incorrecto." };
    return { valid: true };
}

// ── RUC persona natural (3er dígito 0–5) ─────────────────────────────────────
function _validateRUCNatural(v) {
    const ci = _validateCI(v.substring(0, 10));
    if (!ci.valid) return { valid: false, message: "RUC inválido: cédula base incorrecta." };
    if (v.substring(10) !== "001")
        return { valid: false, message: "RUC persona natural debe terminar en 001." };
    return { valid: true };
}

// ── RUC persona jurídica (3er dígito = 9) ────────────────────────────────────
function _validateRUCJuridica(v) {
    const coefs = [4, 3, 2, 7, 6, 5, 4, 3, 2];
    const sum = coefs.reduce((acc, c, i) => acc + parseInt(v[i], 10) * c, 0);
    const residuo = sum % 11;
    const verifier = residuo === 0 ? 0 : 11 - residuo;
    if (verifier === 10 || verifier !== parseInt(v[9], 10))
        return { valid: false, message: "RUC persona jurídica inválido: dígito verificador incorrecto." };
    if (v.substring(10) === "000")
        return { valid: false, message: "RUC persona jurídica inválido: establecimiento 000." };
    return { valid: true };
}

// ── RUC entidad pública (3er dígito = 6) ─────────────────────────────────────
function _validateRUCPublica(v) {
    const coefs = [3, 2, 7, 6, 5, 4, 3, 2];
    const sum = coefs.reduce((acc, c, i) => acc + parseInt(v[i], 10) * c, 0);
    const residuo = sum % 11;
    const verifier = residuo === 0 ? 0 : 11 - residuo;
    if (verifier === 10 || verifier !== parseInt(v[8], 10))
        return { valid: false, message: "RUC entidad pública inválido: dígito verificador incorrecto." };
    if (v.substring(10) === "000")
        return { valid: false, message: "RUC entidad pública inválido: establecimiento 000." };
    return { valid: true };
}

// ── Punto de entrada ──────────────────────────────────────────────────────────
// Vacío      → válido (campo opcional)
// Con letras → pasaporte / doc extranjero, acepta si >= 5 chars
// 10 dígitos → cédula (CI)
// 13 dígitos → RUC (natural / jurídica / pública)
// Otro       → inválido
function validateEcuadorianDocument(rawValue) {
    const v = (rawValue || "").trim().replace(/[-\s]/g, "");
    if (!v) return { valid: true };

    if (!/^\d+$/.test(v)) {
        return v.length >= 5
            ? { valid: true }
            : { valid: false, message: "Número de documento muy corto (mínimo 5 caracteres)." };
    }

    if (v.length === 10) return _validateCI(v);

    if (v.length === 13) {
        const third = parseInt(v[2], 10);
        if (third < 6)  return _validateRUCNatural(v);
        if (third === 9) return _validateRUCJuridica(v);
        if (third === 6) return _validateRUCPublica(v);
        return { valid: false, message: "RUC inválido." };
    }

    return { valid: false, message: "Documento numérico inválido: debe tener 10 dígitos (cédula) o 13 dígitos (RUC)." };
}

// ─────────────────────────────────────────────────────────────────────────────
// Integración con el formulario de dirección del checkout
// ─────────────────────────────────────────────────────────────────────────────

function initCedulaValidation() {
    console.log("[cedula] init, buscando input[name=vat] en:", window.location.pathname);
    const vatInput = document.querySelector('input[name="vat"]');
    if (!vatInput) {
        console.log("[cedula] input[name=vat] NO encontrado");
        return;
    }
    console.log("[cedula] input[name=vat] encontrado:", vatInput);

    let errorEl = null;

    function getOrCreateError() {
        if (!errorEl) {
            errorEl = document.getElementById("cedula_validation_error");
            if (!errorEl) {
                errorEl = document.createElement("div");
                errorEl.id = "cedula_validation_error";
                errorEl.className = "text-danger small mt-1";
                vatInput.insertAdjacentElement("afterend", errorEl);
            }
        }
        return errorEl;
    }

    function showError(msg) {
        const el = getOrCreateError();
        el.textContent = msg || "";
        el.style.display = msg ? "block" : "none";
        vatInput.classList.toggle("is-invalid", Boolean(msg));
        vatInput.classList.toggle("is-valid", !msg && vatInput.value.trim().length > 0);
    }

    function validate() {
        console.log("[cedula] validando valor:", vatInput.value);
        const result = validateEcuadorianDocument(vatInput.value);
        console.log("[cedula] resultado:", result);
        if (!result.valid) {
            const msg = result.message || "Documento inválido.";
            showError(msg);
            vatInput.setCustomValidity(msg);
            return false;
        }
        showError("");
        vatInput.setCustomValidity("");
        return true;
    }

    vatInput.addEventListener("blur", function () {
        console.log("[cedula] blur disparado");
        validate();
    });

    // Re-valida mientras corrige para dar feedback inmediato
    vatInput.addEventListener("input", function () {
        if (vatInput.classList.contains("is-invalid")) {
            validate();
        }
    });
}

// Guard: si el DOM ya estaba listo cuando este script cargó, ejecuta de inmediato
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCedulaValidation);
} else {
    initCedulaValidation();
}

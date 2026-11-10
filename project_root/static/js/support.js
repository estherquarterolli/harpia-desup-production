(function () {
    'use strict';
    var dock = document.getElementById('supportDock');
    if (!dock) return;
    var key = 'harpia.support.minimized';
    var minimize = dock.querySelector('[data-support-minimize]');
    var restore = dock.querySelector('[data-support-restore]');
    function setMinimized(value, focus) {
        dock.classList.toggle('is-minimized', value);
        try { localStorage.setItem(key, value ? '1' : '0'); } catch (error) { /* Storage opcional. */ }
        if (focus) (value ? restore : dock.querySelector('a')).focus();
    }
    try { setMinimized(localStorage.getItem(key) === '1', false); } catch (error) { /* Usa estado expandido. */ }
    minimize.addEventListener('click', function () { setMinimized(true, true); });
    restore.addEventListener('click', function () { setMinimized(false, true); });
    window.addEventListener('storage', function (event) {
        if (event.key === key) setMinimized(event.newValue === '1', false);
    });

    // Sem polling: overlays já ficam acima do suporte por z-index; escondê-lo
    // também evita que o teclado alcance controles por trás de um modal.
    function updateOverlay() {
        var overlay = document.querySelector('.sidebar-backdrop.active, [aria-modal="true"]:not(.hidden), dialog[open]');
        if (!overlay) {
            overlay = Array.from(document.querySelectorAll('[id^="modal"], [id$="Modal"]')).find(function (element) {
                return getComputedStyle(element).position === 'fixed' && element.getClientRects().length > 0;
            });
        }
        dock.hidden = Boolean(overlay);
    }
    var overlaySelector = '.sidebar-backdrop, [aria-modal="true"], dialog, [id^="modal"], [id$="Modal"]';
    new MutationObserver(function (records) {
        // Mudanças em linhas, filtros e autocompletes não precisam percorrer
        // todos os modais da página, especialmente nas listagens grandes.
        var changed = records.some(function (record) {
            if (record.type === 'attributes') return record.target.matches(overlaySelector);
            return Array.from(record.addedNodes).concat(Array.from(record.removedNodes)).some(function (node) {
                return node.nodeType === 1 && (node.matches(overlaySelector) || node.querySelector(overlaySelector));
            });
        });
        if (changed) updateOverlay();
    }).observe(document.body, {
        attributes: true, attributeFilter: ['class', 'style', 'open', 'aria-modal'], subtree: true, childList: true,
    });
    updateOverlay();
    var errors = document.querySelector('[data-support-errors]');
    if (errors) errors.focus();
    // O debouncer global restaura botões após 3 s; este formulário permanece
    // bloqueado durante a navegação para prevenir cliques enquanto SMTP espera.
    var form = document.querySelector('[data-support-form]');
    if (form) form.addEventListener('submit', function (event) {
        if (form.dataset.submitting) { event.preventDefault(); return; }
        form.dataset.submitting = 'true';
        form.setAttribute('aria-busy', 'true');
    });
    window.addEventListener('pageshow', function () {
        if (form) { delete form.dataset.submitting; form.removeAttribute('aria-busy'); }
    });
})();

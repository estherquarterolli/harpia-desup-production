(function () {
    'use strict';
    var dock = document.getElementById('supportDock');
    if (!dock) return;

    var link = dock.querySelector('.support-tab');
    var positionKey = 'harpia.support.position.v1';
    var position = null;
    var drag = null;
    var suppressClick = false;
    try {
        var saved = JSON.parse(localStorage.getItem(positionKey));
        if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y) &&
            saved.x >= 0 && saved.x <= 1 && saved.y >= 0 && saved.y <= 1) position = saved;
    } catch (error) { /* Armazenamento opcional; usa o canto inferior direito. */ }

    function bounds() {
        return {
            x: Math.max(0, window.innerWidth - (dock.offsetWidth || 40)),
            y: Math.max(0, window.innerHeight - (dock.offsetHeight || 112)),
        };
    }
    function moveDock(left, top) {
        var limits = bounds();
        left = Math.min(limits.x, Math.max(0, left));
        top = Math.min(limits.y, Math.max(0, top));
        dock.style.left = left + 'px';
        dock.style.top = top + 'px';
        dock.style.right = 'auto';
        dock.style.bottom = 'auto';
        dock.classList.add('is-positioned');
        // Frações mantêm a posição relativa ao trocar de página ou de tamanho de tela.
        position = { x: limits.x ? left / limits.x : 0, y: limits.y ? top / limits.y : 0 };
    }
    function restorePosition() {
        if (!position) return;
        var limits = bounds();
        moveDock(position.x * limits.x, position.y * limits.y);
    }
    function finishDrag(event) {
        if (!drag || event.pointerId !== drag.id) return;
        var finished = drag;
        drag = null;
        dock.classList.remove('is-dragging');
        if (link.hasPointerCapture && link.hasPointerCapture(finished.id)) link.releasePointerCapture(finished.id);
        if (!finished.moved) return;
        try { localStorage.setItem(positionKey, JSON.stringify(position)); } catch (error) { /* Mantém a posição nesta página. */ }
        if (event.type === 'pointerup') {
            suppressClick = true;
            // O click gerado pelo término do arraste não deve abrir o formulário.
            setTimeout(function () { suppressClick = false; }, 0);
        }
    }
    link.addEventListener('pointerdown', function (event) {
        if (event.pointerType !== 'mouse' || event.button !== 0 || drag ||
            event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        var rect = dock.getBoundingClientRect();
        drag = { id: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false };
        if (link.setPointerCapture) link.setPointerCapture(event.pointerId);
    });
    window.addEventListener('pointermove', function (event) {
        if (!drag || event.pointerId !== drag.id) return;
        var dx = event.clientX - drag.x;
        var dy = event.clientY - drag.y;
        if (!drag.moved && Math.hypot(dx, dy) < 6) return;
        drag.moved = true;
        dock.classList.add('is-dragging');
        event.preventDefault();
        moveDock(drag.left + dx, drag.top + dy);
    }, { passive: false });
    window.addEventListener('pointerup', finishDrag);
    window.addEventListener('pointercancel', finishDrag);
    link.addEventListener('lostpointercapture', finishDrag);
    link.addEventListener('click', function (event) {
        if (suppressClick && event.detail !== 0) {
            event.preventDefault();
            event.stopImmediatePropagation();
            suppressClick = false;
        }
    }, true);
    window.addEventListener('resize', restorePosition);
    restorePosition();

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
        restorePosition();
        if (form) { delete form.dataset.submitting; form.removeAttribute('aria-busy'); }
    });
})();

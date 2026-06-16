(function () {
    const TYPE_CONFIG = {
        alert: { title: 'Aviso', icon: 'i', confirmText: 'OK', role: 'dialog' },
        confirm: { title: 'Confirmar', icon: '?', confirmText: 'Confirmar', cancelText: 'Cancelar', role: 'alertdialog' },
        error: { title: 'Erro', icon: '!', confirmText: 'OK', role: 'alertdialog' },
        success: { title: 'Sucesso', icon: 'OK', confirmText: 'OK', role: 'dialog' },
        warning: { title: 'Atenção', icon: '!', confirmText: 'OK', role: 'alertdialog' }
    };

    let activeDialog = null;
    let previousFocus = null;
    let idCounter = 0;

    function ensureRoot() {
        let root = document.getElementById('system-dialog-root');
        if (root) return root;

        root = document.createElement('div');
        root.id = 'system-dialog-root';
        root.className = 'system-dialog-root';
        root.innerHTML = '<div class="system-dialog-backdrop" data-dialog-cancel></div>';
        root.querySelector('[data-dialog-cancel]').addEventListener('click', () => closeDialog(false));
        document.body.appendChild(root);
        return root;
    }

    function getFocusable(panel) {
        return Array.from(panel.querySelectorAll([
            'a[href]',
            'button:not([disabled])',
            'textarea:not([disabled])',
            'input:not([disabled])',
            'select:not([disabled])',
            '[tabindex]:not([tabindex="-1"])'
        ].join(','))).filter((el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }

    function closeDialog(result) {
        if (!activeDialog) return;
        const dialog = activeDialog;
        activeDialog = null;

        dialog.root.classList.remove('is-open');
        document.body.classList.remove('system-dialog-lock');
        document.removeEventListener('keydown', dialog.onKeydown, true);

        window.setTimeout(() => {
            if (dialog.panel && dialog.panel.parentElement) {
                dialog.panel.parentElement.removeChild(dialog.panel);
            }
            if (previousFocus && typeof previousFocus.focus === 'function') {
                previousFocus.focus({ preventScroll: true });
            }
            previousFocus = null;
            dialog.resolve(result);
        }, 180);
    }

    function onKeydown(event) {
        if (!activeDialog) return;

        if (event.key === 'Escape') {
            event.preventDefault();
            closeDialog(false);
            return;
        }

        if (event.key !== 'Tab') return;
        const focusable = getFocusable(activeDialog.panel);
        if (!focusable.length) {
            event.preventDefault();
            activeDialog.panel.focus();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function showDialog(type, title, message, options) {
        const config = TYPE_CONFIG[type] || TYPE_CONFIG.alert;
        const dialogTitle = title || config.title;
        const dialogMessage = message || '';
        const dialogOptions = options || {};
        const titleId = `system-dialog-title-${++idCounter}`;
        const messageId = `system-dialog-message-${idCounter}`;
        const root = ensureRoot();

        if (activeDialog) closeDialog(false);

        const panel = document.createElement('section');
        panel.className = `system-dialog-panel system-dialog-type-${type}`;
        panel.setAttribute('role', config.role);
        panel.setAttribute('aria-modal', 'true');
        panel.setAttribute('aria-labelledby', titleId);
        panel.setAttribute('aria-describedby', messageId);
        panel.setAttribute('tabindex', '-1');

        const confirmText = dialogOptions.confirmText || config.confirmText || 'OK';
        const cancelText = dialogOptions.cancelText || config.cancelText || 'Cancelar';
        const showCancel = type === 'confirm';

        panel.innerHTML = `
            <div class="system-dialog-header">
                <div class="system-dialog-icon" aria-hidden="true">${config.icon}</div>
                <h2 class="system-dialog-title" id="${titleId}"></h2>
                <button type="button" class="system-dialog-close" data-dialog-cancel aria-label="Fechar">&times;</button>
            </div>
            <div class="system-dialog-body" id="${messageId}"></div>
            <div class="system-dialog-actions">
                ${showCancel ? `<button type="button" class="system-dialog-btn system-dialog-btn-secondary" data-dialog-cancel>${cancelText}</button>` : ''}
                <button type="button" class="system-dialog-btn system-dialog-btn-primary" data-dialog-confirm>${confirmText}</button>
            </div>
        `;

        panel.querySelector(`#${titleId}`).textContent = dialogTitle;
        panel.querySelector(`#${messageId}`).textContent = dialogMessage;
        root.appendChild(panel);

        return new Promise((resolve) => {
            previousFocus = document.activeElement;

            activeDialog = {
                root,
                panel,
                resolve,
                onKeydown
            };

            panel.querySelectorAll('[data-dialog-cancel]').forEach((el) => {
                el.addEventListener('click', () => closeDialog(false));
            });
            panel.querySelector('[data-dialog-confirm]').addEventListener('click', () => closeDialog(true));

            document.addEventListener('keydown', onKeydown, true);
            document.body.classList.add('system-dialog-lock');

            requestAnimationFrame(() => {
                root.classList.add('is-open');
                const primary = panel.querySelector('[data-dialog-confirm]');
                const secondary = panel.querySelector('[data-dialog-cancel].system-dialog-btn');
                (showCancel ? secondary : primary)?.focus({ preventScroll: true });
            });
        });
    }

    window.showAlert = function (title, message) {
        return showDialog('alert', title, message);
    };

    window.showSuccess = function (title, message) {
        return showDialog('success', title, message);
    };

    window.showError = function (title, message) {
        return showDialog('error', title, message);
    };

    window.showWarning = function (title, message) {
        return showDialog('warning', title, message);
    };

    window.showConfirm = function (title, message) {
        return showDialog('confirm', title, message);
    };

    document.addEventListener('submit', async function (event) {
        const form = event.target;
        if (!form || !form.matches || !form.matches('form[data-confirm-message]')) return;
        if (form.dataset.confirmed === 'true') {
            delete form.dataset.confirmed;
            return;
        }

        event.preventDefault();
        const ok = await window.showConfirm(form.dataset.confirmTitle || 'Confirmar ação', form.dataset.confirmMessage || 'Deseja continuar?');
        if (!ok) return;
        form.dataset.confirmed = 'true';
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }, true);
})();

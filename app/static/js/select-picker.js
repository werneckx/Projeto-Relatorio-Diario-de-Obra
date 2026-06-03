(function () {
    'use strict';

    const SELECT_PICKER_SELECTOR = 'select:not([data-no-tom-select="true"])';

    function shouldSkip(select) {
        if (!select || select.tomselect || select.disabled) return true;
        if (select.closest('[data-no-tom-select="true"]')) return true;
        if (select.closest('.dataTables_wrapper')) return true;
        if (select.classList.contains('dataTable-selector')) return true;
        return false;
    }

    function getPlaceholder(select) {
        const firstOption = select.querySelector('option[value=""], option:not([value])');
        return select.getAttribute('placeholder')
            || select.dataset.placeholder
            || (firstOption ? firstOption.textContent.trim() : 'Selecione...');
    }

    function initSelect(select) {
        if (!window.TomSelect || shouldSkip(select)) return;

        const classList = select.classList;
        const isCompact = select.dataset.compactSelect === 'true'
            || classList.contains('h-9')
            || classList.contains('h-10')
            || select.name === 'ativo'
            || select.name === 'frente_ativo[]'
            || select.id === 'add-ativo'
            || select.dataset.field === 'ativo';

        const settings = {
            allowEmptyOption: true,
            closeAfterSelect: true,
            create: false,
            dropdownParent: 'body',
            hideSelected: false,
            openOnFocus: true,
            maxOptions: 5000,
            placeholder: getPlaceholder(select),
            plugins: select.multiple ? ['remove_button'] : [],
            render: {
                no_results: function () {
                    return '<div class="no-results">Nenhum resultado encontrado</div>';
                }
            },
            onInitialize: function () {
                this.wrapper.classList.add('ds-tom-select');
                if (isCompact) this.wrapper.classList.add('ds-tom-select-compact');
                if (select.classList.contains('text-center')) this.wrapper.classList.add('ds-tom-select-center');
                if (!select.multiple) this.wrapper.classList.add('ds-tom-select-searchable');
            },
            onItemAdd: function () {
                if (select.multiple) return;
                window.setTimeout(() => {
                    this.close();
                    this.blur();
                }, 0);
            }
        };

        new window.TomSelect(select, settings);
        select.dataset.tomSelectInitialized = 'true';
    }

    function initSelectPickers(context = document) {
        const root = context && context.querySelectorAll ? context : document;
        if (root.matches && root.matches(SELECT_PICKER_SELECTOR)) initSelect(root);
        root.querySelectorAll(SELECT_PICKER_SELECTOR).forEach(initSelect);
    }

    function destroySelectPicker(select) {
        if (select && select.tomselect) {
            select.tomselect.destroy();
            select.dataset.tomSelectInitialized = '';
        }
    }

    function refreshSelectPicker(select) {
        if (!select) return;
        destroySelectPicker(select);
        initSelect(select);
    }

    function observeDynamicContent() {
        if (!document.body || !window.MutationObserver) return;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType !== Node.ELEMENT_NODE) return;
                    initSelectPickers(node);
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    window.initSelectPickers = initSelectPickers;
    window.refreshSelectPicker = refreshSelectPicker;
    window.destroySelectPicker = destroySelectPicker;

    document.addEventListener('DOMContentLoaded', function () {
        initSelectPickers(document);
        observeDynamicContent();
    });

    document.addEventListener('shown.bs.modal', function (event) {
        initSelectPickers(event.target || document);
    });

    document.addEventListener('modal:opened', function (event) {
        initSelectPickers(event.detail && event.detail.context ? event.detail.context : document);
    });
})();

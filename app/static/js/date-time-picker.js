(function () {
    'use strict';

    const PICKER_SELECTORS = [
        '.js-date-picker',
        '.js-time-picker',
        '.js-datetime-picker'
    ].join(',');

    const nativeTypeMap = {
        date: 'js-date-picker',
        time: 'js-time-picker',
        'datetime-local': 'js-datetime-picker'
    };

    function normalizeNativeFields(context) {
        if (!context || !context.querySelectorAll) return;
        context.querySelectorAll('input[type="date"], input[type="time"], input[type="datetime-local"]').forEach((input) => {
            const nativeType = (input.getAttribute('type') || '').toLowerCase();
            const pickerClass = nativeTypeMap[nativeType];
            if (!pickerClass || input.closest('[data-no-flatpickr="true"]')) return;
            input.classList.add(pickerClass);
            input.dataset.originalPickerType = nativeType;
            input.setAttribute('type', 'text');
        });
    }

    function isDisabledOrHidden(input) {
        if (!input || input.disabled || input.type === 'hidden') return true;
        if (input.closest('[data-no-flatpickr="true"]')) return true;
        const className = String(input.className || '');
        if (/\b(pointer-events-none|opacity-0|w-0|h-0)\b/.test(className)) return true;
        return false;
    }

    function getLocale() {
        if (!window.flatpickr || !window.flatpickr.l10ns) return 'pt';
        return window.flatpickr.l10ns.pt || window.flatpickr.l10ns.default || 'pt';
    }

    function copyA11yFromLabel(input, instance) {
        if (!instance || !instance.altInput || input.getAttribute('aria-label')) return;
        const id = input.id;
        const safeId = id && window.CSS && CSS.escape ? CSS.escape(id) : String(id || '').replace(/"/g, '\\"');
        const explicitLabel = id ? document.querySelector(`label[for="${safeId}"]`) : null;
        const wrappedLabel = input.closest('label');
        const labelText = (explicitLabel || wrappedLabel)?.textContent?.trim();
        if (labelText) instance.altInput.setAttribute('aria-label', labelText);
    }

    function dispatchNativeEvents(input) {
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function buildOptions(input, mode) {
        const common = {
            locale: getLocale(),
            allowInput: true,
            appendTo: document.body,
            disableMobile: true,
            clickOpens: true,
            onReady: function (_selectedDates, _dateStr, instance) {
                if (instance.altInput) {
                    instance.altInput.classList.add('flatpickr-alt-input');
                    instance.altInput.classList.remove('js-date-picker', 'js-time-picker', 'js-datetime-picker');
                    instance.altInput.dataset.noFlatpickr = 'true';
                    instance.altInput.dataset.flatpickrAltFor = input.name || input.id || '';
                    if (input.placeholder && !instance.altInput.placeholder) {
                        instance.altInput.placeholder = input.placeholder;
                    }
                }
                copyA11yFromLabel(input, instance);
            },
            onChange: function () {
                dispatchNativeEvents(input);
            },
            onClose: function () {
                dispatchNativeEvents(input);
            }
        };

        if (mode === 'time') {
            return {
                ...common,
                enableTime: true,
                noCalendar: true,
                time_24hr: true,
                dateFormat: 'H:i',
                altInput: false,
                minuteIncrement: Number(input.dataset.minuteIncrement || 5)
            };
        }

        if (mode === 'datetime') {
            return {
                ...common,
                enableTime: true,
                time_24hr: true,
                dateFormat: 'Y-m-d H:i',
                altInput: true,
                altFormat: 'd/m/Y H:i',
                minuteIncrement: Number(input.dataset.minuteIncrement || 5)
            };
        }

        return {
            ...common,
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'd/m/Y'
        };
    }

    function initInput(input) {
        if (!window.flatpickr || isDisabledOrHidden(input) || input._flatpickr) return;
        if (input.matches('input[type="date"], input[type="time"], input[type="datetime-local"]')) {
            const nativeType = (input.getAttribute('type') || '').toLowerCase();
            input.classList.add(nativeTypeMap[nativeType] || 'js-date-picker');
            input.dataset.originalPickerType = nativeType;
            input.setAttribute('type', 'text');
        }

        const mode = input.classList.contains('js-time-picker')
            ? 'time'
            : input.classList.contains('js-datetime-picker')
                ? 'datetime'
                : 'date';

        const instance = window.flatpickr(input, buildOptions(input, mode));
        input.dataset.flatpickrInitialized = 'true';
        if (input.value) instance.setDate(input.value, false, mode === 'time' ? 'H:i' : undefined);
    }

    function initDateTimePickers(context = document) {
        const root = context && context.querySelectorAll ? context : document;
        normalizeNativeFields(root);
        root.querySelectorAll(PICKER_SELECTORS).forEach(initInput);
    }

    function observeDynamicContent() {
        if (!document.body || !window.MutationObserver) return;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType !== Node.ELEMENT_NODE) return;
                    if (node.matches && node.matches(PICKER_SELECTORS)) initInput(node);
                    initDateTimePickers(node);
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    window.initDateTimePickers = initDateTimePickers;
    window.openDateTimePickerFor = function (target) {
        const input = typeof target === 'string' ? document.getElementById(target) : target;
        if (input && input._flatpickr) input._flatpickr.open();
        else if (input && input.focus) input.focus({ preventScroll: true });
    };

    function openLegacyShowPickerTarget(targetId) {
        const input = document.getElementById(targetId);
        if (!input || !window.flatpickr) return false;
        if (!input._flatpickr) {
            const originalType = (input.getAttribute('type') || '').toLowerCase();
            input.setAttribute('type', 'text');
            input.classList.add(originalType === 'time' ? 'js-time-picker' : 'js-date-picker');
            window.flatpickr(input, {
                locale: getLocale(),
                allowInput: true,
                appendTo: document.body,
                disableMobile: true,
                dateFormat: originalType === 'time' ? 'H:i' : 'Y-m-d',
                enableTime: originalType === 'time',
                noCalendar: originalType === 'time',
                time_24hr: true,
                onChange: function () {
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }
        input._flatpickr.open();
        return true;
    }

    document.addEventListener('click', function (event) {
        const trigger = event.target && event.target.closest ? event.target.closest('[onclick*="showPicker"]') : null;
        if (!trigger) return;
        const inlineHandler = trigger.getAttribute('onclick') || '';
        const match = inlineHandler.match(/getElementById\(['"]([^'"]+)['"]\)\.showPicker\(\)/);
        if (!match || !openLegacyShowPickerTarget(match[1])) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);

    document.addEventListener('DOMContentLoaded', function () {
        initDateTimePickers(document);
        observeDynamicContent();
    });

    document.addEventListener('shown.bs.modal', function (event) {
        initDateTimePickers(event.target || document);
    });

    document.addEventListener('modal:opened', function (event) {
        initDateTimePickers(event.detail && event.detail.context ? event.detail.context : document);
    });
})();

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

    const TIME_PICKER_STYLE_ID = 'ds-global-time-picker-styles';
    const TIME_PICKER_DEFAULT_INCREMENT = 5;
    const TIME_PICKER_OPEN_CLASS = 'ds-timepicker-open';
    let timePickerUi = null;
    let activeTimePicker = null;

    const RANGE_START_HINTS = ['inicio', 'início', 'start', 'from', 'min', 'de'];
    const RANGE_END_HINTS = ['fim', 'final', 'end', 'to', 'max', 'ate', 'até', 'planejada', 'planejado'];

    function normalizeKey(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    }

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

    function ensureTimePickerStyles() {
        if (document.getElementById(TIME_PICKER_STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = TIME_PICKER_STYLE_ID;

        style.textContent = `

            @media (max-width: 576px) {
                .flatpickr-calendar {
                    position: fixed !important;
                    top: auto !important;
                    left: 50% !important;
                    bottom: 16px !important;
                    transform: translateX(-50%) !important;
                    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.15) !important;
                    z-index: 999999 !important;
                }
            }

            .ds-timepicker-root {
                position: fixed;
                inset: 0;
                z-index: 100000;
                display: none;
            }

            .ds-timepicker-root.is-open {
                display: block;
            }

            .ds-timepicker-backdrop {
                position: absolute;
                inset: 0;
                background: transparent;
            }

            .ds-timepicker-panel {
                position: fixed;
                min-width: 288px;
                max-width: calc(100vw - 24px);
                max-height: 85vh; /* NOVO: Limite de altura máximo baseado na tela */
                display: flex; /* NOVO */
                flex-direction: column; /* NOVO */
                border-radius: 20px;
                border: 1px solid rgba(148, 163, 184, 0.28);
                background: rgba(255, 255, 255, 0.98);
                box-shadow: 0 24px 54px rgba(15, 23, 42, 0.18), 0 8px 18px rgba(15, 23, 42, 0.08);
                overflow: hidden;
                backdrop-filter: blur(14px);
            }

            .ds-timepicker-columns {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                border-bottom: 1px solid rgba(226, 232, 240, 0.92);
                flex: 1; /* NOVO */
                min-height: 0; /* NOVO: Permite que os filhos rolem */
            }

            .ds-timepicker-panel[data-time-cycle="24"] .ds-timepicker-columns {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .ds-timepicker-column {
                display: flex;
                flex-direction: column;
                height: 250px; /* NOVO: Altura fixa para forçar a rolagem em vez de min-height */
                background: #fff;
            }

            .ds-timepicker-column + .ds-timepicker-column {
                border-left: 1px solid rgba(226, 232, 240, 0.92);
            }

            .ds-timepicker-arrow {
                height: 40px;
                border: 0;
                background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.92));
                color: #64748b;
                cursor: pointer;
                transition: background-color 0.2s ease, color 0.2s ease;
            }

            .ds-timepicker-arrow:hover,
            .ds-timepicker-arrow:focus-visible {
                background: #eff6ff;
                color: #2563eb;
                outline: none;
            }

            .ds-timepicker-list {
                flex: 1;
                overflow-y: auto;
                padding: 10px 8px;
                display: flex;
                flex-direction: column;
                gap: 4px;
                /* NOVO: Estilização moderna da barra de rolagem */
                scrollbar-width: thin;
                scrollbar-color: #cbd5e1 transparent;
            }

            .ds-timepicker-list::-webkit-scrollbar {
                display: none;
            }

            .ds-timepicker-option {
                border: 0;
                background: transparent;
                color: #0f172a;
                border-radius: 8px;
                padding: 10px 8px;
                min-height: 42px;
                font-size: 0.96rem;
                font-weight: 500;
                cursor: pointer;
                transition: background-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
            }

            .ds-timepicker-option:hover,
            .ds-timepicker-option:focus-visible {
                background: rgba(37, 99, 235, 0.08);
                color: #1d4ed8;
                outline: none;
            }

            .ds-timepicker-option.is-selected {
                background: #106ebe;
                color: #fff;
            }

            .ds-timepicker-actions {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                background: #fff;
            }

            .ds-timepicker-action {
                border: 0;
                background: #fff;
                min-height: 48px;
                font-size: 1rem;
                color: #334155;
                cursor: pointer;
                transition: background-color 0.2s ease, color 0.2s ease;
            }

            .ds-timepicker-action + .ds-timepicker-action {
                border-left: 1px solid rgba(226, 232, 240, 0.92);
            }

            .ds-timepicker-action:hover,
            .ds-timepicker-action:focus-visible {
                background: #f8fafc;
                color: #0f172a;
                outline: none;
            }

            .ds-timepicker-action[data-action="confirm"] {
                color: #0f172a;
            }

            .ds-timepicker-list::-webkit-scrollbar {
                width: 6px;
            }
            .ds-timepicker-list::-webkit-scrollbar-track {
                background: transparent;
            }
            .ds-timepicker-list::-webkit-scrollbar-thumb {
                background-color: #cbd5e1;
                border-radius: 10px;
            }

            input.${TIME_PICKER_OPEN_CLASS} {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12) !important;
            }
        `;
        document.head.appendChild(style);
    }

    function pad2(value) {
        return String(value).padStart(2, '0');
    }

    function normalizeMinuteIncrement(value) {
        const numeric = Number(value || TIME_PICKER_DEFAULT_INCREMENT);
        if (!Number.isFinite(numeric) || numeric <= 0) return TIME_PICKER_DEFAULT_INCREMENT;
        return Math.min(30, Math.max(1, Math.round(numeric)));
    }

    function parseTimeValue(value) {
        if (value instanceof Date && !Number.isNaN(value.getTime())) {
            return { hour24: value.getHours(), minute: value.getMinutes() };
        }
        const raw = String(value || '').trim();
        if (!raw) return null;
        const match = raw.match(/^(\d{1,2}):(\d{2})$/);
        if (!match) return null;
        const hour24 = Number(match[1]);
        const minute = Number(match[2]);
        if (hour24 < 0 || hour24 > 23 || minute < 0 || minute > 59) return null;
        return { hour24, minute };
    }

    function formatTimeValue(hour24, minute) {
        return `${pad2(hour24)}:${pad2(minute)}`;
    }

    function toSyntheticTimeDate(hour24, minute) {
        return new Date(1970, 0, 1, Number(hour24 || 0), Number(minute || 0), 0, 0);
    }

    function to12Hour(hour24) {
        const normalized = ((Number(hour24) % 24) + 24) % 24;
        const meridiem = normalized >= 12 ? 'PM' : 'AM';
        const hour12 = normalized % 12 || 12;
        return { hour12, meridiem };
    }

    function from12Hour(hour12, meridiem) {
        const safeHour = Number(hour12) || 12;
        if (meridiem === 'PM') return safeHour === 12 ? 12 : safeHour + 12;
        return safeHour === 12 ? 0 : safeHour;
    }

    function getTimeCycle(input) {
        const explicit = String(
            input?.dataset?.timeCycle
            || input?.dataset?.clockIdentifier
            || input?.dataset?.timeFormat
            || ''
        ).toLowerCase();
        if (explicit.includes('12') || explicit.includes('ampm')) return '12';
        return '24';
    }

    function getTimePickerMinuteOptions(minuteIncrement, selectedMinute) {
        const options = new Set();
        for (let minute = 0; minute < 60; minute += minuteIncrement) options.add(minute);
        if (Number.isFinite(selectedMinute) && selectedMinute >= 0 && selectedMinute < 60) options.add(selectedMinute);
        return Array.from(options).sort((a, b) => a - b);
    }

    function ensureTimePickerUi() {
        ensureTimePickerStyles();
        if (timePickerUi) return timePickerUi;

        const root = document.createElement('div');
        root.className = 'ds-timepicker-root';
        root.innerHTML = `
            <div class="ds-timepicker-backdrop"></div>
            <div class="ds-timepicker-panel" role="dialog" aria-modal="true" aria-label="Selecionar horário">
                <div class="ds-timepicker-columns">
                    <div class="ds-timepicker-column" data-part="hour">
                        <button type="button" class="ds-timepicker-arrow" data-part="hour" data-direction="-1" aria-label="Hora anterior"><i class="fas fa-chevron-up"></i></button>
                        <div class="ds-timepicker-list" data-list="hour" role="listbox" aria-label="Horas"></div>
                        <button type="button" class="ds-timepicker-arrow" data-part="hour" data-direction="1" aria-label="Próxima hora"><i class="fas fa-chevron-down"></i></button>
                    </div>
                    <div class="ds-timepicker-column" data-part="minute">
                        <button type="button" class="ds-timepicker-arrow" data-part="minute" data-direction="-1" aria-label="Minuto anterior"><i class="fas fa-chevron-up"></i></button>
                        <div class="ds-timepicker-list" data-list="minute" role="listbox" aria-label="Minutos"></div>
                        <button type="button" class="ds-timepicker-arrow" data-part="minute" data-direction="1" aria-label="Próximo minuto"><i class="fas fa-chevron-down"></i></button>
                    </div>
                    <div class="ds-timepicker-column" data-part="meridiem">
                        <button type="button" class="ds-timepicker-arrow" data-part="meridiem" data-direction="-1" aria-label="Alternar período"><i class="fas fa-chevron-up"></i></button>
                        <div class="ds-timepicker-list" data-list="meridiem" role="listbox" aria-label="Período"></div>
                        <button type="button" class="ds-timepicker-arrow" data-part="meridiem" data-direction="1" aria-label="Alternar período"><i class="fas fa-chevron-down"></i></button>
                    </div>
                </div>
                <div class="ds-timepicker-actions">
                    <button type="button" class="ds-timepicker-action" data-action="confirm" aria-label="Confirmar">
                        <i class="fas fa-check"></i> Confirmar
                    </button>
                    <button type="button" class="ds-timepicker-action" data-action="cancel" aria-label="Cancelar">
                        <i class="fas fa-times"></i> Cancelar
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(root);

        const panel = root.querySelector('.ds-timepicker-panel');
        const lists = {
            hour: root.querySelector('[data-list="hour"]'),
            minute: root.querySelector('[data-list="minute"]'),
            meridiem: root.querySelector('[data-list="meridiem"]')
        };

        root.querySelector('.ds-timepicker-backdrop').addEventListener('mousedown', () => closeActiveTimePicker(false));

        root.addEventListener('click', (event) => {
            const action = event.target.closest('[data-action]');
            if (action) {
                closeActiveTimePicker(action.dataset.action === 'confirm');
                return;
            }
            const arrow = event.target.closest('.ds-timepicker-arrow');
            if (arrow) {
                event.preventDefault();
                stepTimePickerPart(arrow.dataset.part, Number(arrow.dataset.direction || 0));
                return;
            }
            const option = event.target.closest('.ds-timepicker-option');
            if (!option) return;
            event.preventDefault();
            selectTimePickerPart(option.dataset.part, option.dataset.value);
        });

        timePickerUi = { root, panel, lists };
        return timePickerUi;
    }

    function setTimePickerValue(input, hour24, minute, triggerChange) {
        const nextValue = formatTimeValue(hour24, minute);
        input.value = nextValue;
        if (input._flatpickr) {
            input._flatpickr.selectedDates = [toSyntheticTimeDate(hour24, minute)];
            input._flatpickr.latestSelectedDateObj = input._flatpickr.selectedDates[0];
        }
        if (triggerChange) dispatchNativeEvents(input);
    }

    function syncManualTimeInput(input, dispatch = false) {
        if (!input) return;
        const parsed = parseTimeValue(input.value);
        if (!parsed) {
            if (!String(input.value || '').trim()) {
                if (input._flatpickr) {
                    input._flatpickr.selectedDates = [];
                    input._flatpickr.latestSelectedDateObj = null;
                }
            }
            return;
        }
        setTimePickerValue(input, parsed.hour24, parsed.minute, dispatch);
    }

    function buildTimePickerOptions(part, state) {
        if (part === 'meridiem') {
            return ['AM', 'PM'];
        }
        if (part === 'minute') {
            return getTimePickerMinuteOptions(state.minuteIncrement, state.minute);
        }
        if (state.timeCycle === '12') {
            return Array.from({ length: 12 }, (_, index) => index + 1);
        }
        return Array.from({ length: 24 }, (_, index) => index);
    }

    function getCurrentPartValue(part, state) {
        if (part === 'minute') return state.minute;
        if (part === 'meridiem') return to12Hour(state.hour24).meridiem;
        return state.timeCycle === '12' ? to12Hour(state.hour24).hour12 : state.hour24;
    }

    function formatTimePickerLabel(part, value, state) {
        if (part === 'meridiem') return String(value);
        if (part === 'hour' && state.timeCycle === '12') return String(value);
        return pad2(value);
    }

    function scrollSelectedTimeOption(part) {
        const ui = ensureTimePickerUi();
        const list = ui.lists[part];
        if (!list) return;
        const selected = list.querySelector('.ds-timepicker-option.is-selected');
        if (selected) selected.scrollIntoView({ block: 'center', inline: 'nearest' });
    }

    function renderTimePicker() {
        const state = activeTimePicker;
        const ui = ensureTimePickerUi();
        if (!state) return;

        ui.panel.dataset.timeCycle = state.timeCycle;
        const meridiemColumn = ui.panel.querySelector('[data-part="meridiem"]');
        if (meridiemColumn) meridiemColumn.style.display = state.timeCycle === '12' ? '' : 'none';

        ['hour', 'minute', 'meridiem'].forEach((part) => {
            const list = ui.lists[part];
            if (!list) return;
            if (part === 'meridiem' && state.timeCycle !== '12') {
                list.innerHTML = '';
                return;
            }
            const selectedValue = getCurrentPartValue(part, state);
            list.innerHTML = buildTimePickerOptions(part, state).map((value) => {
                const isSelected = String(value) === String(selectedValue);
                return `<button type="button" class="ds-timepicker-option${isSelected ? ' is-selected' : ''}" data-part="${part}" data-value="${value}" role="option" aria-selected="${isSelected ? 'true' : 'false'}">${formatTimePickerLabel(part, value, state)}</button>`;
            }).join('');
        });

        requestAnimationFrame(() => {
            scrollSelectedTimeOption('hour');
            scrollSelectedTimeOption('minute');
            if (state.timeCycle === '12') scrollSelectedTimeOption('meridiem');
        });
    }

    function positionTimePicker(input) {
        const ui = ensureTimePickerUi();
        const rect = input.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        ui.panel.style.visibility = 'hidden';
        ui.panel.style.left = '12px';
        ui.panel.style.top = '12px';
        ui.panel.style.minWidth = `${Math.max(rect.width, 288)}px`;

        requestAnimationFrame(() => {
            const panelRect = ui.panel.getBoundingClientRect();
            let left = rect.left;
            let top = rect.bottom + 8;
            if (left + panelRect.width > viewportWidth - 12) left = viewportWidth - panelRect.width - 12;
            if (left < 12) left = 12;
            if (top + panelRect.height > viewportHeight - 12) top = rect.top - panelRect.height - 8;
            if (top < 12) top = 12;
            ui.panel.style.left = `${left}px`;
            ui.panel.style.top = `${top}px`;
            ui.panel.style.visibility = 'visible';
        });
    }

    function selectTimePickerPart(part, rawValue) {
        if (!activeTimePicker) return;
        const state = activeTimePicker;
        if (part === 'minute') {
            state.minute = Number(rawValue) || 0;
        } else if (part === 'meridiem') {
            const current12 = to12Hour(state.hour24).hour12;
            state.hour24 = from12Hour(current12, String(rawValue));
        } else if (part === 'hour') {
            const numeric = Number(rawValue);
            if (state.timeCycle === '12') {
                const meridiem = to12Hour(state.hour24).meridiem;
                state.hour24 = from12Hour(numeric, meridiem);
            } else {
                state.hour24 = numeric;
            }
        }
        renderTimePicker();
        if (state.input) {
            setTimePickerValue(state.input, state.hour24, state.minute, false);
        }
    }

    function stepTimePickerPart(part, direction) {
        if (!activeTimePicker || !direction) return;
        const state = activeTimePicker;
        const options = buildTimePickerOptions(part, state);
        const currentValue = getCurrentPartValue(part, state);
        const currentIndex = Math.max(0, options.findIndex((value) => String(value) === String(currentValue)));
        const nextIndex = (currentIndex + direction + options.length) % options.length;
        selectTimePickerPart(part, options[nextIndex]);
    }

    function closeActiveTimePicker(confirmSelection) {
        if (!activeTimePicker) return;
        const ui = ensureTimePickerUi();
        const { input, originalValue } = activeTimePicker;
        if (input._flatpickr) input._flatpickr.isOpen = false;
        if (confirmSelection) {
            setTimePickerValue(input, activeTimePicker.hour24, activeTimePicker.minute, true);
        } else {
            input.value = originalValue || '';
            syncManualTimeInput(input, false);
        }
        input.classList.remove(TIME_PICKER_OPEN_CLASS);
        ui.root.classList.remove('is-open');
        ui.root.setAttribute('aria-hidden', 'true');
        activeTimePicker = null;
    }

    function handleTimePickerKeydown(event) {
        if (!activeTimePicker) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            closeActiveTimePicker(false);
        } else if (event.key === 'Enter') {
            event.preventDefault();
            closeActiveTimePicker(true);
        }
    }

    function openTimePicker(input) {
        if (!input || input.disabled || input.readOnly) return;
        ensureTimePickerStyles();
        const ui = ensureTimePickerUi();
        if (activeTimePicker && activeTimePicker.input === input) {
            positionTimePicker(input);
            return;
        }
        if (activeTimePicker) closeActiveTimePicker(false);

        const parsed = parseTimeValue(input.value) || { hour24: 0, minute: 0 };
        activeTimePicker = {
            input,
            originalValue: input.value || '',
            hour24: parsed.hour24,
            minute: parsed.minute,
            minuteIncrement: normalizeMinuteIncrement(input.dataset.minuteIncrement),
            timeCycle: getTimeCycle(input)
        };

        if (input._flatpickr) input._flatpickr.isOpen = true;
        input.classList.add(TIME_PICKER_OPEN_CLASS);
        ui.root.classList.add('is-open');
        ui.root.setAttribute('aria-hidden', 'false');
        renderTimePicker();
        positionTimePicker(input);
    }

    function createTimePickerInstance(input) {
        if (!input || input._flatpickr) return input._flatpickr;
        ensureTimePickerStyles();
        const instance = {
            input,
            config: {
                enableTime: true,
                noCalendar: true,
                allowInput: true,
                clickOpens: true,
                ignoredFocusElements: [],
                time_24hr: getTimeCycle(input) !== '12',
                minuteIncrement: normalizeMinuteIncrement(input.dataset.minuteIncrement)
            },
            selectedDates: [],
            latestSelectedDateObj: null,
            isOpen: false,
            open() {
                this.isOpen = true;
                openTimePicker(input);
            },
            close() {
                this.isOpen = false;
                if (activeTimePicker && activeTimePicker.input === input) closeActiveTimePicker(false);
            },
            setDate(value, triggerChange) {
                const parsed = parseTimeValue(value);
                if (!parsed) {
                    input.value = value ? String(value) : '';
                    this.selectedDates = [];
                    this.latestSelectedDateObj = null;
                    if (triggerChange) dispatchNativeEvents(input);
                    return;
                }
                setTimePickerValue(input, parsed.hour24, parsed.minute, Boolean(triggerChange));
            },
            clear() {
                input.value = '';
                this.selectedDates = [];
                this.latestSelectedDateObj = null;
            },
            redraw() { },
            set() { },
            jumpToDate() { }
        };
        input._flatpickr = instance;
        input.dataset.flatpickrInitialized = 'true';
        syncManualTimeInput(input, false);
        if (!input.dataset.timePickerBound) {
            input.dataset.timePickerBound = 'true';
            input.addEventListener('click', () => openTimePicker(input));
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
                    event.preventDefault();
                    openTimePicker(input);
                }
            });
            input.addEventListener('change', () => syncManualTimeInput(input, false));
        }
        return instance;
    }

    function parsePickerDate(input) {
        if (!input) return null;
        if (input._flatpickr && input._flatpickr.selectedDates && input._flatpickr.selectedDates[0]) {
            return input._flatpickr.selectedDates[0];
        }
        const value = String(input.value || '').trim();
        if (!value) return null;
        const iso = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (iso) return new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
        const br = value.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        if (br) return new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1]));
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    function sameDay(a, b) {
        return a && b
            && a.getFullYear() === b.getFullYear()
            && a.getMonth() === b.getMonth()
            && a.getDate() === b.getDate();
    }

    function isBetween(day, start, end) {
        if (!day || !start || !end) return false;
        const current = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
        const from = new Date(start.getFullYear(), start.getMonth(), start.getDate()).getTime();
        const to = new Date(end.getFullYear(), end.getMonth(), end.getDate()).getTime();
        return current > Math.min(from, to) && current < Math.max(from, to);
    }

    function isWithinInclusiveRange(day, start, end) {
        if (!day || !start || !end) return false;
        const current = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
        const from = new Date(start.getFullYear(), start.getMonth(), start.getDate()).getTime();
        const to = new Date(end.getFullYear(), end.getMonth(), end.getDate()).getTime();
        return current >= Math.min(from, to) && current <= Math.max(from, to);
    }

    function isBeforeDate(day, minDate) {
        if (!day || !minDate) return false;
        return new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime()
            < new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate()).getTime();
    }

    function getLinkedRanges(input) {
        const links = input && input._dateRangeLinks ? input._dateRangeLinks : [];
        return links
            .map((link) => ({
                start: parsePickerDate(link.start),
                end: parsePickerDate(link.end)
            }))
            .filter((range) => range.start && range.end);
    }

    function getSelfOrLinkedDate(input) {
        const ownDate = parsePickerDate(input);
        if (ownDate) return ownDate;
        const links = input && input._dateRangeLinks ? input._dateRangeLinks : [];
        for (const link of links) {
            const counterpart = link.start === input ? parsePickerDate(link.end) : parsePickerDate(link.start);
            if (counterpart) return counterpart;
        }
        return null;
    }

    function decorateRangeDay(input, dayElem) {
        if (!input || !dayElem || !(dayElem.dateObj instanceof Date)) return;
        getLinkedRanges(input).forEach((range) => {
            if (isWithinInclusiveRange(dayElem.dateObj, range.start, range.end)) dayElem.classList.add('ds-range-selected');
            if (sameDay(dayElem.dateObj, range.start)) dayElem.classList.add('ds-range-start');
            if (sameDay(dayElem.dateObj, range.end)) dayElem.classList.add('ds-range-end');
            if (isBetween(dayElem.dateObj, range.start, range.end)) dayElem.classList.add('ds-range-middle');
        });
    }

    function buildMinDateDisabler(minDate) {
        const disabler = function (date) {
            return isBeforeDate(date, minDate);
        };
        disabler._dsMinDateDisabler = true;
        return disabler;
    }

    function mergeDisableRules(existingRules, minDate) {
        const rules = Array.isArray(existingRules) ? existingRules : (existingRules ? [existingRules] : []);
        const withoutOldMinDateRule = rules.filter((rule) => !(rule && rule._dsMinDateDisabler));
        return minDate ? [...withoutOldMinDateRule, buildMinDateDisabler(minDate)] : withoutOldMinDateRule;
    }

    function applyEndDateConstraint(endInput, startDate) {
        if (!endInput || !endInput._flatpickr) return;
        const picker = endInput._flatpickr;
        picker.set('minDate', startDate || null);
        picker.set('disable', mergeDisableRules(picker.config.disable, startDate));

        const endDate = parsePickerDate(endInput);
        if (startDate && endDate && isBeforeDate(endDate, startDate)) {
            picker.clear();
            dispatchNativeEvents(endInput);
        }
        picker.redraw();
    }

    function refreshLinkedCalendars(input) {
        const links = input && input._dateRangeLinks ? input._dateRangeLinks : [];
        links.forEach((link) => {
            [link.start, link.end].forEach((field) => {
                if (field && field._flatpickr) field._flatpickr.redraw();
            });
        });
    }

    function syncLinkedRange(input) {
        const links = input && input._dateRangeLinks ? input._dateRangeLinks : [];
        const startsToConstrain = new Set();
        links.forEach((link) => {
            const startDate = parsePickerDate(link.start);
            const endDate = parsePickerDate(link.end);
            applyEndDateConstraint(link.end, startDate);
            if (link.start && link.start._flatpickr) startsToConstrain.add(link.start);
            if (startDate && link.end && link.end._flatpickr && !link.end._flatpickr.isOpen) {
                link.end._flatpickr.jumpToDate(startDate, false);
            }
            if (endDate && link.start && link.start._flatpickr && !link.start._flatpickr.isOpen) {
                link.start._flatpickr.jumpToDate(endDate, false);
            }
        });
        startsToConstrain.forEach((start) => {
            const endDates = (start._dateRangeLinks || [])
                .map((link) => parsePickerDate(link.end))
                .filter(Boolean)
                .sort((a, b) => a - b);
            start._flatpickr.set('maxDate', endDates[0] || null);
        });
        refreshLinkedCalendars(input);
    }

    function buildOptions(input, mode) {
        const common = {
            locale: getLocale(),
            allowInput: true,
            appendTo: document.body,
            disableMobile: true,
            clickOpens: true,
            monthSelectorType: 'static',
            static: false,
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
                if (instance.calendarContainer) {
                    instance.calendarContainer.classList.add('ds-flatpickr-calendar');
                    instance.calendarContainer.setAttribute('data-picker-mode', mode);
                }
                syncLinkedRange(input);
            },
            onChange: function () {
                syncLinkedRange(input);
                dispatchNativeEvents(input);
            },
            onValueUpdate: function () {
                syncLinkedRange(input);
            },
            onClose: function () {
                syncLinkedRange(input);
                dispatchNativeEvents(input);
            },
            onOpen: function (_selectedDates, _dateStr, instance) {
                syncLinkedRange(input);
                const reference = getSelfOrLinkedDate(input);
                if (reference) instance.jumpToDate(reference, false);
            },
            onMonthChange: function () {
                refreshLinkedCalendars(input);
            },
            onYearChange: function () {
                refreshLinkedCalendars(input);
            },
            onDayCreate: function (_selectedDates, _dateStr, _instance, dayElem) {
                decorateRangeDay(input, dayElem);
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

        if (mode === 'time') {
            createTimePickerInstance(input);
            return;
        }

        const instance = window.flatpickr(input, buildOptions(input, mode));
        input.dataset.flatpickrInitialized = 'true';
        if (input.value) instance.setDate(input.value, false, mode === 'time' ? 'H:i' : undefined);
    }

    function getPickerInputs(root) {
        return Array.from(root.querySelectorAll('.js-date-picker, .js-datetime-picker'))
            .filter((input) => input._flatpickr && !isDisabledOrHidden(input));
    }

    function fieldIdentity(input) {
        return normalizeKey([
            input.id,
            input.name,
            input.className,
            input.dataset.dateRole,
            input.dataset.rangeRole,
            input.placeholder
        ].join(' '));
    }

    function isRangeStart(input) {
        const identity = fieldIdentity(input);
        if (input.dataset.rangeStart !== undefined || input.dataset.dateRangeStart !== undefined) return true;
        if (input.dataset.rangeEnd !== undefined || input.dataset.dateRangeEnd !== undefined) return false;
        return RANGE_START_HINTS.some((hint) => identity.includes(hint))
            && !RANGE_END_HINTS.some((hint) => identity.includes(hint) && !identity.includes('inicio'));
    }

    function isRangeEnd(input) {
        const identity = fieldIdentity(input);
        if (input.dataset.rangeEnd !== undefined || input.dataset.dateRangeEnd !== undefined) return true;
        return RANGE_END_HINTS.some((hint) => identity.includes(hint));
    }

    function scoreRangePair(start, end) {
        if (!start || !end || start === end || !isRangeEnd(end)) return -1;
        const startScope = start.closest('tr, [data-date-range], .surface-card, .rounded-xl, form') || document.body;
        const endScope = end.closest('tr, [data-date-range], .surface-card, .rounded-xl, form') || document.body;
        let score = 0;
        if (startScope === endScope) score += 12;
        if (start.closest('tr') && start.closest('tr') === end.closest('tr')) score += 40;
        if (start.closest('[data-colaborador-key]') && start.closest('[data-colaborador-key]') === end.closest('[data-colaborador-key]')) score += 45;
        if ((start.name || '').replace(/inicio|start|min|from|de/gi, '') === (end.name || '').replace(/fim|final|end|max|to|ate|planejada|planejado/gi, '')) score += 20;
        if ((start.id || '').replace(/inicio|start|min|from|de/gi, '') === (end.id || '').replace(/fim|final|end|max|to|ate|planejada|planejado/gi, '')) score += 20;
        if (normalizeKey(end.id || end.name).includes('planejada')) score += 1;
        return score;
    }

    function attachRangeLink(start, end) {
        if (!start || !end || start === end) return;
        const startLinks = start._dateRangeLinks || [];
        if (startLinks.some((link) => link.start === start && link.end === end)) return;
        const link = { start, end };
        start._dateRangeLinks = [...startLinks, link];
        end._dateRangeLinks = [...(end._dateRangeLinks || []), link];
        syncLinkedRange(start);
    }

    function linkDateRanges(context = document) {
        const root = context && context.querySelectorAll ? context : document;
        const inputs = getPickerInputs(root);
        const starts = inputs.filter(isRangeStart);
        const ends = inputs.filter(isRangeEnd);

        starts.forEach((start) => {
            const explicitTarget = start.dataset.rangeEnd || start.dataset.dateRangeEnd;
            if (explicitTarget) {
                let target = null;
                try {
                    target = document.querySelector(explicitTarget);
                } catch (error) {
                    target = null;
                }
                target = target || document.getElementById(explicitTarget.replace(/^#/, ''));
                attachRangeLink(start, target);
                return;
            }
            const candidates = ends
                .map((end) => ({ end, score: scoreRangePair(start, end) }))
                .filter((item) => item.score >= 12)
                .sort((a, b) => b.score - a.score);

            const sameRowCandidates = candidates.filter((item) => item.score >= 40);
            const selected = sameRowCandidates.length ? sameRowCandidates : candidates.slice(0, 2);
            selected.forEach((item) => attachRangeLink(start, item.end));
        });
    }

    function initDateTimePickers(context = document) {
        const root = context && context.querySelectorAll ? context : document;
        ensureTimePickerStyles();
        normalizeNativeFields(root);
        root.querySelectorAll(PICKER_SELECTORS).forEach(initInput);
        linkDateRanges(root);
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
        if (input && !input._flatpickr) initInput(input);
        if (input && input._flatpickr) input._flatpickr.open();
        else if (input && input.focus) input.focus({ preventScroll: true });
    };

    function openLegacyShowPickerTarget(targetId) {
        const input = document.getElementById(targetId);
        if (!input || !window.flatpickr) return false;
        if (!input._flatpickr) initInput(input);
        if (!input._flatpickr || typeof input._flatpickr.open !== 'function') return false;
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
        ensureTimePickerStyles();
        initDateTimePickers(document);
        observeDynamicContent();
    });

    document.addEventListener('keydown', handleTimePickerKeydown);

    window.addEventListener('resize', function () {
        if (activeTimePicker && activeTimePicker.input) positionTimePicker(activeTimePicker.input);
    });

    window.addEventListener('scroll', function () {
        if (activeTimePicker && activeTimePicker.input) positionTimePicker(activeTimePicker.input);
    }, true);

    document.addEventListener('shown.bs.modal', function (event) {
        initDateTimePickers(event.target || document);
    });

    document.addEventListener('modal:opened', function (event) {
        initDateTimePickers(event.detail && event.detail.context ? event.detail.context : document);
    });
})();

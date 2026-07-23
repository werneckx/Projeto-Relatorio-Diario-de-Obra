(function () {
    function readEmpresaPageData() {
        const dataScript = document.getElementById('empresa-page-data');
        if (dataScript?.textContent) {
            try {
                return JSON.parse(dataScript.textContent);
            } catch (error) {
                console.error('Nao foi possivel interpretar os dados da pagina da empresa.', error);
            }
        }
        return window.__empresaPageData || {};
    }

    const pageData = readEmpresaPageData();
    const empresaUrls = pageData.urls || {};
    const empresaWorkflowData = pageData.workflow || {};
    const empresaWorkflowRoleOptions = empresaWorkflowData.roleOptions || [];
    const empresaWorkflowUserOptions = empresaWorkflowData.userOptions || [];
    const empresaWorkflowPreviewById = empresaWorkflowData.previewById || {};
    const empresaWorkflowDefaultId = Number(empresaWorkflowData.defaultId || 0);
    const previewObjectUrls = {};
    const empresaGeneralFormState = {
        initialized: false,
        previewMarkup: {},
    };
    const empresaImageConfig = {
        logo: {
            inputId: 'logo_empresa',
            imgId: 'img-logo',
            allowedTypes: ['image/png', 'image/webp'],
            maxBytes: 2 * 1024 * 1024,
            maxWidth: 2000,
            maxHeight: 2000,
            message: 'Use PNG ou WebP com até 2 MB e dimensões de até 2000x2000.',
        },
        icon: {
            inputId: 'icone_empresa',
            imgId: 'img-icon',
            allowedTypes: ['image/png', 'image/x-icon', 'image/vnd.microsoft.icon'],
            maxBytes: 512 * 1024,
            maxWidth: 512,
            maxHeight: 512,
            message: 'Use PNG ou ICO com até 512 KB e dimensões de até 512x512.',
        },
    };

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }

    function buildJsonHeaders() {
        const csrf = getCsrfToken();
        return Object.assign({ 'Content-Type': 'application/json' }, csrf ? { 'X-CSRFToken': csrf } : {});
    }

    async function fetchJson(url, options = {}) {
        const response = await fetch(url, Object.assign({
            headers: buildJsonHeaders(),
        }, options));
        const data = await response.json();
        return { response, data };
    }

    function initializeEmpresaGeneralFormState() {
        if (empresaGeneralFormState.initialized) return;
        ['logo', 'icon'].forEach((key) => {
            const container = document.getElementById(`preview-${key}`);
            if (container) {
                empresaGeneralFormState.previewMarkup[key] = container.innerHTML;
            }
        });
        empresaGeneralFormState.initialized = true;
    }

    function restoreEmpresaPreviewContainer(key) {
        const container = document.getElementById(`preview-${key}`);
        if (!container) return;
        const originalMarkup = empresaGeneralFormState.previewMarkup[key];
        if (typeof originalMarkup === 'string') {
            container.innerHTML = originalMarkup;
        }
    }

    function resetEmpresaGeneralForm() {
        const form = document.getElementById('empresaForm');
        form?.reset();
        Object.keys(previewObjectUrls).forEach((imgId) => {
            try {
                URL.revokeObjectURL(previewObjectUrls[imgId]);
            } catch (_) {
                // no-op
            }
            delete previewObjectUrls[imgId];
        });
        restoreEmpresaPreviewContainer('logo');
        restoreEmpresaPreviewContainer('icon');
        Object.keys(empresaImageConfig).forEach((key) => {
            setEmpresaImageError(key);
            setEmpresaImageResetVisible(key, false);
        });
    }

    function setEmpresaImageError(key, message = '') {
        const errorEl = document.querySelector(`[data-image-error="${key}"]`);
        if (!errorEl) return;
        errorEl.textContent = message;
        errorEl.classList.toggle('hidden', !message);
    }

    function setEmpresaImageResetVisible(key, visible) {
        document.querySelector(`[data-image-reset="${key}"]`)?.classList.toggle('hidden', !visible);
    }

    function clearEmpresaImageObjectUrl(imgId) {
        if (!previewObjectUrls[imgId]) return;
        try {
            URL.revokeObjectURL(previewObjectUrls[imgId]);
        } catch (_) {
            // no-op
        }
        delete previewObjectUrls[imgId];
    }

    function validateEmpresaImageFile(file, config) {
        if (!file) return Promise.resolve(null);
        if (!config.allowedTypes.includes(file.type)) {
            return Promise.resolve(config.message);
        }
        if (file.size > config.maxBytes) {
            return Promise.resolve(config.message);
        }
        if (file.type === 'image/x-icon' || file.type === 'image/vnd.microsoft.icon') {
            return Promise.resolve(null);
        }

        return new Promise((resolve) => {
            const objectUrl = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () => {
                const invalid = image.naturalWidth > config.maxWidth || image.naturalHeight > config.maxHeight;
                URL.revokeObjectURL(objectUrl);
                resolve(invalid ? config.message : null);
            };
            image.onerror = () => {
                URL.revokeObjectURL(objectUrl);
                resolve('Nao foi possivel ler a imagem selecionada.');
            };
            image.src = objectUrl;
        });
    }

    async function previewEmpresaImage(input, key) {
        const config = empresaImageConfig[key];
        if (!config) return false;
        const [file] = input.files || [];
        setEmpresaImageError(key);

        if (!file) {
            resetEmpresaImageSelection(key);
            return true;
        }

        const validationMessage = await validateEmpresaImageFile(file, config);
        if (validationMessage) {
            input.value = '';
            setEmpresaImageError(key, validationMessage);
            setEmpresaImageResetVisible(key, false);
            return false;
        }

        const imgId = config.imgId;
        const preview = document.getElementById(imgId);
        const previewContainer = preview?.parentElement || document.getElementById(`preview-${key}`);
        const objectUrl = URL.createObjectURL(file);
        clearEmpresaImageObjectUrl(imgId);
        previewObjectUrls[imgId] = objectUrl;
        if (!previewContainer) return true;
        if (!preview || preview.tagName !== 'IMG') {
            previewContainer.innerHTML = `<img src="${objectUrl}" id="${imgId}" alt="" class="max-w-full max-h-full object-contain p-4 animate-fade-in">`;
        } else {
            preview.src = objectUrl;
        }
        setEmpresaImageResetVisible(key, true);
        return true;
    }

    function resetEmpresaImageSelection(key) {
        const config = empresaImageConfig[key];
        if (!config) return;
        const input = document.getElementById(config.inputId);
        if (input) input.value = '';
        clearEmpresaImageObjectUrl(config.imgId);
        restoreEmpresaPreviewContainer(key);
        setEmpresaImageError(key);
        setEmpresaImageResetVisible(key, false);
    }

    function normalizeSearchText(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function escapeSvgText(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function sanitizeSvgMarkup(markup) {
        const rawMarkup = String(markup || '').trim();
        if (!rawMarkup) return '';
        const allowedElements = new Set([
            'svg', 'defs', 'g', 'path', 'circle', 'rect', 'polygon', 'polyline',
            'text', 'tspan', 'marker', 'filter', 'fedropshadow',
        ]);
        const allowedAttributes = new Set([
            'aria-label', 'class', 'cx', 'cy', 'd', 'dx', 'dy', 'fill', 'filter',
            'flood-color', 'flood-opacity', 'font-family', 'font-size', 'font-weight',
            'height', 'id', 'marker-end', 'markerheight', 'markerunits', 'markerwidth',
            'orient', 'points', 'preserveaspectratio', 'refx', 'refy', 'role', 'rx',
            'ry', 'r', 'stddeviation', 'stroke', 'stroke-linecap', 'stroke-linejoin',
            'stroke-width', 'text-anchor', 'viewbox', 'width', 'x', 'xmlns', 'y',
        ]);
        const parser = new DOMParser();
        const doc = parser.parseFromString(rawMarkup, 'image/svg+xml');
        if (doc.querySelector('parsererror') || doc.documentElement?.tagName?.toLowerCase() !== 'svg') {
            return '';
        }

        Array.from(doc.querySelectorAll('*')).forEach((node) => {
            const tagName = node.tagName.toLowerCase();
            if (!allowedElements.has(tagName)) {
                node.remove();
                return;
            }
            Array.from(node.attributes || []).forEach((attribute) => {
                const name = attribute.name.toLowerCase();
                const value = String(attribute.value || '');
                const isAllowedUrl = /^url\(#[-_a-zA-Z0-9:.]+\)$/.test(value);
                const hasUnsafeValue = /javascript:|data:|<|>/i.test(value) && !isAllowedUrl;
                if (name.startsWith('on') || !allowedAttributes.has(name) || hasUnsafeValue) {
                    node.removeAttribute(attribute.name);
                }
            });
        });

        return new XMLSerializer().serializeToString(doc.documentElement);
    }

    function normalizeWorkflowStageDisplay(value) {
        return String(value || 'Responsável').replace(/_/g, ' ').trim() || 'Responsável';
    }

    function wrapWorkflowSvgText(value, maxChars = 18, maxLines = 3) {
        const chunks = normalizeWorkflowStageDisplay(value)
            .split(/\s+/)
            .flatMap((word) => {
                if (word.length <= maxChars) return [word];
                const parts = [];
                for (let index = 0; index < word.length; index += maxChars) {
                    parts.push(word.slice(index, index + maxChars));
                }
                return parts;
            });
        const lines = [];
        let currentLine = '';

        chunks.forEach((word) => {
            const nextLine = currentLine ? `${currentLine} ${word}` : word;
            if (nextLine.length <= maxChars) {
                currentLine = nextLine;
                return;
            }
            if (currentLine) lines.push(currentLine);
            currentLine = word;
        });

        if (currentLine) lines.push(currentLine);
        if (lines.length <= maxLines) return lines;

        const visibleLines = lines.slice(0, maxLines);
        visibleLines[maxLines - 1] = `${visibleLines[maxLines - 1].slice(0, Math.max(maxChars - 3, 1))}...`;
        return visibleLines;
    }

    function wrapWorkflowSvgRoleTokenLines(value, maxChars = 20, maxLines = 4) {
        const tokens = normalizeWorkflowStageDisplay(value)
            .split(/\s+/)
            .filter(Boolean)
            .flatMap((word) => {
                const lower = word.toLowerCase();
                if (lower === 'e' || lower === 'ou') {
                    return [{ text: lower, connector: true }];
                }
                const upper = word.toUpperCase();
                if (upper.length <= maxChars) {
                    return [{ text: upper, connector: false }];
                }
                const parts = [];
                for (let index = 0; index < upper.length; index += maxChars) {
                    parts.push({ text: upper.slice(index, index + maxChars), connector: false });
                }
                return parts;
            });
        const lines = [];
        let currentLine = [];
        let currentLength = 0;
        const lineLength = (line) => line.reduce((sum, token) => sum + token.text.length, Math.max(line.length - 1, 0));

        tokens.forEach((token) => {
            const nextLength = currentLength + (currentLine.length ? 1 : 0) + token.text.length;
            if (!currentLine.length || nextLength <= maxChars) {
                currentLine.push(token);
                currentLength = nextLength;
                return;
            }
            lines.push(currentLine);
            currentLine = [token];
            currentLength = token.text.length;
        });

        if (currentLine.length) lines.push(currentLine);
        if (lines.length <= maxLines) return lines;

        const visibleLines = lines.slice(0, maxLines);
        const lastLine = visibleLines[maxLines - 1];
        const ellipsis = { text: '...', connector: false };
        while (lastLine.length && lineLength([...lastLine, ellipsis]) > maxChars) {
            lastLine.pop();
        }
        lastLine.push(ellipsis);
        return visibleLines;
    }

    function toNonNegativeNumber(value) {
        const normalized = Number(value);
        if (!Number.isFinite(normalized) || normalized < 0) return 0;
        return normalized;
    }

    function parseTimelineLabel(label) {
        const match = String(label || '').match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?$/);
        if (!match) return Number.MAX_SAFE_INTEGER;
        const day = Number(match[1]);
        const month = Number(match[2]);
        const year = match[3] ? Number(match[3].length === 2 ? `20${match[3]}` : match[3]) : new Date().getFullYear();
        if (!Number.isFinite(day) || !Number.isFinite(month) || !Number.isFinite(year)) return Number.MAX_SAFE_INTEGER;
        return (year * 10000) + (month * 100) + day;
    }

    function normalizeTimelineSeries(series) {
        if (!Array.isArray(series)) return [];
        return series.map((item) => ({
            label: String(item?.label || '').trim(),
            value: toNonNegativeNumber(item?.value),
        })).filter((item) => item.label);
    }

    function mergeTimelineSeries(execucoes, erros) {
        const labels = [];
        const labelsSet = new Set();
        const execucoesMap = new Map();
        const errosMap = new Map();

        normalizeTimelineSeries(execucoes).forEach((item) => {
            execucoesMap.set(item.label, item.value);
            if (!labelsSet.has(item.label)) {
                labels.push(item.label);
                labelsSet.add(item.label);
            }
        });

        normalizeTimelineSeries(erros).forEach((item) => {
            errosMap.set(item.label, item.value);
            if (!labelsSet.has(item.label)) {
                labels.push(item.label);
                labelsSet.add(item.label);
            }
        });

        return labels
            .map((label) => ({
                label,
                execucoes: toNonNegativeNumber(execucoesMap.get(label)),
                erros: toNonNegativeNumber(errosMap.get(label)),
                order: parseTimelineLabel(label),
            }))
            .filter((item) => item.execucoes > 0)
            .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
            .slice(-5)
            .map(({ order, ...item }) => item);
    }

    function normalizeWorkflowTipoResumoSeguro(item) {
        const origem = normalizeSearchText(item?.workflow_origem_tipo || item?.workflow_tipo_resumo);
        return origem === 'empresa' || origem === 'herdado' ? 'Herdado' : 'Próprio';
    }

    function normalizeDuracaoMediaFluxo(value) {
        const rawValue = String(value || '').trim();
        const normalized = normalizeSearchText(rawValue);
        if (!rawValue || normalized === 'sem historico' || normalized === '0 min' || normalized === '0 h' || normalized === 'nan') {
            return {
                value: 'Não disponível',
                available: false,
                helper: 'Ainda não existem execuções concluídas para calcular a duração média.',
            };
        }

        return {
            value: rawValue
                .replace(/^(\d+)d\s*(\d+)h$/i, '$1 dia $2 h')
                .replace(/^(\d+)h(\d{2})m$/i, '$1 h $2 min')
                .replace(/^(\d+)min$/i, '$1 min'),
            available: true,
            helper: '',
        };
    }

    function normalizeStatusBreakdown(series) {
        if (!Array.isArray(series)) return [];
        return series
            .map((item) => {
                const statusCode = String(item?.status_code || '');
                return {
                    status: statusCode.toUpperCase() === 'APROVADO' ? 'Concluído com Êxito' : String(item?.status || 'Sem execução'),
                    status_code: statusCode,
                    total: toNonNegativeNumber(item?.total),
                    badge_class: String(item?.badge_class || 'border-slate-200 bg-slate-100 text-slate-700'),
                    dot_class: String(item?.dot_class || 'bg-slate-400'),
                    icon: String(item?.icon || 'fa-circle-question'),
                };
            })
            .filter((item) => item.total > 0);
    }

    function normalizeWorkflowStatusCode(value) {
        const normalized = normalizeSearchText(value).replace(/\s+/g, '_');
        return {
            pendente: 'PENDENTE',
            em_andamento: 'EM_ANDAMENTO',
            concluido: 'APROVADO',
            aprovado: 'APROVADO',
            rejeitado: 'REJEITADO',
            cancelado: 'CANCELADO',
            erro: 'ERRO',
        }[normalized] || String(value || '').trim().toUpperCase();
    }

    function normalizeWorkflowHistorico(series) {
        if (!Array.isArray(series)) return [];
        return series
            .map((item) => ({
                id: item?.id ?? '',
                execution_number: String(item?.execution_number || ''),
                status: String(item?.status || ''),
                status_label: String(item?.status_label || 'Sem execucao'),
                status_badge_class: String(item?.status_badge_class || 'border-slate-200 bg-slate-100 text-slate-700'),
                status_dot_class: String(item?.status_dot_class || 'bg-slate-400'),
                started_at_label: String(item?.started_at_label || 'Sem registro'),
                duration_label: String(item?.duration_label || 'Sem duracao'),
                requester_name: String(item?.requester_name || 'Nao identificado'),
                workflow_name: String(item?.workflow_name || 'Workflow nao identificado'),
                detalhes_url: String(item?.detalhes_url || ''),
            }))
            .filter((item) => item.id || item.execution_number || item.started_at_label !== 'Sem registro');
    }

    function getObraWorkflowDiagramGroupKey(etapa, index) {
        if (etapa?.grupo_id != null && etapa.grupo_id !== '') return `grupo-id-${etapa.grupo_id}`;
        if (etapa?.grupo_ordem != null && etapa.grupo_ordem !== '') return `grupo-ordem-${etapa.grupo_ordem}`;
        if (etapa?.workflow_group != null && etapa.workflow_group !== '') return `workflow-group-${etapa.workflow_group}`;
        if (etapa?.grupo_paralelo != null && etapa.grupo_paralelo !== '') return `grupo-paralelo-${etapa.grupo_paralelo}`;
        return `nivel-${etapa?.nivel || index + 1}`;
    }

    function getObraWorkflowDiagramGroupOrder(etapa, index) {
        return toNonNegativeNumber(etapa?.grupo_ordem)
            || toNonNegativeNumber(etapa?.workflow_group)
            || toNonNegativeNumber(etapa?.grupo_paralelo)
            || toNonNegativeNumber(etapa?.nivel)
            || (index + 1);
    }

    function joinObraWorkflowDiagramApprovers(etapas, regra) {
        const labels = (Array.isArray(etapas) ? etapas : [])
            .map((etapa) => normalizeWorkflowStageDisplay(etapa?.papel || etapa?.papel_nome || etapa?.usuario_nome || etapa?.nome))
            .filter(Boolean);
        if (!labels.length) return 'Papel nao definido';
        if (labels.length === 1) return labels[0];
        const connector = normalizeEmpresaWorkflowGroupRule(regra) === 'QUALQUER' ? ' ou ' : ' e ';
        return `${labels.slice(0, -1).join(connector)}${connector}${labels[labels.length - 1]}`;
    }

    function groupObraWorkflowDiagramStages(etapas, obra) {
        const groups = new Map();
        (Array.isArray(etapas) ? etapas : []).forEach((etapa, index) => {
            const key = getObraWorkflowDiagramGroupKey(etapa, index);
            if (!groups.has(key)) {
                groups.set(key, {
                    key,
                    order: getObraWorkflowDiagramGroupOrder(etapa, index),
                    items: [],
                });
            }
            groups.get(key).items.push(etapa);
        });

        const isParallel = String(obra?.workflow_diagram_variant || '').toLowerCase() === 'parallel' || obra?.aprovacao_paralela;
        const entityLabel = isParallel ? 'Grupo' : 'Etapa';

        return Array.from(groups.values())
            .sort((a, b) => a.order - b.order)
            .map((group, groupIndex) => {
                const first = group.items[0] || {};
                const regra = normalizeEmpresaWorkflowGroupRule(first.regra_aprovacao || first.regra_etapa || 'TODOS');
                const label = joinObraWorkflowDiagramApprovers(group.items, regra);
                return {
                    ...first,
                    nivel: groupIndex + 1,
                    nome: label,
                    papel: label,
                    rotulo: `${entityLabel} ${groupIndex + 1}`,
                    regra_aprovacao: regra,
                    regra_etapa: regra,
                    tempo_medio: String(first.tempo_medio || 'Sem historico'),
                    workflow_group: groupIndex + 1,
                    grupo_itens: group.items,
                };
            });
    }

    function normalizeObraDetalhe(item) {
        if (!item) return null;
        const workflowEtapasRaw = Array.isArray(item.workflow_etapas)
            ? item.workflow_etapas.map((etapa, index) => ({
                ...etapa,
                nivel: toNonNegativeNumber(etapa?.nivel) || (index + 1),
                nome: String(etapa?.nome || `Etapa ${index + 1}`),
                papel: String(etapa?.papel || etapa?.nome || `Etapa ${index + 1}`),
                tempo_medio: String(etapa?.tempo_medio || 'Sem histórico'),
            }))
            : [];
        const workflowEtapas = groupObraWorkflowDiagramStages(workflowEtapasRaw, item);
        const timelineExecucoes = normalizeTimelineSeries(item.timeline_execucoes);
        const timelineErros = normalizeTimelineSeries(item.timeline_erros);
        const duracaoMediaFluxo = normalizeDuracaoMediaFluxo(item.duracao_media_fluxo);
        const execucoesStatus = normalizeStatusBreakdown(item.execucoes_status);

        return {
            ...item,
            obra_nome: String(item.obra_nome || 'Obra sem nome'),
            workflow_nome: String(item.workflow_nome || 'Sem workflow'),
            workflow_etapas: workflowEtapas,
            execucoes_total: toNonNegativeNumber(item.execucoes_total),
            execucoes_status: execucoesStatus,
            workflow_tipo_resumo: normalizeWorkflowTipoResumoSeguro(item),
            obra_workflow_url: String(item.obra_workflow_url || ''),
            obra_workflow_historico_url: String(item.obra_workflow_historico_url || item.obra_workflow_url || ''),
            workflow_historico: normalizeWorkflowHistorico(item.workflow_historico || item.workflow_execucoes_historico),
            duracao_media_fluxo: duracaoMediaFluxo.value,
            duracao_media_fluxo_disponivel: duracaoMediaFluxo.available,
            duracao_media_fluxo_ajuda: duracaoMediaFluxo.helper,
            timeline_execucoes: timelineExecucoes,
            timeline_erros: timelineErros,
            timeline_resumo: mergeTimelineSeries(timelineExecucoes, timelineErros),
            matriz: Array.isArray(item.matriz) ? item.matriz : [],
            ultima_atualizacao: String(item.ultima_atualizacao || 'não disponível'),
        };
    }

    function prefersReducedMotion() {
        return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    }

    function getEmpresaPageRoot() {
        return document.getElementById('empresaPageRoot');
    }

    function prepareEmpresaRouteTransition() {
        const root = getEmpresaPageRoot();
        if (!root || prefersReducedMotion()) return;

        root.style.transition = 'opacity 140ms ease, transform 140ms ease';
        if (sessionStorage.getItem('empresaRouteTransition') === '1') {
            sessionStorage.removeItem('empresaRouteTransition');
            root.style.opacity = '0';
            root.style.transform = 'translateY(4px)';
            requestAnimationFrame(() => {
                root.style.opacity = '1';
                root.style.transform = 'translateY(0)';
                window.setTimeout(() => {
                    root.style.transition = '';
                    root.style.opacity = '';
                    root.style.transform = '';
                }, 170);
            });
            return;
        }
        root.style.transition = '';
        root.style.opacity = '';
        root.style.transform = '';
    }

    function navigateEmpresaRoute(url) {
        if (!url) return;
        if (prefersReducedMotion()) {
            window.location.href = url;
            return;
        }

        const root = getEmpresaPageRoot();
        sessionStorage.setItem('empresaRouteTransition', '1');
        if (!root) {
            window.location.href = url;
            return;
        }

        root.style.transition = 'opacity 120ms ease, transform 120ms ease';
        root.style.opacity = '0';
        root.style.transform = 'translateY(-3px)';
        window.setTimeout(() => {
            window.location.href = url;
        }, 120);
    }

    function replaceEmpresaRoute(url) {
        if (!url || window.location.href === url) return;
        try {
            window.history.pushState({ empresaRoute: url }, '', url);
        } catch (_) {
            // A troca de URL e apenas cosmetica; se falhar, mantemos a tela sem reload.
        }
    }

        function empresaApp() {
            return {
                abaAtiva: localStorage.getItem('empresa_aba_ativa') || 'geral',
                tabOrder: ['geral', 'workflow'],
                novaDefinicaoVisible: false,
                novoDefinicao: { chave: '', descricao: '', valor: '', tipo: 'STRING' },
                novoPapelVisible: false,
                formPapel: { nome: '', descricao: '', permissoes: [] },
                novoWorkflowVisible: false,
                formWorkflow: { nome: '', descricao: '', obra_id: '', etapas: [{ nome: '' }] },
                mostrarWorkflowDefaultForm: false,
                legendaWorkflowVisible: false,
                modalObrasVisible: false,
                obraDetalheVisible: false,
                obraSelecionada: null,
                timelineTooltip: null,
                workflowDiagramDragging: null,
                workflowDiagramZoom: 1,
                workflowStagesPanelOpen: false,
                workflowStagesPanelPosition: null,
                workflowStagesPanelDrag: null,
                workflowStagesPanelHeight: null,
                workflowStagesPanelResize: null,
                workflowSubtab: localStorage.getItem('empresa_workflow_subtab') || 'configuracao',
                filtroObras: '',
                filtroWorkflow: '',
                filtroResponsavel: '',
                filtroStatus: '',
                obrasWorkflowData: pageData.obrasWorkflowData || [],
                workflowDefaultCodigo: pageData.workflowDefaultCodigo || 'SIMPLES',
                empresaEditing: Boolean(pageData.startInEditMode),
                saving: false,

                init() {
                    this.abaAtiva = localStorage.getItem('empresa_aba_ativa') || this.abaAtiva || 'geral';
                    if (!this.tabOrder.includes(this.abaAtiva)) {
                        this.abaAtiva = 'geral';
                        localStorage.setItem('empresa_aba_ativa', this.abaAtiva);
                    }
                    prepareEmpresaRouteTransition();
                    initializeEmpresaGeneralFormState();
                    setEmpresaEditingDataset(this.empresaEditing);
                    window.applyRequiredMarkers?.(document);
                    if (typeof this.$watch === 'function') {
                        this.$watch('filtroStatus', syncEmpresaStatusFilterPickers);
                        this.$watch('empresaEditing', (editing) => {
                            if (!editing) this.closeWorkflowStagesPanel();
                        });
                        this.$watch('abaAtiva', (aba) => {
                            if (aba !== 'workflow') this.closeWorkflowStagesPanel();
                        });
                        this.$watch('workflowSubtab', (subtab) => {
                            if (subtab !== 'configuracao') this.closeWorkflowStagesPanel();
                        });
                    }
                },
                mudarAba(aba) {
                    if (!this.tabOrder.includes(aba)) return;
                    this.abaAtiva = aba;
                    localStorage.setItem('empresa_aba_ativa', aba);
                    if (aba !== 'workflow') {
                        this.closeWorkflowStagesPanel();
                        closeEmpresaWorkflowTypeDropdown();
                    }
                },
                focarAba(aba) {
                    document.querySelector(`[data-empresa-tab="${aba}"]`)?.focus();
                },
                focarProximaAba() {
                    const currentIndex = this.tabOrder.indexOf(this.abaAtiva);
                    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % this.tabOrder.length : 0;
                    const nextTab = this.tabOrder[nextIndex];
                    this.mudarAba(nextTab);
                    this.focarAba(nextTab);
                },
                focarAbaAnterior() {
                    const currentIndex = this.tabOrder.indexOf(this.abaAtiva);
                    const previousIndex = currentIndex >= 0 ? (currentIndex - 1 + this.tabOrder.length) % this.tabOrder.length : 0;
                    const previousTab = this.tabOrder[previousIndex];
                    this.mudarAba(previousTab);
                    this.focarAba(previousTab);
                },
                focarPrimeiraAba() {
                    const firstTab = this.tabOrder[0] || 'geral';
                    this.mudarAba(firstTab);
                    this.focarAba(firstTab);
                },
                focarUltimaAba() {
                    const lastTab = this.tabOrder[this.tabOrder.length - 1] || 'geral';
                    this.mudarAba(lastTab);
                    this.focarAba(lastTab);
                },
                mudarWorkflowSubtab(subtab) {
                    this.workflowSubtab = subtab === 'obras' ? 'obras' : 'configuracao';
                    localStorage.setItem('empresa_workflow_subtab', this.workflowSubtab);
                    if (this.workflowSubtab !== 'configuracao') this.closeWorkflowStagesPanel();
                },
                openWorkflowStagesPanel() {
                    if (!this.empresaEditing || this.abaAtiva !== 'workflow' || this.workflowSubtab !== 'configuracao') return;
                    this.workflowStagesPanelOpen = true;
                    this.$nextTick?.(() => this.ensureWorkflowStagesPanelPosition());
                },
                closeWorkflowStagesPanel() {
                    this.workflowStagesPanelOpen = false;
                    this.workflowStagesPanelDrag = null;
                    this.workflowStagesPanelResize = null;
                    if (typeof closeEmpresaWorkflowTypeDropdown === 'function') closeEmpresaWorkflowTypeDropdown();
                },
                toggleWorkflowStagesPanel() {
                    if (this.workflowStagesPanelOpen) {
                        this.closeWorkflowStagesPanel();
                        return;
                    }
                    this.openWorkflowStagesPanel();
                },
                getWorkflowStagesPanelMetrics() {
                    const margin = 12;
                    const viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
                    const viewportHeight = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
                    const panel = document.getElementById('workflowCompanyStagesPanel');
                    const panelWidth = Math.min(440, Math.max(280, viewportWidth - (margin * 2)));
                    const rect = panel?.getBoundingClientRect();
                    const width = rect?.width || panelWidth;
                    const minHeight = Math.min(280, Math.max(180, viewportHeight - (margin * 2)));
                    const height = Math.min(this.workflowStagesPanelHeight || rect?.height || 520, viewportHeight - (margin * 2));
                    return { margin, viewportWidth, viewportHeight, panelWidth, width, height, minHeight };
                },
                clampWorkflowStagesPanelHeight(height, y = null) {
                    const metrics = this.getWorkflowStagesPanelMetrics();
                    const top = Number.isFinite(y) ? y : (this.workflowStagesPanelPosition?.y || metrics.margin);
                    const maxHeight = Math.max(metrics.minHeight, metrics.viewportHeight - top - metrics.margin);
                    return Math.min(Math.max(height, metrics.minHeight), maxHeight);
                },
                clampWorkflowStagesPanelPosition(position) {
                    const metrics = this.getWorkflowStagesPanelMetrics();
                    const maxX = Math.max(metrics.margin, metrics.viewportWidth - metrics.width - metrics.margin);
                    const maxY = Math.max(metrics.margin, metrics.viewportHeight - metrics.height - metrics.margin);
                    return {
                        x: Math.min(Math.max(position.x, metrics.margin), maxX),
                        y: Math.min(Math.max(position.y, metrics.margin), maxY),
                        width: metrics.panelWidth,
                    };
                },
                ensureWorkflowStagesPanelPosition() {
                    const metrics = this.getWorkflowStagesPanelMetrics();
                    const fallback = {
                        x: metrics.viewportWidth - metrics.panelWidth - 24,
                        y: 96,
                        width: metrics.panelWidth,
                    };
                    const nextPosition = this.clampWorkflowStagesPanelPosition(this.workflowStagesPanelPosition || fallback);
                    const current = this.workflowStagesPanelPosition;
                    if (!current || current.x !== nextPosition.x || current.y !== nextPosition.y || current.width !== nextPosition.width) {
                        this.workflowStagesPanelPosition = nextPosition;
                    }
                    const fallbackHeight = Math.min(560, metrics.viewportHeight - nextPosition.y - metrics.margin);
                    const nextHeight = this.clampWorkflowStagesPanelHeight(this.workflowStagesPanelHeight || fallbackHeight, nextPosition.y);
                    if (this.workflowStagesPanelHeight !== nextHeight) {
                        this.workflowStagesPanelHeight = nextHeight;
                    }
                },
                getWorkflowStagesPanelStyle() {
                    this.ensureWorkflowStagesPanelPosition();
                    const position = this.workflowStagesPanelPosition;
                    const metrics = this.getWorkflowStagesPanelMetrics();
                    const maxHeight = Math.max(240, metrics.viewportHeight - position.y - metrics.margin);
                    const height = this.clampWorkflowStagesPanelHeight(this.workflowStagesPanelHeight || maxHeight, position.y);
                    return `left: ${position.x}px; top: ${position.y}px; width: ${position.width}px; height: ${height}px; max-height: ${maxHeight}px;`;
                },
                startWorkflowStagesPanelDrag(event) {
                    if (event.button !== 0 || event.target?.closest?.('button, a, input, select, textarea, [data-workflow-custom-dropdown]')) return;
                    this.ensureWorkflowStagesPanelPosition();
                    const panel = document.getElementById('workflowCompanyStagesPanel');
                    this.workflowStagesPanelDrag = {
                        pointerId: event.pointerId,
                        startClientX: event.clientX,
                        startClientY: event.clientY,
                        startX: this.workflowStagesPanelPosition.x,
                        startY: this.workflowStagesPanelPosition.y,
                    };
                    panel?.setPointerCapture?.(event.pointerId);
                    event.preventDefault();
                },
                moveWorkflowStagesPanelDrag(event) {
                    const drag = this.workflowStagesPanelDrag;
                    if (!drag || drag.pointerId !== event.pointerId) return;
                    this.workflowStagesPanelPosition = this.clampWorkflowStagesPanelPosition({
                        x: drag.startX + event.clientX - drag.startClientX,
                        y: drag.startY + event.clientY - drag.startClientY,
                    });
                },
                endWorkflowStagesPanelDrag(event) {
                    const drag = this.workflowStagesPanelDrag;
                    if (!drag || drag.pointerId !== event.pointerId) return;
                    const panel = document.getElementById('workflowCompanyStagesPanel');
                    if (panel?.hasPointerCapture?.(event.pointerId)) {
                        panel.releasePointerCapture(event.pointerId);
                    }
                    this.workflowStagesPanelDrag = null;
                },
                startWorkflowStagesPanelResize(event) {
                    if (event.button !== 0) return;
                    this.ensureWorkflowStagesPanelPosition();
                    const panel = document.getElementById('workflowCompanyStagesPanel');
                    this.workflowStagesPanelResize = {
                        pointerId: event.pointerId,
                        startClientY: event.clientY,
                        startHeight: this.workflowStagesPanelHeight || panel?.getBoundingClientRect?.().height || 520,
                    };
                    panel?.setPointerCapture?.(event.pointerId);
                    event.preventDefault();
                },
                moveWorkflowStagesPanelResize(event) {
                    const resize = this.workflowStagesPanelResize;
                    if (!resize || resize.pointerId !== event.pointerId) return;
                    this.workflowStagesPanelHeight = this.clampWorkflowStagesPanelHeight(
                        resize.startHeight + event.clientY - resize.startClientY,
                        this.workflowStagesPanelPosition?.y,
                    );
                },
                endWorkflowStagesPanelResize(event) {
                    const resize = this.workflowStagesPanelResize;
                    if (!resize || resize.pointerId !== event.pointerId) return;
                    const panel = document.getElementById('workflowCompanyStagesPanel');
                    if (panel?.hasPointerCapture?.(event.pointerId)) {
                        panel.releasePointerCapture(event.pointerId);
                    }
                    this.workflowStagesPanelResize = null;
                },
                adjustWorkflowStagesPanelHeight(delta) {
                    this.ensureWorkflowStagesPanelPosition();
                    this.workflowStagesPanelHeight = this.clampWorkflowStagesPanelHeight(
                        (this.workflowStagesPanelHeight || 520) + delta,
                        this.workflowStagesPanelPosition?.y,
                    );
                },
                isSectionEditing() {
                    return this.empresaEditing;
                },
                hasGlobalActions() {
                    return ['geral', 'workflow'].includes(this.abaAtiva);
                },
                getActionDescription() {
                    if (this.abaAtiva === 'geral') {
                        return this.empresaEditing
                            ? 'Revise os dados institucionais antes de salvar.'
                            : 'Ative a edicao para alterar nome, logotipo e icone.';
                    }
                    if (this.abaAtiva === 'workflow') {
                        return this.empresaEditing
                            ? 'Ajuste a estrutura do workflow e salve quando terminar.'
                            : 'Ative a edicao para modificar o workflow padrao da empresa.';
                    }
                    if (this.abaAtiva === 'definicoes') {
                        return 'A secao de definicoes esta em desenvolvimento.';
                    }
                    if (this.abaAtiva === 'papeis') {
                        return 'A secao de papeis esta em desenvolvimento.';
                    }
                    return 'Use os controles disponiveis nesta secao.';
                },
                isSaveDisabled() {
                    if (!this.empresaEditing) return true;
                    return false;
                },
                async handleEmpresaImageChange(event, key) {
                    await previewEmpresaImage(event.target, key);
                },
                resetEmpresaImageSelection(key) {
                    resetEmpresaImageSelection(key);
                },
                startSectionEdit() {
                    if (this.empresaEditing) return;
                    this.empresaEditing = true;
                    setEmpresaEditingDataset(true);
                    replaceEmpresaRoute(empresaUrls.empresaEdit);
                    renderEmpresaWorkflowCards();
                },
                cancelSectionEdit() {
                    resetEmpresaGeneralForm();
                    window.resetEmpresaWorkflowEditor?.();
                    this.novoDefinicao = { chave: '', descricao: '', valor: '', tipo: 'STRING' };
                    this.novaDefinicaoVisible = false;
                    this.resetFormPapel();
                    this.resetFormWorkflow();
                    this.empresaEditing = false;
                    setEmpresaEditingDataset(false);
                    pageData.startInEditMode = false;
                    replaceEmpresaRoute(empresaUrls.empresaView);
                    closeEmpresaWorkflowTypeDropdown();
                    renderEmpresaWorkflowCards();
                },
                saveSection() {
                    if (this.saving || this.isSaveDisabled()) return;
                    if (this.abaAtiva === 'geral') {
                        const form = document.getElementById('empresaForm');
                        if (form && typeof form.reportValidity === 'function' && !form.reportValidity()) return;
                        this.saving = true;
                        form?.requestSubmit();
                        return;
                    }
                    if (this.abaAtiva === 'workflow') {
                        this.saving = true;
                        Promise.resolve(window.saveEmpresaWorkflowAction?.()).finally(() => {
                            this.saving = false;
                        });
                        return;
                    }
                    this.empresaEditing = false;
                    setEmpresaEditingDataset(false);
                    replaceEmpresaRoute(empresaUrls.empresaView);
                },
                async criarDefinicao() {
                    try {
                        const { response, data } = await fetchJson(empresaUrls.createDefinicao, {
                            method: 'POST',
                            body: JSON.stringify(this.novoDefinicao)
                        });
                        if (response.ok && data.ok) {
                            this.novaDefinicaoVisible = false;
                            this.novoDefinicao = { chave: '', descricao: '', valor: '', tipo: 'STRING' };
                            location.reload();
                        } else {
                            await showError('Erro ao criar definicao', data.error || 'Erro ao criar definicao.');
                        }
                    } catch (err) {
                        console.error(err);
                        await showError('Erro de rede', 'Erro de rede ao criar definicao.');
                    }
                },
                resetFormPapel() {
                    this.novoPapelVisible = false;
                    this.formPapel = { nome: '', descricao: '', permissoes: [] };
                },
                async criarPapel() {
                    try {
                        const { response, data } = await fetchJson(empresaUrls.createPapel, {
                            method: 'POST',
                            body: JSON.stringify(this.formPapel)
                        });
                        if (response.ok && data.ok) {
                            this.resetFormPapel();
                            location.reload();
                        } else {
                            await showError('Erro ao criar papel', data.error || 'Erro ao criar papel.');
                        }
                    } catch (err) {
                        console.error(err);
                        await showError('Erro de rede', 'Erro de rede ao criar papel.');
                    }
                },
                resetFormWorkflow() {
                    this.novoWorkflowVisible = false;
                    this.formWorkflow = { nome: '', descricao: '', obra_id: '', etapas: [{ nome: '' }] };
                },
                adicionarEtapa() {
                    this.formWorkflow.etapas.push({ nome: '' });
                },
                removerEtapa(index) {
                    if (this.formWorkflow.etapas.length > 1) {
                        this.formWorkflow.etapas.splice(index, 1);
                    }
                },
                async criarWorkflow() {
                    const payload = {
                        nome: this.formWorkflow.nome,
                        descricao: this.formWorkflow.descricao,
                        obra_id: this.formWorkflow.obra_id || null,
                        etapas: this.formWorkflow.etapas.filter(e => e.nome.trim()).map(e => ({ nome: e.nome.trim() }))
                    };
                    if (!payload.nome) return await showWarning('Workflow incompleto', 'Nome do workflow e obrigatorio.');
                    if (!payload.etapas.length) return await showWarning('Workflow incompleto', 'Adicione ao menos uma etapa.');
                    try {
                        const { response, data } = await fetchJson(empresaUrls.createWorkflow, {
                            method: 'POST',
                            body: JSON.stringify(payload)
                        });
                        if (response.ok && data.ok) {
                            this.resetFormWorkflow();
                            location.reload();
                        } else {
                            await showError('Erro ao criar workflow', data.error || 'Erro ao criar workflow.');
                        }
                    } catch (err) {
                        console.error(err);
                        await showError('Erro de rede', 'Erro de rede ao criar workflow.');
                    }
                },
                async salvarWorkflowDefault() {
                    if (!this.workflowDefaultCodigo) {
                        return await showWarning('Workflow padrao ausente', 'Selecione um workflow corporativo para a empresa.');
                    }
                    try {
                        const { response, data } = await fetchJson(empresaUrls.updateWorkflowDefault, {
                            method: 'POST',
                            body: JSON.stringify({ codigo: this.workflowDefaultCodigo })
                        });
                        if (response.ok && data.ok) {
                            location.reload();
                        } else {
                            await showError('Erro ao definir workflow padrao', data.error || 'Erro ao definir workflow padrao.');
                        }
                    } catch (err) {
                        console.error(err);
                        await showError('Erro de rede', 'Erro de rede ao definir workflow padrao.');
                    }
                },
                filteredObras() {
                    const termoObra = normalizeSearchText(this.filtroObras);
                    const termoWorkflow = normalizeSearchText(this.filtroWorkflow);
                    const termoResponsavel = normalizeSearchText(this.filtroResponsavel);
                    const statusFilter = normalizeWorkflowStatusCode(this.filtroStatus);
                    return this.obrasWorkflowData.filter((obra) => {
                        const matchObra = !termoObra || normalizeSearchText(obra.obra_nome).includes(termoObra);
                        const matchWorkflow = !termoWorkflow || normalizeSearchText(obra.workflow_nome).includes(termoWorkflow);
                        const matchResponsavel = !termoResponsavel || normalizeSearchText(obra.responsavel).includes(termoResponsavel);
                        const obraStatus = normalizeWorkflowStatusCode(obra.status_code || obra.status);
                        const matchStatus = !statusFilter || obraStatus === statusFilter;
                        return matchObra && matchWorkflow && matchResponsavel && matchStatus;
                    });
                },
                abrirModalObras() {
                    this.modalObrasVisible = true;
                },
                fecharModalObras() {
                    this.modalObrasVisible = false;
                },
                abrirDetalhesObra(obraId) {
                    const obra = this.obrasWorkflowData.find((item) => item.obra_id === obraId) || null;
                    this.obraSelecionada = normalizeObraDetalhe(obra);
                    this.resetarZoomDiagrama();
                    this.obraDetalheVisible = !!this.obraSelecionada;
                    this.$nextTick?.(() => this.syncObraWorkflowDiagramViewport(true));
                },
                fecharDetalhesObra() {
                    this.obraDetalheVisible = false;
                    this.obraSelecionada = null;
                    this.encerrarArrasteDiagrama();
                    this.resetarZoomDiagrama();
                },
                alterarZoomDiagrama(delta) {
                    const nextZoom = Number(this.workflowDiagramZoom || 1) + Number(delta || 0);
                    this.workflowDiagramZoom = Math.min(2, Math.max(0.5, Math.round(nextZoom * 10) / 10));
                    this.syncObraWorkflowDiagramViewport();
                    return this.workflowDiagramZoom;
                },
                zoomDiagramaPorWheel(event) {
                    if (!event || !event.currentTarget || !event.ctrlKey) {
                        return;
                    }

                    event.preventDefault();
                    event.stopPropagation();
                    const canvas = event.currentTarget;
                    const currentZoom = Math.min(2, Math.max(0.5, Number(this.workflowDiagramZoom || 1)));
                    const rect = canvas.getBoundingClientRect();
                    const offsetX = event.clientX - rect.left;
                    const offsetY = event.clientY - rect.top;
                    const anchorX = canvas.scrollLeft + offsetX;
                    const anchorY = canvas.scrollTop + offsetY;
                    const nextZoom = this.alterarZoomDiagrama(event.deltaY < 0 ? 0.1 : -0.1);

                    if (nextZoom === currentZoom) {
                        return;
                    }

                    window.requestAnimationFrame(() => {
                        const ratio = nextZoom / currentZoom;
                        canvas.scrollLeft = (anchorX * ratio) - offsetX;
                        canvas.scrollTop = (anchorY * ratio) - offsetY;
                    });
                },
                iniciarArrasteDiagrama(event) {
                    if (!event || !event.currentTarget || event.button !== 0) {
                        return;
                    }

                    event.preventDefault();
                    const canvas = event.currentTarget;
                    if (typeof canvas.setPointerCapture === 'function' && event.pointerId != null) {
                        canvas.setPointerCapture(event.pointerId);
                    }
                    this.workflowDiagramDragging = {
                        canvas,
                        pointerId: event.pointerId,
                        startX: event.clientX,
                        startY: event.clientY,
                        scrollLeft: canvas.scrollLeft,
                        scrollTop: canvas.scrollTop,
                    };
                    canvas.classList.add('workflow-canvas--dragging');
                },
                arrastarDiagrama(event) {
                    const drag = this.workflowDiagramDragging;
                    if (!drag || !drag.canvas || !event) {
                        return;
                    }
                    if (event.buttons !== 1) {
                        this.encerrarArrasteDiagrama();
                        return;
                    }

                    event.preventDefault();
                    drag.canvas.scrollLeft = drag.scrollLeft - (event.clientX - drag.startX);
                    drag.canvas.scrollTop = drag.scrollTop - (event.clientY - drag.startY);
                },
                encerrarArrasteDiagrama() {
                    if (this.workflowDiagramDragging?.canvas) {
                        const { canvas, pointerId } = this.workflowDiagramDragging;
                        if (typeof canvas.releasePointerCapture === 'function' && pointerId != null && canvas.hasPointerCapture?.(pointerId)) {
                            canvas.releasePointerCapture(pointerId);
                        }
                        this.workflowDiagramDragging.canvas.classList.remove('workflow-canvas--dragging');
                    }
                    this.workflowDiagramDragging = null;
                },
                resetarZoomDiagrama() {
                    this.workflowDiagramZoom = 1;
                    this.syncObraWorkflowDiagramViewport(true);
                },
                getZoomDiagramaLabel() {
                    return `${Math.round((this.workflowDiagramZoom || 1) * 100)}%`;
                },
                syncObraWorkflowDiagramViewport(resetScroll = false) {
                    const diagramEl = document.getElementById('workflowObraDetailDiagram');
                    const canvasEl = document.getElementById('workflowObraDetailDiagramCanvas');
                    if (!diagramEl) return;

                    const etapas = this.getObraFluxoEtapas(this.obraSelecionada);
                    if (!etapas.length) {
                        diagramEl.innerHTML = '';
                        diagramEl.removeAttribute('style');
                        if (resetScroll && canvasEl) {
                            canvasEl.scrollLeft = 0;
                            canvasEl.scrollTop = 0;
                        }
                        return;
                    }

                    const zoom = Math.min(2, Math.max(0.5, Number(this.workflowDiagramZoom || 1)));
                    this.workflowDiagramZoom = Math.round(zoom * 10) / 10;
                    const baseSize = this.getWorkflowDiagramBaseSize(this.obraSelecionada);
                    const width = Math.round(baseSize.width * this.workflowDiagramZoom);
                    const height = Math.round(baseSize.height * this.workflowDiagramZoom);
                    diagramEl.style.width = `${width}px`;
                    diagramEl.style.minWidth = `${width}px`;
                    diagramEl.style.height = `${height}px`;
                    diagramEl.style.minHeight = `${height}px`;

                    if (resetScroll && canvasEl) {
                        canvasEl.scrollLeft = 0;
                        canvasEl.scrollTop = 0;
                    }
                },
                getWorkflowDiagramBoardStyle(obra) {
                    const zoom = Math.min(2, Math.max(0.5, Number(this.workflowDiagramZoom || 1)));
                    const baseSize = this.getWorkflowDiagramBaseSize(obra);
                    const width = Math.round(baseSize.width * zoom);
                    const height = Math.round(baseSize.height * zoom);
                    return `width:${width}px; min-width:${width}px; height:${height}px; min-height:${height}px;`;
                },
                getObraWorkflowDetalhesUrl(obra) {
                    return String(obra?.obra_workflow_url || '').trim() || '#';
                },
                getObraWorkflowHistoricoUrl(obra) {
                    return String(obra?.obra_workflow_historico_url || obra?.obra_workflow_url || '').trim() || '#';
                },
                abrirDetalhesWorkflowObra(obra) {
                    const url = this.getObraWorkflowDetalhesUrl(obra);
                    if (!url || url === '#') return;
                    window.location.assign(url);
                },
                getObraWorkflowHistorico(obra) {
                    return Array.isArray(obra?.workflow_historico) ? obra.workflow_historico : [];
                },
                getObraTimelineSeries(obra) {
                    return Array.isArray(obra?.timeline_resumo) ? obra.timeline_resumo : [];
                },
                getObraStatusSeries(obra) {
                    return Array.isArray(obra?.execucoes_status) ? obra.execucoes_status : [];
                },
                getObraStatusTotal(obra) {
                    return this.getObraStatusSeries(obra).reduce((total, item) => total + toNonNegativeNumber(item.total), 0);
                },
                getObraStatusMax(obra) {
                    const values = this.getObraStatusSeries(obra).map((item) => toNonNegativeNumber(item.total));
                    const max = Math.max(0, ...values);
                    return max > 0 ? max : 1;
                },
                getObraStatusBarWidth(item, obra) {
                    return `${Math.max((toNonNegativeNumber(item?.total) / this.getObraStatusMax(obra)) * 100, 0)}%`;
                },
                getObraStatusColor(item) {
                    const code = String(item?.status_code || '').toUpperCase();
                    if (code === 'APROVADO') return '#149318';
                    if (code === 'REJEITADO' || code === 'ERRO') return '#d31313';
                    if (code === 'CANCELADO') return '#64748b';
                    if (code === 'PENDENTE') return '#f59e0b';
                    if (code === 'EM_ANDAMENTO' || code === 'REABERTO') return '#64748b';
                    return '#94a3b8';
                },
                getObraStatusDonutStyle(obra) {
                    const series = this.getObraStatusSeries(obra);
                    const total = this.getObraStatusTotal(obra);
                    if (!series.length || total <= 0) {
                        return 'background: conic-gradient(#cbd5e1 0 360deg)';
                    }
                    let cursor = 0;
                    const segments = series.map((item) => {
                        const start = cursor;
                        const span = (toNonNegativeNumber(item.total) / total) * 360;
                        cursor += span;
                        return `${this.getObraStatusColor(item)} ${start}deg ${cursor}deg`;
                    });
                    return `background: conic-gradient(${segments.join(', ')})`;
                },
                getObraStatusSuccessPercent(obra) {
                    const total = this.getObraStatusTotal(obra);
                    if (total <= 0) return 0;
                    const success = this.getObraStatusSeries(obra)
                        .filter((item) => String(item.status_code || '').toUpperCase() === 'APROVADO')
                        .reduce((sum, item) => sum + toNonNegativeNumber(item.total), 0);
                    return Math.round((success / total) * 100);
                },
                getObraStatusLegend(obra) {
                    return this.getObraStatusSeries(obra).slice(0, 3);
                },
                getObraTimelineMax(obra) {
                    const values = this.getObraTimelineSeries(obra).flatMap((item) => [toNonNegativeNumber(item.execucoes), toNonNegativeNumber(item.erros)]);
                    const max = Math.max(0, ...values);
                    return max > 0 ? max : 1;
                },
                getObraTimelineChartWidthValue(obra) {
                    const count = this.getObraTimelineSeries(obra).length;
                    return Math.max(count * 104, 520);
                },
                getObraTimelineGeometry(obra) {
                    const width = this.getObraTimelineChartWidthValue(obra);
                    const height = 220;
                    const margin = { top: 18, right: 18, bottom: 36, left: 42 };
                    return {
                        width,
                        height,
                        margin,
                        plotWidth: Math.max(width - margin.left - margin.right, 1),
                        plotHeight: Math.max(height - margin.top - margin.bottom, 1),
                        baseline: height - margin.bottom,
                    };
                },
                getObraTimelineX(index, obra) {
                    const series = this.getObraTimelineSeries(obra);
                    const geometry = this.getObraTimelineGeometry(obra);
                    const stepWidth = geometry.plotWidth / Math.max(series.length, 1);
                    return geometry.margin.left + (stepWidth * index) + (stepWidth / 2);
                },
                getObraTimelineY(value, obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    const ratio = toNonNegativeNumber(value) / this.getObraTimelineMax(obra);
                    return geometry.baseline - (ratio * geometry.plotHeight);
                },
                getObraTimelineBarWidth(obra) {
                    const series = this.getObraTimelineSeries(obra);
                    const geometry = this.getObraTimelineGeometry(obra);
                    const stepWidth = geometry.plotWidth / Math.max(series.length, 1);
                    return Math.min(34, Math.max(22, stepWidth * 0.38));
                },
                getObraTimelineBarX(index, obra) {
                    return this.getObraTimelineX(index, obra) - (this.getObraTimelineBarWidth(obra) / 2);
                },
                getObraTimelineBarY(value, obra) {
                    return this.getObraTimelineY(value, obra);
                },
                getObraTimelineBarSvgHeight(value, obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    return Math.max(0, geometry.baseline - this.getObraTimelineY(value, obra));
                },
                getObraTimelineTicks(obra) {
                    const max = this.getObraTimelineMax(obra);
                    return [1, 0.75, 0.5, 0.25, 0].map((ratio, index) => ({
                        key: `${index}-${Math.round(max * ratio)}`,
                        value: Math.round(max * ratio),
                        y: this.getObraTimelineY(Math.round(max * ratio), obra),
                    }));
                },
                getObraTimelineTickStyle(tick) {
                    return `top:${tick.y}px`;
                },
                getObraTimelineChartWidth(obra) {
                    return `${this.getObraTimelineChartWidthValue(obra)}px`;
                },
                getObraTimelineBarStyle(item, index, obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    return [
                        `left:${this.getObraTimelineBarX(index, obra)}px`,
                        `top:${this.getObraTimelineBarY(item.execucoes, obra)}px`,
                        `width:${this.getObraTimelineBarWidth(obra)}px`,
                        `height:${this.getObraTimelineBarSvgHeight(item.execucoes, obra)}px`,
                    ].join(';');
                },
                getObraTimelinePointStyle(item, index, obra) {
                    return `left:${this.getObraTimelineX(index, obra)}px; top:${this.getObraTimelineY(item.erros, obra)}px`;
                },
                getObraTimelineLabelStyle(index, obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    const series = this.getObraTimelineSeries(obra);
                    const stepWidth = geometry.plotWidth / Math.max(series.length, 1);
                    return `left:${geometry.margin.left + (stepWidth * index)}px; width:${stepWidth}px; top:${geometry.height - 24}px`;
                },
                getObraTimelinePolylinePoints(obra) {
                    return this.getObraTimelineSeries(obra)
                        .map((item, index) => `${this.getObraTimelineX(index, obra)},${this.getObraTimelineY(item.erros, obra)}`)
                        .join(' ');
                },
                getObraTimelineViewBox(obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    return `0 0 ${geometry.width} ${geometry.height}`;
                },
                getObraTimelineTooltipText(item) {
                    return `${item.label}\nExecuções de fluxo: ${toNonNegativeNumber(item.execucoes)}\nErros do fluxo: ${toNonNegativeNumber(item.erros)}`;
                },
                showObraTimelineTooltip(item, index, obra) {
                    const geometry = this.getObraTimelineGeometry(obra);
                    this.timelineTooltip = {
                        label: item.label,
                        execucoes: toNonNegativeNumber(item.execucoes),
                        erros: toNonNegativeNumber(item.erros),
                        left: `${this.getObraTimelineX(index, obra)}px`,
                        top: `${Math.max(geometry.margin.top, this.getObraTimelineY(item.erros, obra) - 76)}px`,
                    };
                },
                hideObraTimelineTooltip() {
                    this.timelineTooltip = null;
                },
                getObraFluxoEtapas(obra) {
                    return Array.isArray(obra?.workflow_etapas) ? obra.workflow_etapas : [];
                },
                getWorkflowDiagramStageCount() {
                    return this.getObraFluxoEtapas(this.obraSelecionada).length;
                },
                getWorkflowDiagramLayout(stageCount) {
                    const columns = stageCount <= 1 ? 1 : 2;
                    const rowHeight = 250;
                    const firstRowY = 88;
                    const rows = Math.ceil(stageCount / columns);
                    return {
                        badgeH: 22,
                        badgeW: 90,
                        cardH: 150,
                        cardW: 230,
                        cardX: 130,
                        columnWidth: 520,
                        columns,
                        decisionGap: 88,
                        diamondHalf: 42,
                        firstRowY,
                        height: firstRowY + ((rows - 1) * rowHeight) + 184,
                        rejectedBadgeW: 94,
                        rowHeight,
                        startCx: 54,
                        startR: 28,
                        width: columns === 1 ? 850 : 1390,
                    };
                },
                getWorkflowParallelForkJoinDiagramSize(obra, etapas) {
                    const L = {
                        PADDING_X: 72,
                        PADDING_TOP: 58,
                        PADDING_BOTTOM: 86,
                        CARD_WIDTH: 240,
                        CARD_MIN_HEIGHT: 110,
                        CARD_GAP: 38,
                        NODE_RADIUS: 28,
                        DECISION_HALF: 42,
                        START_TO_SPLIT: 86,
                        SPLIT_TO_CARD: 90,
                        CARD_TO_SYNC: 92,
                        SYNC_TO_DECISION: 110,
                        RESULT_GAP: 80,
                        APPROVED_BADGE_WIDTH: 90,
                        BADGE_HEIGHT: 22,
                        END_GAP: 76,
                        END_LABEL_WIDTH: 138,
                        REJECT_GAP: 40,
                    };
                    const normalizeApproverLabel = (label) => {
                        const normalized = normalizeWorkflowStageDisplay(label);
                        return normalized.toUpperCase() === 'CLIENTE OBRA' ? 'Cliente da Obra' : normalized;
                    };
                    const approvers = etapas.map((etapa, index) => {
                        const source = String(etapa?.papel || etapa?.nome || `Aprovador ${index + 1}`);
                        return normalizeApproverLabel(source);
                    });

                    if (!approvers.length) {
                        return { width: 960, height: 420 };
                    }

                    const cardHeights = approvers.map((label) => Math.max(L.CARD_MIN_HEIGHT, 62 + (wrapWorkflowSvgRoleTokenLines(label, 17, 4).length * 22)));
                    const normalizedCardHeight = Math.max(...cardHeights);
                    const gridHeight = (approvers.length * normalizedCardHeight) + ((approvers.length - 1) * L.CARD_GAP);
                    const startCx = L.PADDING_X + L.NODE_RADIUS;
                    const splitX = startCx + L.NODE_RADIUS + L.START_TO_SPLIT;
                    const cardX = splitX + L.SPLIT_TO_CARD;
                    const syncX = cardX + L.CARD_WIDTH + L.CARD_TO_SYNC;
                    const decisionCx = syncX + L.SYNC_TO_DECISION;
                    const approvedBadgeX = decisionCx + L.DECISION_HALF + L.RESULT_GAP;
                    const approvedEndCx = approvedBadgeX + L.APPROVED_BADGE_WIDTH + L.END_GAP;
                    const width = approvedEndCx + L.NODE_RADIUS + 28 + L.END_LABEL_WIDTH + L.PADDING_X;
                    const decisionCy = L.PADDING_TOP + Math.max(gridHeight / 2, L.NODE_RADIUS + L.DECISION_HALF);
                    const approvedBottom = decisionCy + L.NODE_RADIUS;
                    const rejectedBadgeY = decisionCy + L.DECISION_HALF + L.REJECT_GAP;
                    const rejectedEndBottom = rejectedBadgeY + L.BADGE_HEIGHT + L.RESULT_GAP + 18;
                    const height = Math.max(L.PADDING_TOP + gridHeight + L.PADDING_BOTTOM, rejectedEndBottom + L.PADDING_BOTTOM, approvedBottom + L.PADDING_BOTTOM);

                    return { width, height };
                },
                getWorkflowDiagramBaseSize(obra) {
                    const etapas = this.getObraFluxoEtapas(obra);
                    if (!etapas.length) {
                        return { width: 960, height: 420 };
                    }
                    if (String(obra?.workflow_diagram_variant || '').toLowerCase() === 'parallel' || obra?.aprovacao_paralela) {
                        return this.getWorkflowParallelForkJoinDiagramSize(obra, etapas);
                    }
                    const layout = this.getWorkflowDiagramLayout(etapas.length);
                    return { width: layout.width, height: layout.height };
                },
                getWorkflowDiagramStagePosition(index, layout) {
                    const column = index % layout.columns;
                    const row = Math.floor(index / layout.columns);
                    const rowY = layout.firstRowY + (row * layout.rowHeight);
                    const cardX = layout.cardX + (column * layout.columnWidth);
                    const decisionCx = cardX + layout.cardW + layout.decisionGap;
                    const approvedBadgeX = decisionCx + layout.diamondHalf + 18;
                    return {
                        approvedBadgeX,
                        approvedBadgeY: rowY - (layout.badgeH / 2),
                        cardX,
                        cardY: rowY - (layout.cardH / 2),
                        column,
                        decisionCx,
                        decisionCy: rowY,
                        row,
                        rowY,
                    };
                },
                renderWorkflowSvgPath(d, color, markerId = '') {
                    const marker = markerId ? ` marker-end="url(#${markerId})"` : '';
                    return `<path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"${marker}></path>`;
                },
                renderWorkflowSvgBadge(label, x, y, width, height, color) {
                    const centerY = y + (height / 2) + 4;
                    return [
                        `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${height / 2}" fill="#ffffff" stroke="${color}" stroke-width="1.4"></rect>`,
                        `<text x="${x + (width / 2)}" y="${centerY}" fill="${color}" text-anchor="middle" font-size="10" font-weight="800">${escapeSvgText(label.toUpperCase())}</text>`,
                    ].join('');
                },
                renderWorkflowSvgTextLines(lines, x, y, lineHeight, attrs) {
                    return lines
                        .map((line, index) => `<text x="${x}" y="${y + (index * lineHeight)}" ${attrs}>${escapeSvgText(line)}</text>`)
                        .join('');
                },
                renderWorkflowSvgRoleTextLines(lines, x, y, lineHeight, color, fontSize = 17, clip = null) {
                    const content = lines
                        .map((line, index) => {
                            const content = line
                                .map((token, tokenIndex) => {
                                    const space = tokenIndex ? '<tspan xml:space="preserve"> </tspan>' : '';
                                    const weight = token.connector ? '400' : '800';
                                    return `${space}<tspan font-weight="${weight}">${escapeSvgText(token.text)}</tspan>`;
                                })
                                .join('');
                            return `<text x="${x}" y="${y + (index * lineHeight)}" fill="${color}" font-size="${fontSize}">${content}</text>`;
                        })
                        .join('');
                    if (!clip?.id || !clip?.width || !clip?.height) return content;
                    return [
                        `<clipPath id="${clip.id}"><rect x="${x}" y="${clip.y ?? y - fontSize}" width="${clip.width}" height="${clip.height}"></rect></clipPath>`,
                        `<g clip-path="url(#${clip.id})">${content}</g>`,
                    ].join('');
                },
                getWorkflowApprovedConnectorPath(currentStage, nextStage, layout) {
                    const fromX = currentStage.approvedBadgeX + layout.badgeW;
                    const fromY = currentStage.rowY;
                    const toX = nextStage.cardX;
                    const toY = nextStage.rowY;
                    if (currentStage.row === nextStage.row) {
                        return `M ${fromX} ${fromY} H ${toX}`;
                    }
                    const gutterX = Math.min(layout.width - 48, Math.max(fromX + 38, toX + 240));
                    const laneY = nextStage.cardY - 18;
                    const preEntryX = toX - 30;
                    return `M ${fromX} ${fromY} H ${gutterX} V ${laneY} H ${preEntryX} V ${toY} H ${toX}`;
                },
                getWorkflowParallelDiagramSvg(obra, etapas) {
                    return this.getWorkflowParallelForkJoinDiagramSvg(obra, etapas);
                    const neutral = '#475569';
                    const green = '#15803d';
                    const red = '#dc2626';
                    const slate = '#64748b';
                    const dark = '#0f172a';
                    const parallelRule = String(obra?.regra_etapa || etapas[0]?.regra_etapa || 'TODOS').toUpperCase() === 'PRIMEIRO'
                        ? 'PRIMEIRO'
                        : 'TODOS';
                    const approvers = etapas.flatMap((etapa, index) => {
                        const source = String(etapa?.papel || etapa?.nome || `Aprovador ${index + 1}`);
                        const parts = source.split(',').map((item) => normalizeWorkflowStageDisplay(item)).filter(Boolean);
                        return (parts.length ? parts : [normalizeWorkflowStageDisplay(source)]).map((label, itemIndex) => ({
                            id: `${index + 1}-${itemIndex + 1}`,
                            label,
                        }));
                    });
                    if (!approvers.length) return '';

                    const margin = { top: 64, right: 120, bottom: 80, left: 72 };
                    const spacing = {
                        startToFork: 110,
                        forkToCards: 92,
                        cardGapX: 28,
                        cardGapY: 40,
                        cardsToJoin: 92,
                        joinToDecision: 116,
                        decisionToResult: 72,
                        resultToEnd: 90,
                        rejectToEnd: 80,
                    };
                    const startRadius = 28;
                    const splitRadius = 18;
                    const joinRadius = 18;
                    const cardWidth = 176;
                    const cardPaddingX = 16;
                    const cardPaddingTop = 14;
                    const cardPaddingBottom = 16;
                    const cardLineHeight = 20;
                    const maxCardLines = 3;
                    const decisionHalf = 42;
                    const approvedBadge = { width: 94, height: 22 };
                    const rejectedBadge = { width: 96, height: 22 };

                    const cardModels = approvers.map((item) => {
                        const lines = wrapWorkflowSvgText(item.label, 16, maxCardLines);
                        const height = cardPaddingTop + 14 + (lines.length * cardLineHeight) + cardPaddingBottom;
                        return { ...item, lines, height };
                    });

                    const columns = approvers.length <= 4 ? approvers.length : (approvers.length <= 8 ? 3 : 1);
                    const rowsCount = Math.ceil(cardModels.length / columns);
                    const rows = Array.from({ length: rowsCount }, (_, rowIndex) => cardModels.slice(rowIndex * columns, (rowIndex + 1) * columns));
                    const rowHeights = rows.map((row) => Math.max(...row.map((item) => item.height)));
                    const totalCardsHeight = rowHeights.reduce((sum, value) => sum + value, 0) + (Math.max(rows.length - 1, 0) * spacing.cardGapY);
                    const cardAreaHeight = Math.max(totalCardsHeight, 240);
                    const startCx = margin.left;
                    const forkX = startCx + startRadius + spacing.startToFork;
                    const cardsX = forkX + spacing.forkToCards;
                    const cardsAreaWidth = (columns * cardWidth) + (Math.max(columns - 1, 0) * spacing.cardGapX);
                    const joinX = cardsX + cardsAreaWidth + spacing.cardsToJoin;
                    const decisionCx = joinX + spacing.joinToDecision;
                    const approvedBadgeX = decisionCx + decisionHalf + spacing.decisionToResult;
                    const approvedEndX = approvedBadgeX + approvedBadge.width + spacing.resultToEnd;
                    const endLabelWidth = 132;
                    const width = approvedEndX + splitRadius + endLabelWidth + margin.right;
                    const cardAreaTop = margin.top + 24;
                    const cardAreaBottom = cardAreaTop + cardAreaHeight;
                    const centerY = cardAreaTop + (cardAreaHeight / 2);
                    const decisionCy = centerY;
                    const approvedEndY = centerY;
                    const rejectedBadgeX = decisionCx + decisionHalf + spacing.decisionToResult;
                    const rejectedBadgeY = decisionCy + 56;
                    const rejectedEndX = rejectedBadgeX + 26;
                    const rejectedEndY = rejectedBadgeY + rejectedBadge.height + spacing.rejectToEnd;
                    const height = Math.max(cardAreaBottom, rejectedEndY + splitRadius + margin.bottom);

                    let currentY = cardAreaTop + ((cardAreaHeight - totalCardsHeight) / 2);
                    const cardLayout = [];
                    rows.forEach((row, rowIndex) => {
                        const rowHeight = rowHeights[rowIndex];
                        const rowWidth = (row.length * cardWidth) + (Math.max(row.length - 1, 0) * spacing.cardGapX);
                        const rowStartX = cardsX + ((cardsAreaWidth - rowWidth) / 2);
                        row.forEach((item, colIndex) => {
                            const x = rowStartX + (colIndex * (cardWidth + spacing.cardGapX));
                            const y = currentY + ((rowHeight - item.height) / 2);
                            cardLayout.push({
                                ...item,
                                x,
                                y,
                                width: cardWidth,
                                centerY: y + (item.height / 2),
                            });
                        });
                        currentY += rowHeight + spacing.cardGapY;
                    });

                    const connectors = [];
                    const shapes = [];
                    const labels = [];

                    connectors.push(this.renderWorkflowSvgPath(
                        `M ${startCx + startRadius} ${centerY} H ${forkX - splitRadius}`,
                        neutral,
                        'workflow-arrow-neutral',
                    ));
                    shapes.push(`<circle cx="${startCx}" cy="${centerY}" r="${startRadius}" fill="${slate}" filter="url(#workflow-node-shadow)"></circle>`);
                    shapes.push(`<circle cx="${forkX}" cy="${centerY}" r="${splitRadius}" fill="${slate}" filter="url(#workflow-node-shadow)"></circle>`);
                    shapes.push(`<circle cx="${joinX}" cy="${centerY}" r="${joinRadius}" fill="${slate}" filter="url(#workflow-node-shadow)"></circle>`);
                    labels.push(`<text x="${startCx}" y="${centerY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Início</text>`);
                    labels.push(`<text x="${forkX}" y="${centerY - 30}" fill="${slate}" text-anchor="middle" font-size="11" font-weight="800">Fork</text>`);
                    labels.push(`<text x="${joinX}" y="${centerY - 30}" fill="${slate}" text-anchor="middle" font-size="11" font-weight="800">Join</text>`);

                    cardLayout.forEach((card) => {
                        connectors.push(this.renderWorkflowSvgPath(`M ${forkX} ${centerY} H ${card.x - 18} V ${card.centerY} H ${card.x}`, neutral));
                        connectors.push(this.renderWorkflowSvgPath(`M ${card.x + card.width} ${card.centerY} H ${joinX}`, neutral, 'workflow-arrow-neutral'));
                        shapes.push(`<rect x="${card.x}" y="${card.y}" width="${card.width}" height="${card.height}" rx="8" fill="#ffffff" stroke="#cbd5e1" filter="url(#workflow-card-shadow)"></rect>`);
                        labels.push(`<text x="${card.x + cardPaddingX}" y="${card.y + 18}" fill="#475569" font-size="11" font-weight="800">PAPEL</text>`);
                        labels.push(this.renderWorkflowSvgTextLines(
                            card.lines,
                            card.x + cardPaddingX,
                            card.y + 44,
                            cardLineHeight,
                            `fill="${dark}" font-size="15" font-weight="800"`,
                        ));
                    });

                    connectors.push(this.renderWorkflowSvgPath(`M ${joinX + joinRadius} ${centerY} H ${decisionCx - decisionHalf}`, neutral, 'workflow-arrow-neutral'));
                    connectors.push(this.renderWorkflowSvgPath(`M ${decisionCx + decisionHalf} ${decisionCy} H ${approvedBadgeX}`, green));
                    connectors.push(this.renderWorkflowSvgPath(`M ${approvedBadgeX + approvedBadge.width} ${approvedEndY} H ${approvedEndX - splitRadius}`, green, 'workflow-arrow-approved'));
                    connectors.push(this.renderWorkflowSvgPath(`M ${decisionCx} ${decisionCy + decisionHalf} V ${rejectedBadgeY}`, red));
                    connectors.push(this.renderWorkflowSvgPath(`M ${rejectedBadgeX + rejectedBadge.width} ${rejectedBadgeY + (rejectedBadge.height / 2)} H ${rejectedEndX}`, red));
                    connectors.push(this.renderWorkflowSvgPath(`M ${rejectedEndX} ${rejectedBadgeY + (rejectedBadge.height / 2)} V ${rejectedEndY - splitRadius}`, red, 'workflow-arrow-rejected'));

                    shapes.push(`<polygon points="${decisionCx},${decisionCy - decisionHalf} ${decisionCx + decisionHalf},${decisionCy} ${decisionCx},${decisionCy + decisionHalf} ${decisionCx - decisionHalf},${decisionCy}" fill="${slate}" filter="url(#workflow-node-shadow)"></polygon>`);
                    shapes.push(`<circle cx="${approvedEndX}" cy="${approvedEndY}" r="${splitRadius}" fill="#16a34a"></circle>`);
                    shapes.push(`<circle cx="${rejectedEndX}" cy="${rejectedEndY}" r="21" fill="${red}"></circle>`);
                    labels.push(`<text x="${decisionCx}" y="${decisionCy - 8}" fill="#ffffff" text-anchor="middle" font-size="10" font-weight="800">Todos</text>`);
                    labels.push(`<text x="${decisionCx}" y="${decisionCy + 10}" fill="#ffffff" text-anchor="middle" font-size="10" font-weight="800">${parallelRule === 'PRIMEIRO' ? 'responderam?' : 'aprovaram?'}</text>`);
                    labels.push(this.renderWorkflowSvgBadge('Aprovado', approvedBadgeX, approvedEndY - (approvedBadge.height / 2), approvedBadge.width, approvedBadge.height, green));
                    labels.push(this.renderWorkflowSvgBadge('Recusado', rejectedBadgeX, rejectedBadgeY, rejectedBadge.width, rejectedBadge.height, red));
                    labels.push(`<path d="M ${approvedEndX - 8} ${approvedEndY} L ${approvedEndX - 2} ${approvedEndY + 6} L ${approvedEndX + 9} ${approvedEndY - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
                    labels.push(`<text x="${approvedEndX + 28}" y="${approvedEndY + 6}" fill="${green}" font-size="17" font-weight="800">Fim aprovado</text>`);
                    labels.push(`<text x="${rejectedEndX}" y="${rejectedEndY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Fim</text>`);

                    return `
                        <svg class="workflow-board-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Diagrama de aprovação paralela" xmlns="http://www.w3.org/2000/svg">
                            <defs>
                                <marker id="workflow-arrow-neutral" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${neutral}"></path>
                                </marker>
                                <marker id="workflow-arrow-approved" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${green}"></path>
                                </marker>
                                <marker id="workflow-arrow-rejected" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${red}"></path>
                                </marker>
                                <filter id="workflow-card-shadow" x="-10%" y="-10%" width="120%" height="130%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.10"></feDropShadow>
                                </filter>
                                <filter id="workflow-node-shadow" x="-20%" y="-20%" width="140%" height="140%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#0f172a" flood-opacity="0.16"></feDropShadow>
                                </filter>
                            </defs>
                            <g font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
                                ${shapes.join('')}
                                ${connectors.join('')}
                                ${labels.join('')}
                            </g>
                        </svg>
                    `;
                },
                getWorkflowParallelForkJoinDiagramSvg(obra, etapas) {
                    const COLORS = {
                        neutral: '#475569',
                        green: '#15803d',
                        red: '#dc2626',
                        slate: '#64748b',
                        dark: '#0f172a',
                    };
                    const L = {
                        PADDING_X: 72,
                        PADDING_TOP: 58,
                        PADDING_BOTTOM: 86,
                        CARD_WIDTH: 240,
                        CARD_MIN_HEIGHT: 110,
                        CARD_GAP: 38,
                        NODE_RADIUS: 28,
                        DECISION_HALF: 42,
                        START_TO_SPLIT: 86,
                        SPLIT_TO_CARD: 90,
                        CARD_TO_SYNC: 92,
                        SYNC_TO_DECISION: 110,
                        RESULT_GAP: 80,
                        APPROVED_BADGE_WIDTH: 90,
                        BADGE_HEIGHT: 22,
                        END_GAP: 76,
                        END_LABEL_WIDTH: 138,
                        REJECT_GAP: 40,
                    };
                    const rule = String(obra?.regra_etapa || etapas[0]?.regra_etapa || 'TODOS').toUpperCase() === 'PRIMEIRO'
                        ? 'PRIMEIRO'
                        : 'TODOS';
                    const normalizeApproverLabel = (label) => {
                        const normalized = normalizeWorkflowStageDisplay(label);
                        return normalized.toUpperCase() === 'CLIENTE OBRA' ? 'Cliente da Obra' : normalized;
                    };
                    const approvers = etapas.map((etapa, index) => {
                        const source = String(etapa?.papel || etapa?.nome || `Aprovador ${index + 1}`);
                        return {
                            id: `${index + 1}`,
                            label: normalizeApproverLabel(source),
                            title: String(etapa?.rotulo || `Grupo ${index + 1}`),
                            nivel: etapa?.nivel || index + 1,
                        };
                    });
                    if (!approvers.length) return '';

                    const createCard = (approver, index) => {
                        const lines = wrapWorkflowSvgRoleTokenLines(approver.label, 17, 4);
                        return {
                            ...approver,
                            index,
                            lines,
                            width: L.CARD_WIDTH,
                            height: Math.max(L.CARD_MIN_HEIGHT, 62 + (lines.length * 22)),
                        };
                    };
                    const createCircleNode = (cx, cy, r) => ({ cx, cy, r });
                    const createDecision = (cx, cy) => ({ cx, cy, half: L.DECISION_HALF });
                    const createBadge = (x, y, width = L.BADGE_WIDTH, height = L.BADGE_HEIGHT) => ({ x, y, width, height });
                    const anchor = (node, side = 'center') => {
                        const radius = node.r ?? node.half ?? 0;
                        if (side === 'top') return { x: node.cx ?? (node.x + node.width / 2), y: node.cy != null ? node.cy - radius : node.y };
                        if (side === 'bottom') return { x: node.cx ?? (node.x + node.width / 2), y: node.cy != null ? node.cy + radius : node.y + node.height };
                        if (side === 'left') return { x: node.cx != null ? node.cx - (node.r ?? node.half) : node.x, y: node.cy ?? (node.y + node.height / 2) };
                        if (side === 'right') return { x: node.cx != null ? node.cx + (node.r ?? node.half) : node.x + node.width, y: node.cy ?? (node.y + node.height / 2) };
                        return { x: node.cx ?? (node.x + node.width / 2), y: node.cy ?? (node.y + node.height / 2) };
                    };
                    const roundedPath = (points, radius = 12) => {
                        if (points.length < 2) return '';
                        const parts = [`M ${points[0].x} ${points[0].y}`];
                        for (let index = 1; index < points.length; index += 1) {
                            const current = points[index];
                            const next = points[index + 1];
                            if (!next) {
                                parts.push(`L ${current.x} ${current.y}`);
                                continue;
                            }
                            const previous = points[index - 1];
                            const incomingHorizontal = previous.y === current.y;
                            const outgoingHorizontal = next.y === current.y;
                            if (incomingHorizontal === outgoingHorizontal) {
                                parts.push(`L ${current.x} ${current.y}`);
                                continue;
                            }
                            const before = { x: current.x, y: current.y };
                            const after = { x: current.x, y: current.y };
                            if (incomingHorizontal) before.x += previous.x < current.x ? -radius : radius;
                            else before.y += previous.y < current.y ? -radius : radius;
                            if (outgoingHorizontal) after.x += next.x < current.x ? -radius : radius;
                            else after.y += next.y < current.y ? -radius : radius;
                            parts.push(`L ${before.x} ${before.y}`);
                            parts.push(`Q ${current.x} ${current.y} ${after.x} ${after.y}`);
                        }
                        return parts.join(' ');
                    };
                    const drawConnector = (points, color, markerId = '') => this.renderWorkflowSvgPath(roundedPath(points), color, markerId);
                    const calculateLayout = () => {
                        const cards = approvers.map(createCard);
                        const cardHeight = Math.max(...cards.map((card) => card.height));
                        cards.forEach((card) => {
                            card.height = cardHeight;
                        });
                        const gridHeight = (cards.length * cardHeight) + ((cards.length - 1) * L.CARD_GAP);
                        const startCx = L.PADDING_X + L.NODE_RADIUS;
                        const splitX = startCx + L.NODE_RADIUS + L.START_TO_SPLIT;
                        const cardX = splitX + L.SPLIT_TO_CARD;
                        const syncX = cardX + L.CARD_WIDTH + L.CARD_TO_SYNC;
                        const decisionCx = syncX + L.SYNC_TO_DECISION;
                        const approvedBadgeX = decisionCx + L.DECISION_HALF + L.RESULT_GAP;
                        const approvedEndCx = approvedBadgeX + L.APPROVED_BADGE_WIDTH + L.END_GAP;
                        const width = approvedEndCx + L.NODE_RADIUS + 28 + L.END_LABEL_WIDTH + L.PADDING_X;
                        const centerY = L.PADDING_TOP + Math.max(gridHeight / 2, L.NODE_RADIUS + L.DECISION_HALF);
                        const gridTop = centerY - (gridHeight / 2);
                        cards.forEach((card, index) => {
                            card.x = cardX;
                            card.y = gridTop + (index * (cardHeight + L.CARD_GAP));
                        });
                        const start = createCircleNode(startCx, centerY, L.NODE_RADIUS);
                        const split = { x: splitX, y: centerY };
                        const sync = { x: syncX, y: centerY };
                        const decision = createDecision(decisionCx, centerY);
                        const approvedBadge = createBadge(approvedBadgeX, centerY - (L.BADGE_HEIGHT / 2), L.APPROVED_BADGE_WIDTH, L.BADGE_HEIGHT);
                        const approvedEnd = createCircleNode(approvedEndCx, centerY, 18);
                        const rejectedBadge = createBadge(decisionCx - 47, anchor(decision, 'bottom').y + L.REJECT_GAP, 94, L.BADGE_HEIGHT);
                        const rejectedEnd = createCircleNode(decisionCx, anchor(rejectedBadge, 'bottom').y + L.RESULT_GAP, 18);
                        const height = Math.max(L.PADDING_TOP + gridHeight + L.PADDING_BOTTOM, anchor(rejectedEnd, 'bottom').y + L.PADDING_BOTTOM, anchor(approvedEnd, 'bottom').y + L.PADDING_BOTTOM);
                        return { cards, width, height, start, split, sync, decision, approvedBadge, approvedEnd, rejectedBadge, rejectedEnd };
                    };

                    const layout = calculateLayout();
                    const connectors = [];
                    const shapes = [];
                    const labels = [];
                    const svgId = `workflow-parallel-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
                    const ids = {
                        neutralArrow: `${svgId}-arrow-neutral`,
                        approvedArrow: `${svgId}-arrow-approved`,
                        rejectedArrow: `${svgId}-arrow-rejected`,
                        cardShadow: `${svgId}-card-shadow`,
                        nodeShadow: `${svgId}-node-shadow`,
                    };

                    connectors.push(drawConnector([anchor(layout.start, 'right'), layout.split], COLORS.neutral));
                    layout.cards.forEach((card) => {
                        const cardLeft = anchor(card, 'left');
                        const cardRight = anchor(card, 'right');
                        connectors.push(drawConnector([
                            layout.split,
                            { x: layout.split.x + 46, y: layout.split.y },
                            { x: layout.split.x + 46, y: cardLeft.y },
                            cardLeft,
                        ], COLORS.neutral, ids.neutralArrow));
                        connectors.push(drawConnector([
                            cardRight,
                            { x: layout.sync.x - 46, y: cardRight.y },
                            { x: layout.sync.x - 46, y: layout.sync.y },
                            layout.sync,
                        ], COLORS.neutral));
                    });
                    connectors.push(drawConnector([layout.sync, anchor(layout.decision, 'left')], COLORS.neutral, ids.neutralArrow));
                    connectors.push(drawConnector([anchor(layout.decision, 'right'), anchor(layout.approvedBadge, 'left')], COLORS.green));
                    connectors.push(drawConnector([anchor(layout.approvedBadge, 'right'), anchor(layout.approvedEnd, 'left')], COLORS.green, ids.approvedArrow));
                    connectors.push(drawConnector([
                        anchor(layout.decision, 'bottom'),
                        { x: anchor(layout.decision, 'bottom').x, y: anchor(layout.rejectedBadge, 'top').y - 18 },
                        anchor(layout.rejectedBadge, 'top'),
                    ], COLORS.red));
                    connectors.push(drawConnector([anchor(layout.rejectedBadge, 'bottom'), anchor(layout.rejectedEnd, 'top')], COLORS.red, ids.rejectedArrow));

                    shapes.push(`<circle cx="${layout.start.cx}" cy="${layout.start.cy}" r="${layout.start.r}" fill="${COLORS.slate}" filter="url(#${ids.nodeShadow})"></circle>`);
                    layout.cards.forEach((card) => {
                        shapes.push(`<rect x="${card.x}" y="${card.y}" width="${card.width}" height="${card.height}" rx="8" fill="#ffffff" stroke="#cbd5e1" filter="url(#${ids.cardShadow})"></rect>`);
                        labels.push(`<text x="${card.x + 16}" y="${card.y + 30}" fill="#475569" font-size="12" font-weight="800">${escapeSvgText(card.title || `Grupo ${card.nivel || card.index + 1}`).toUpperCase()}</text>`);
                        labels.push(this.renderWorkflowSvgRoleTextLines(card.lines, card.x + 16, card.y + 62, 22, COLORS.dark, 17, {
                            id: `${svgId}-card-${card.index}-text-clip`,
                            width: card.width - 32,
                            height: card.height - 66,
                            y: card.y + 44,
                        }));
                    });
                    shapes.push(`<polygon points="${layout.decision.cx},${layout.decision.cy - layout.decision.half} ${layout.decision.cx + layout.decision.half},${layout.decision.cy} ${layout.decision.cx},${layout.decision.cy + layout.decision.half} ${layout.decision.cx - layout.decision.half},${layout.decision.cy}" fill="${COLORS.slate}" filter="url(#${ids.nodeShadow})"></polygon>`);
                    shapes.push(`<circle cx="${layout.approvedEnd.cx}" cy="${layout.approvedEnd.cy}" r="${layout.approvedEnd.r}" fill="#16a34a"></circle>`);
                    shapes.push(`<circle cx="${layout.rejectedEnd.cx}" cy="${layout.rejectedEnd.cy}" r="${layout.rejectedEnd.r}" fill="${COLORS.red}"></circle>`);
                    labels.push(`<text x="${layout.start.cx}" y="${layout.start.cy + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Início</text>`);
                    labels.push(`<text x="${layout.decision.cx}" y="${layout.decision.cy + 4}" fill="#ffffff" text-anchor="middle" font-size="11" font-weight="800">Decisão</text>`);
                    labels.push(this.renderWorkflowSvgBadge('Aprovado', layout.approvedBadge.x, layout.approvedBadge.y, layout.approvedBadge.width, layout.approvedBadge.height, COLORS.green));
                    labels.push(this.renderWorkflowSvgBadge('Recusado', layout.rejectedBadge.x, layout.rejectedBadge.y, layout.rejectedBadge.width, layout.rejectedBadge.height, COLORS.red));
                    labels.push(`<path d="M ${layout.approvedEnd.cx - 8} ${layout.approvedEnd.cy} L ${layout.approvedEnd.cx - 2} ${layout.approvedEnd.cy + 6} L ${layout.approvedEnd.cx + 9} ${layout.approvedEnd.cy - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
                    labels.push(`<text x="${layout.rejectedEnd.cx}" y="${layout.rejectedEnd.cy + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Fim</text>`);
                    labels.push(`<text x="${layout.approvedEnd.cx + 28}" y="${layout.approvedEnd.cy + 6}" fill="${COLORS.green}" font-size="17" font-weight="800">Fim aprovado</text>`);

                    return `
                        <svg class="workflow-board-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Diagrama de aprovação paralela" xmlns="http://www.w3.org/2000/svg">
                            <defs>
                                <marker id="${ids.neutralArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${COLORS.neutral}"></path>
                                </marker>
                                <marker id="${ids.approvedArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${COLORS.green}"></path>
                                </marker>
                                <marker id="${ids.rejectedArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${COLORS.red}"></path>
                                </marker>
                                <filter id="${ids.cardShadow}" x="-10%" y="-10%" width="120%" height="130%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.10"></feDropShadow>
                                </filter>
                                <filter id="${ids.nodeShadow}" x="-20%" y="-20%" width="140%" height="140%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#0f172a" flood-opacity="0.16"></feDropShadow>
                                </filter>
                            </defs>
                            <g font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
                                ${shapes.join('')}
                                ${connectors.join('')}
                                ${labels.join('')}
                            </g>
                        </svg>
                    `;
                },
                getWorkflowDiagramSvg(obra) {
                    const etapas = this.getObraFluxoEtapas(obra);
                    if (!etapas.length) return '';

                    if (String(obra?.workflow_diagram_variant || '').toLowerCase() === 'parallel' || obra?.aprovacao_paralela) {
                        return this.getWorkflowParallelForkJoinDiagramSvg(obra, etapas);
                    }

                    if (String(obra?.workflow_diagram_variant || '').toLowerCase() === 'parallel' || obra?.aprovacao_paralela) {
                        const neutral = '#475569';
                        const green = '#15803d';
                        const red = '#dc2626';
                        const slate = '#64748b';
                        const dark = '#0f172a';
                        const startRadius = 28;
                        const cardWidth = 248;
                        const cardHeight = 112;
                        const topPadding = 56;
                        const laneGap = 108;
                        const width = 1240;
                        const height = Math.max(440, topPadding + (etapas.length * cardHeight) + ((etapas.length - 1) * laneGap) + 220);
                        const startCx = 64;
                        const centerY = height / 2;
                        const cardX = 198;
                        const decisionCx = cardX + cardWidth + 96;
                        const approvedBadgeX = decisionCx + 54;
                        const approvedBadgeWidth = 94;
                        const rejectedBadgeWidth = 96;
                        const approvedTerminalX = width - 140;
                        const approvedMergeX = approvedTerminalX - 36;
                        const approvedAnchorY = Math.max(72, centerY - (((etapas.length - 1) * (cardHeight + laneGap)) / 4));
                        const connectors = [];
                        const shapes = [];
                        const labels = [];

                        connectors.push(this.renderWorkflowSvgPath(
                            `M ${startCx + startRadius} ${centerY} H ${cardX - 34}`,
                            neutral,
                            'workflow-arrow-neutral',
                        ));
                        shapes.push(`<circle cx="${startCx}" cy="${centerY}" r="${startRadius}" fill="${slate}" filter="url(#workflow-node-shadow)"></circle>`);
                        labels.push(`<text x="${startCx}" y="${centerY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Início</text>`);

                        etapas.forEach((etapa, index) => {
                            const cardY = topPadding + (index * (cardHeight + laneGap));
                            const rowY = cardY + (cardHeight / 2);
                            const approvedBadgeY = rowY - 11;
                            const rejectedBadgeX = decisionCx + 18;
                            const rejectedBadgeY = rowY + 44;
                            const rejectedCircleX = rejectedBadgeX + (rejectedBadgeWidth / 2);
                            const rejectedCircleY = rejectedBadgeY + 70;
                            const stageName = normalizeWorkflowStageDisplay(etapa.papel || etapa.nome || `Grupo ${index + 1}`);

                            connectors.push(this.renderWorkflowSvgPath(`M ${cardX - 34} ${centerY} V ${rowY} H ${cardX}`, neutral));
                            connectors.push(this.renderWorkflowSvgPath(`M ${cardX + cardWidth} ${rowY} H ${decisionCx - 42}`, neutral, 'workflow-arrow-neutral'));
                            connectors.push(this.renderWorkflowSvgPath(`M ${decisionCx + 42} ${rowY} H ${approvedBadgeX}`, green));
                            connectors.push(this.renderWorkflowSvgPath(`M ${approvedBadgeX + approvedBadgeWidth} ${rowY} H ${approvedMergeX} V ${approvedAnchorY} H ${approvedTerminalX - 22}`, green, 'workflow-arrow-approved'));
                            connectors.push(this.renderWorkflowSvgPath(`M ${decisionCx} ${rowY + 38} V ${rejectedBadgeY + 11} H ${rejectedCircleX}`, red));
                            connectors.push(this.renderWorkflowSvgPath(`M ${rejectedCircleX} ${rejectedBadgeY + 22} V ${rejectedCircleY - 22}`, red, 'workflow-arrow-rejected'));

                            shapes.push(`<rect x="${cardX}" y="${cardY}" width="${cardWidth}" height="${cardHeight}" rx="8" fill="#ffffff" stroke="#cbd5e1" filter="url(#workflow-card-shadow)"></rect>`);
                            shapes.push(`<polygon points="${decisionCx},${rowY - 38} ${decisionCx + 38},${rowY} ${decisionCx},${rowY + 38} ${decisionCx - 38},${rowY}" fill="${slate}" filter="url(#workflow-node-shadow)"></polygon>`);
                            shapes.push(`<circle cx="${rejectedCircleX}" cy="${rejectedCircleY}" r="21" fill="${red}"></circle>`);
                            labels.push(`<text x="${cardX + 16}" y="${cardY + 28}" fill="#475569" font-size="12" font-weight="800">PAPÉIS</text>`);
                            labels.push(this.renderWorkflowSvgTextLines(
                                wrapWorkflowSvgText(stageName, 22, 3),
                                cardX + 16,
                                cardY + 58,
                                20,
                                `fill="${dark}" font-size="15" font-weight="800"`,
                            ));
                            labels.push(`<text x="${decisionCx}" y="${rowY + 4}" fill="#ffffff" text-anchor="middle" font-size="11" font-weight="800">Decisão</text>`);
                            labels.push(this.renderWorkflowSvgBadge('Aprovado', approvedBadgeX, approvedBadgeY, approvedBadgeWidth, 22, green));
                            labels.push(this.renderWorkflowSvgBadge('Recusado', rejectedBadgeX, rejectedBadgeY, rejectedBadgeWidth, 22, red));
                            labels.push(`<text x="${rejectedCircleX}" y="${rejectedCircleY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Fim</text>`);
                        });

                        shapes.push(`<circle cx="${approvedTerminalX}" cy="${approvedAnchorY}" r="18" fill="#16a34a"></circle>`);
                        labels.push(`<path d="M ${approvedTerminalX - 8} ${approvedAnchorY} L ${approvedTerminalX - 2} ${approvedAnchorY + 6} L ${approvedTerminalX + 9} ${approvedAnchorY - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
                        labels.push(`<text x="${approvedTerminalX + 28}" y="${approvedAnchorY + 6}" fill="${green}" font-size="17" font-weight="800">Fim aprovado</text>`);

                        return `
                            <svg class="workflow-board-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Diagrama de aprovação paralela" xmlns="http://www.w3.org/2000/svg">
                                <defs>
                                    <marker id="workflow-arrow-neutral" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                        <path d="M 0 0 L 8 4 L 0 8 z" fill="${neutral}"></path>
                                    </marker>
                                    <marker id="workflow-arrow-approved" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                        <path d="M 0 0 L 8 4 L 0 8 z" fill="${green}"></path>
                                    </marker>
                                    <marker id="workflow-arrow-rejected" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                        <path d="M 0 0 L 8 4 L 0 8 z" fill="${red}"></path>
                                    </marker>
                                    <filter id="workflow-card-shadow" x="-10%" y="-10%" width="120%" height="130%">
                                        <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.10"></feDropShadow>
                                    </filter>
                                    <filter id="workflow-node-shadow" x="-20%" y="-20%" width="140%" height="140%">
                                        <feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#0f172a" flood-opacity="0.16"></feDropShadow>
                                    </filter>
                                </defs>
                                <g font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
                                    ${shapes.join('')}
                                    ${connectors.join('')}
                                    ${labels.join('')}
                                </g>
                            </svg>
                        `;
                    }

                    const layout = this.getWorkflowDiagramLayout(etapas.length);
                    const neutral = '#475569';
                    const green = '#15803d';
                    const red = '#dc2626';
                    const slate = '#64748b';
                    const dark = '#0f172a';
                    const stagePositions = etapas.map((_, index) => this.getWorkflowDiagramStagePosition(index, layout));
                    const connectors = [];
                    const shapes = [];
                    const labels = [];
                    const svgId = `workflow-sequential-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
                    const ids = {
                        neutralArrow: `${svgId}-arrow-neutral`,
                        approvedArrow: `${svgId}-arrow-approved`,
                        rejectedArrow: `${svgId}-arrow-rejected`,
                        cardShadow: `${svgId}-card-shadow`,
                        nodeShadow: `${svgId}-node-shadow`,
                    };

                    connectors.push(this.renderWorkflowSvgPath(
                        `M ${layout.startCx + layout.startR} ${layout.firstRowY} H ${stagePositions[0].cardX}`,
                        neutral,
                        ids.neutralArrow,
                    ));
                    shapes.push(`<circle cx="${layout.startCx}" cy="${layout.firstRowY}" r="${layout.startR}" fill="${slate}" filter="url(#${ids.nodeShadow})"></circle>`);
                    labels.push(`<text x="${layout.startCx}" y="${layout.firstRowY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Início</text>`);

                    etapas.forEach((etapa, index) => {
                        const stage = stagePositions[index];
                        const isLast = index === etapas.length - 1;
                        const cardRight = stage.cardX + layout.cardW;
                        const decisionLeft = stage.decisionCx - layout.diamondHalf;
                        const decisionRight = stage.decisionCx + layout.diamondHalf;
                        const decisionBottom = stage.decisionCy + layout.diamondHalf;
                        const approvedBadgeRight = stage.approvedBadgeX + layout.badgeW;
                        const rejectedBadgeX = stage.decisionCx - (layout.rejectedBadgeW / 2);
                        const rejectedBadgeY = decisionBottom + 16;
                        const rejectedCircleY = rejectedBadgeY + layout.badgeH + 54;
                        const stageName = normalizeWorkflowStageDisplay(etapa.papel || etapa.nome || 'Responsável');

                        connectors.push(this.renderWorkflowSvgPath(`M ${cardRight} ${stage.rowY} H ${decisionLeft}`, neutral, ids.neutralArrow));
                        connectors.push(this.renderWorkflowSvgPath(`M ${decisionRight} ${stage.rowY} H ${stage.approvedBadgeX}`, green));
                        connectors.push(this.renderWorkflowSvgPath(`M ${stage.decisionCx} ${decisionBottom} V ${rejectedBadgeY}`, red));
                        connectors.push(this.renderWorkflowSvgPath(`M ${stage.decisionCx} ${rejectedBadgeY + layout.badgeH} V ${rejectedCircleY - 22}`, red, ids.rejectedArrow));

                        if (!isLast) {
                            const nextStage = stagePositions[index + 1];
                            connectors.push(this.renderWorkflowSvgPath(
                                this.getWorkflowApprovedConnectorPath(stage, nextStage, layout),
                                green,
                                ids.approvedArrow,
                            ));
                        } else {
                            const finalCircleX = approvedBadgeRight + 76;
                            const finalCircleY = stage.rowY;
                            connectors.push(this.renderWorkflowSvgPath(`M ${approvedBadgeRight} ${stage.rowY} H ${finalCircleX - 24}`, green, ids.approvedArrow));
                            shapes.push(`<circle cx="${finalCircleX}" cy="${finalCircleY}" r="18" fill="#16a34a"></circle>`);
                            labels.push(`<path d="M ${finalCircleX - 8} ${finalCircleY} L ${finalCircleX - 2} ${finalCircleY + 6} L ${finalCircleX + 9} ${finalCircleY - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
                            labels.push(`<text x="${finalCircleX + 28}" y="${finalCircleY + 6}" fill="${green}" font-size="17" font-weight="800">Fim aprovado</text>`);
                        }

                        shapes.push(`<rect x="${stage.cardX}" y="${stage.cardY}" width="${layout.cardW}" height="${layout.cardH}" rx="8" fill="#ffffff" stroke="#cbd5e1" filter="url(#${ids.cardShadow})"></rect>`);
                        shapes.push(`<polygon points="${stage.decisionCx},${stage.decisionCy - layout.diamondHalf} ${stage.decisionCx + layout.diamondHalf},${stage.decisionCy} ${stage.decisionCx},${stage.decisionCy + layout.diamondHalf} ${stage.decisionCx - layout.diamondHalf},${stage.decisionCy}" fill="${slate}" filter="url(#${ids.nodeShadow})"></polygon>`);
                        shapes.push(`<circle cx="${stage.decisionCx}" cy="${rejectedCircleY}" r="21" fill="${red}"></circle>`);
                        labels.push(`<text x="${stage.cardX + 16}" y="${stage.cardY + 30}" fill="#475569" font-size="12" font-weight="800">${escapeSvgText(etapa.rotulo || `Etapa ${etapa.nivel || index + 1}`).toUpperCase()}</text>`);
                        labels.push(this.renderWorkflowSvgRoleTextLines(
                            wrapWorkflowSvgRoleTokenLines(stageName, 17, 4),
                            stage.cardX + 16,
                            stage.cardY + 62,
                            22,
                            dark,
                            17,
                            {
                                id: `${svgId}-stage-${index}-text-clip`,
                                width: layout.cardW - 32,
                                height: layout.cardH - 66,
                                y: stage.cardY + 44,
                            },
                        ));
                        labels.push(`<text x="${stage.decisionCx}" y="${stage.decisionCy + 4}" fill="#ffffff" text-anchor="middle" font-size="11" font-weight="800">Decisão</text>`);
                        labels.push(this.renderWorkflowSvgBadge('Aprovado', stage.approvedBadgeX, stage.approvedBadgeY, layout.badgeW, layout.badgeH, green));
                        labels.push(this.renderWorkflowSvgBadge('Recusado', rejectedBadgeX, rejectedBadgeY, layout.rejectedBadgeW, layout.badgeH, red));
                        labels.push(`<text x="${stage.decisionCx}" y="${rejectedCircleY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Fim</text>`);
                    });

                    return `
                        <svg class="workflow-board-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" role="img" aria-label="Diagrama de aprovação" xmlns="http://www.w3.org/2000/svg">
                            <defs>
                                <marker id="${ids.neutralArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${neutral}"></path>
                                </marker>
                                <marker id="${ids.approvedArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${green}"></path>
                                </marker>
                                <marker id="${ids.rejectedArrow}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                                    <path d="M 0 0 L 8 4 L 0 8 z" fill="${red}"></path>
                                </marker>
                                <filter id="${ids.cardShadow}" x="-10%" y="-10%" width="120%" height="130%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.10"></feDropShadow>
                                </filter>
                                <filter id="${ids.nodeShadow}" x="-20%" y="-20%" width="140%" height="140%">
                                    <feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#0f172a" flood-opacity="0.16"></feDropShadow>
                                </filter>
                            </defs>
                            <g font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
                                ${shapes.join('')}
                                ${connectors.join('')}
                                ${labels.join('')}
                            </g>
                        </svg>
                    `;
                },
                getSafeWorkflowDiagramSvg(obra) {
                    return sanitizeSvgMarkup(this.getWorkflowDiagramSvg(obra));
                },
                formatWorkflowStageName(value) {
                    return normalizeWorkflowStageDisplay(value);
                },
                isUltimaEtapaFluxo(obra, index) {
                    return index === this.getObraFluxoEtapas(obra).length - 1;
                },
                getFluxoAprovadoDestino(obra, index) {
                    return this.isUltimaEtapaFluxo(obra, index) ? 'Fim aprovado' : 'Próxima aprovação';
                },
            };
        }
        window.empresaApp = empresaApp;

        let empresaWorkflowState = {
            selectedWorkflowId: empresaWorkflowDefaultId,
            selectedWorkflowModel: 'simples',
            preview: null,
            customStages: [],
            globalSignature: false,
            globalRule: 'TODOS',
            dirty: false,
            collapsedGroups: {},
            diagramZoom: 1,
            diagramDragging: null,
        };

        function workflowEl(id) {
            return document.getElementById(id);
        }

        function getEmpresaWorkflowDiagramPayload() {
            const rules = getEmpresaWorkflowRules();
            return {
                workflow_etapas: getEmpresaWorkflowDiagramEtapas(),
                workflow_diagram_variant: rules.isParallel ? 'parallel' : 'default',
                aprovacao_paralela: rules.isParallel,
                regra_etapa: 'TODOS',
            };
        }

        function getEmpresaWorkflowDiagramBaseSize() {
            const payload = getEmpresaWorkflowDiagramPayload();
            try {
                return window.empresaApp().getWorkflowDiagramBaseSize(payload);
            } catch (_) {
                return { width: 960, height: 420 };
            }
        }

        function syncEmpresaWorkflowDiagramViewport() {
            const diagramEl = workflowEl('workflowCompanyDiagram');
            const labelEl = workflowEl('workflowCompanyDiagramZoomReset');
            const zoom = Math.min(2, Math.max(0.5, Number(empresaWorkflowState.diagramZoom || 1)));
            empresaWorkflowState.diagramZoom = Math.round(zoom * 10) / 10;

            if (labelEl) {
                labelEl.textContent = `${Math.round(empresaWorkflowState.diagramZoom * 100)}%`;
            }

            if (!diagramEl) return;
            const baseSize = getEmpresaWorkflowDiagramBaseSize();
            const width = Math.round(baseSize.width * empresaWorkflowState.diagramZoom);
            const height = Math.round(baseSize.height * empresaWorkflowState.diagramZoom);
            diagramEl.style.width = `${width}px`;
            diagramEl.style.minWidth = `${width}px`;
            diagramEl.style.height = `${height}px`;
            diagramEl.style.minHeight = `${height}px`;
        }

        function setEmpresaWorkflowDiagramZoom(value) {
            empresaWorkflowState.diagramZoom = Math.min(2, Math.max(0.5, Math.round(Number(value || 1) * 10) / 10));
            syncEmpresaWorkflowDiagramViewport();
            return empresaWorkflowState.diagramZoom;
        }

        function alterarEmpresaWorkflowDiagramZoom(delta) {
            return setEmpresaWorkflowDiagramZoom(Number(empresaWorkflowState.diagramZoom || 1) + Number(delta || 0));
        }

        function resetEmpresaWorkflowDiagramZoom() {
            setEmpresaWorkflowDiagramZoom(1);
        }

        function zoomEmpresaWorkflowDiagramPorWheel(event) {
            if (!event || !event.currentTarget || !event.ctrlKey) return;
            event.preventDefault();
            event.stopPropagation();

            const canvas = event.currentTarget;
            const currentZoom = Math.min(2, Math.max(0.5, Number(empresaWorkflowState.diagramZoom || 1)));
            const rect = canvas.getBoundingClientRect();
            const offsetX = event.clientX - rect.left;
            const offsetY = event.clientY - rect.top;
            const anchorX = canvas.scrollLeft + offsetX;
            const anchorY = canvas.scrollTop + offsetY;
            const nextZoom = alterarEmpresaWorkflowDiagramZoom(event.deltaY < 0 ? 0.1 : -0.1);

            if (nextZoom === currentZoom) return;

            window.requestAnimationFrame(() => {
                const ratio = nextZoom / currentZoom;
                canvas.scrollLeft = (anchorX * ratio) - offsetX;
                canvas.scrollTop = (anchorY * ratio) - offsetY;
            });
        }

        function iniciarArrasteEmpresaWorkflowDiagram(event) {
            if (!event || !event.currentTarget || event.button !== 0) return;

            event.preventDefault();
            const canvas = event.currentTarget;
            if (typeof canvas.setPointerCapture === 'function' && event.pointerId != null) {
                canvas.setPointerCapture(event.pointerId);
            }
            empresaWorkflowState.diagramDragging = {
                canvas,
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                scrollLeft: canvas.scrollLeft,
                scrollTop: canvas.scrollTop,
            };
            canvas.classList.add('workflow-canvas--dragging');
        }

        function arrastarEmpresaWorkflowDiagram(event) {
            const drag = empresaWorkflowState.diagramDragging;
            if (!drag || !drag.canvas || !event) return;
            if (event.buttons !== 1) {
                encerrarArrasteEmpresaWorkflowDiagram();
                return;
            }

            event.preventDefault();
            drag.canvas.scrollLeft = drag.scrollLeft - (event.clientX - drag.startX);
            drag.canvas.scrollTop = drag.scrollTop - (event.clientY - drag.startY);
        }

        function encerrarArrasteEmpresaWorkflowDiagram() {
            const drag = empresaWorkflowState.diagramDragging;
            if (drag?.canvas) {
                const { canvas, pointerId } = drag;
                if (typeof canvas.releasePointerCapture === 'function' && pointerId != null && canvas.hasPointerCapture?.(pointerId)) {
                    canvas.releasePointerCapture(pointerId);
                }
                canvas.classList.remove('workflow-canvas--dragging');
            }
            empresaWorkflowState.diagramDragging = null;
        }

        function getEmpresaRoot() {
            return document.getElementById('empresaPageRoot');
        }

        function setEmpresaEditingDataset(value) {
            const root = getEmpresaRoot();
            if (root) root.dataset.empresaEditing = value ? 'true' : 'false';
        }

        function getEmpresaAppState() {
            const root = getEmpresaRoot();
            if (!root) return null;
            if (window.Alpine?.$data) {
                try {
                    const data = window.Alpine.$data(root);
                    if (data) return data;
                } catch (_) { }
            }
            return root.__x?.$data || root._x_dataStack?.[0] || null;
        }

        function isEmpresaWorkflowEditing() {
            const state = getEmpresaAppState();
            if (state && typeof state.empresaEditing !== 'undefined') {
                return Boolean(state.empresaEditing);
            }
            const attr = getEmpresaRoot()?.dataset?.empresaEditing;
            if (typeof attr !== 'undefined') return attr === 'true';
            return Boolean(pageData.startInEditMode);
        }

        function escapeEmpresaWorkflowHtml(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function getEmpresaWorkflowDropdownWrapper(element) {
            return element?.closest?.('[data-workflow-custom-dropdown]') || null;
        }

        let activeEmpresaWorkflowDropdown = null;
        let empresaWorkflowDropdownIdCounter = 0;

        function getEmpresaWorkflowDropdownParts(wrapper) {
            return {
                select: wrapper?.querySelector?.('select') || null,
                button: wrapper?.querySelector?.('[data-workflow-dropdown-button]') || null,
                menu: wrapper?.querySelector?.('[data-workflow-dropdown-menu], #workflowCompanyTypeDropdownMenu') || null,
                options: Array.from(wrapper?.querySelectorAll?.('[data-workflow-dropdown-option]') || []),
            };
        }

        function ensureEmpresaWorkflowDropdownA11y(wrapper) {
            if (!wrapper) return;
            const { button, menu, options } = getEmpresaWorkflowDropdownParts(wrapper);
            if (!button || !menu) return;
            if (!menu.id) {
                empresaWorkflowDropdownIdCounter += 1;
                menu.id = `empresa-workflow-dropdown-menu-${empresaWorkflowDropdownIdCounter}`;
            }
            button.setAttribute('aria-haspopup', 'listbox');
            button.setAttribute('aria-controls', menu.id);
            button.setAttribute('aria-expanded', menu.classList.contains('hidden') ? 'false' : 'true');
            menu.setAttribute('role', 'listbox');
            options.forEach((option) => {
                option.setAttribute('role', 'option');
                option.setAttribute('tabindex', '-1');
            });
        }

        function setEmpresaWorkflowDropdownExpanded(wrapper, expanded) {
            const { button } = getEmpresaWorkflowDropdownParts(wrapper);
            button?.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        }

        function focusEmpresaWorkflowDropdownOption(wrapper, direction) {
            const { select, options } = getEmpresaWorkflowDropdownParts(wrapper);
            if (!options.length) return;
            const activeElement = document.activeElement;
            const currentIndex = options.includes(activeElement)
                ? options.indexOf(activeElement)
                : Math.max(0, options.findIndex((option) => String(option.dataset.value ?? '') === String(select?.value ?? '')));
            let nextIndex = currentIndex;
            if (direction === 'first') nextIndex = 0;
            else if (direction === 'last') nextIndex = options.length - 1;
            else if (direction === 'previous') nextIndex = (currentIndex - 1 + options.length) % options.length;
            else if (direction === 'next') nextIndex = (currentIndex + 1) % options.length;
            options[nextIndex]?.focus({ preventScroll: true });
        }

        function resetEmpresaWorkflowDropdownMenu(menu) {
            if (!menu) return;
            menu.classList.add('hidden');
            menu.style.position = '';
            menu.style.left = '';
            menu.style.top = '';
            menu.style.width = '';
            menu.style.maxHeight = '';
            menu.style.zIndex = '';
            setEmpresaWorkflowDropdownExpanded(getEmpresaWorkflowDropdownWrapper(menu), false);
        }

        function restoreEmpresaWorkflowDropdownMenu() {
            if (!activeEmpresaWorkflowDropdown) return;
            const { wrapper, menu } = activeEmpresaWorkflowDropdown;
            resetEmpresaWorkflowDropdownMenu(menu);
            if (wrapper && menu && !wrapper.contains(menu)) {
                wrapper.appendChild(menu);
            }
            setEmpresaWorkflowDropdownExpanded(wrapper, false);
            activeEmpresaWorkflowDropdown = null;
        }

        function positionEmpresaWorkflowDropdownMenu(wrapper, menu) {
            const button = wrapper.querySelector('[data-workflow-dropdown-button]');
            if (!button || !menu) return;
            const rect = button.getBoundingClientRect();
            const gap = 6;
            const viewportPadding = 12;
            const availableBelow = window.innerHeight - rect.bottom - gap - viewportPadding;
            const availableAbove = rect.top - gap - viewportPadding;
            const openUp = availableBelow < 220 && availableAbove > availableBelow;
            const maxHeight = Math.max(180, Math.min(288, openUp ? availableAbove : availableBelow));

            menu.style.position = 'fixed';
            menu.style.left = `${rect.left}px`;
            menu.style.top = `${openUp ? Math.max(viewportPadding, rect.top - gap - maxHeight) : rect.bottom + gap}px`;
            menu.style.width = `${rect.width}px`;
            menu.style.maxHeight = `${maxHeight}px`;
            menu.style.zIndex = '99999';
            menu.classList.add('overflow-y-auto');
            menu.classList.remove('hidden');
            setEmpresaWorkflowDropdownExpanded(wrapper, true);
        }

        function closeEmpresaWorkflowDropdowns(exceptWrapper = null) {
            const activeWrapper = activeEmpresaWorkflowDropdown?.wrapper || null;
            if (!exceptWrapper || activeWrapper !== exceptWrapper) {
                restoreEmpresaWorkflowDropdownMenu();
            }
            document.querySelectorAll('[data-workflow-custom-dropdown]').forEach((wrapper) => {
                if (exceptWrapper && wrapper === exceptWrapper) return;
                resetEmpresaWorkflowDropdownMenu(wrapper.querySelector('[data-workflow-dropdown-menu], #workflowCompanyTypeDropdownMenu'));
            });
        }

        function closeEmpresaWorkflowTypeDropdown() {
            closeEmpresaWorkflowDropdowns();
        }

        function getEmpresaWorkflowDropdownLabel(select) {
            const selectedOption = select?.selectedOptions?.[0];
            if (selectedOption) return selectedOption.textContent.trim();
            return select?.querySelector('option')?.textContent.trim() || 'Selecione';
        }

        function syncEmpresaWorkflowDropdown(wrapper) {
            if (!wrapper) return;
            const select = wrapper.querySelector('select');
            if (!select) return;

            const value = String(select.value ?? '');
            const label = wrapper.querySelector('[data-workflow-dropdown-label], #workflowCompanyTypeDropdownLabel');
            if (label) label.textContent = getEmpresaWorkflowDropdownLabel(select);
            ensureEmpresaWorkflowDropdownA11y(wrapper);

            wrapper.querySelectorAll('[data-workflow-dropdown-option]').forEach((option) => {
                const isActive = String(option.dataset.value ?? '') === value;
                option.classList.toggle('bg-blue-50', isActive);
                option.classList.toggle('text-blue-700', isActive);
                option.setAttribute('aria-selected', isActive ? 'true' : 'false');
                option.querySelector('[data-workflow-dropdown-check], .workflow-company-type-check')?.classList.toggle('hidden', !isActive);
            });
        }

        function syncEmpresaWorkflowDropdowns(context = document) {
            const root = context && context.querySelectorAll ? context : document;
            if (root.matches?.('[data-workflow-custom-dropdown]')) syncEmpresaWorkflowDropdown(root);
            root.querySelectorAll?.('[data-workflow-custom-dropdown]').forEach(syncEmpresaWorkflowDropdown);
        }

        function canOpenEmpresaWorkflowDropdown(wrapper) {
            return wrapper?.dataset.workflowDropdownMode !== 'edit' || isEmpresaWorkflowEditing();
        }

        function toggleEmpresaWorkflowDropdown(wrapper) {
            if (!wrapper || !canOpenEmpresaWorkflowDropdown(wrapper)) return;
            const menu = wrapper.querySelector('[data-workflow-dropdown-menu], #workflowCompanyTypeDropdownMenu');
            if (!menu) return;
            const shouldOpen = menu.classList.contains('hidden');
            closeEmpresaWorkflowDropdowns(wrapper);
            if (!shouldOpen) {
                restoreEmpresaWorkflowDropdownMenu();
                return;
            }
            syncEmpresaWorkflowDropdown(wrapper);
            activeEmpresaWorkflowDropdown = { wrapper, menu };
            document.body.appendChild(menu);
            positionEmpresaWorkflowDropdownMenu(wrapper, menu);
            ensureEmpresaWorkflowDropdownA11y(wrapper);
            focusEmpresaWorkflowDropdownOption(wrapper, 'current');
        }

        function selectEmpresaWorkflowDropdownOption(option) {
            const wrapper = getEmpresaWorkflowDropdownWrapper(option) || activeEmpresaWorkflowDropdown?.wrapper;
            if (!wrapper || !canOpenEmpresaWorkflowDropdown(wrapper)) return;
            const select = wrapper.querySelector('select');
            if (!select) return;
            select.value = String(option.dataset.value ?? '');
            syncEmpresaWorkflowDropdown(wrapper);
            closeEmpresaWorkflowDropdowns();
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function setEmpresaWorkflowSelectValue(select, value) {
            if (!select) return;
            const normalizedValue = String(value);
            select.value = normalizedValue;
            syncEmpresaWorkflowDropdown(getEmpresaWorkflowDropdownWrapper(select));
        }

        function syncEmpresaStatusFilterPickers(value) {
            const normalizedValue = value == null ? '' : String(value);
            document.querySelectorAll('select[x-model="filtroStatus"]').forEach((select) => {
                select.value = normalizedValue;
                syncEmpresaWorkflowDropdown(getEmpresaWorkflowDropdownWrapper(select));
            });
        }

        function getEmpresaWorkflowPreview(workflowId) {
            return empresaWorkflowPreviewById[String(workflowId)] || null;
        }

        function getEmpresaWorkflowPreviewByModel(model) {
            const previews = Object.values(empresaWorkflowPreviewById || {});
            return previews.find((preview) => getEmpresaWorkflowModelKind(preview) === model) || previews[0] || null;
        }

        function getEmpresaWorkflowRoleById(papelId) {
            return empresaWorkflowRoleOptions.find((papel) => Number(papel.id) === Number(papelId)) || null;
        }

        function getEmpresaWorkflowStageKey(stage, index = 0) {
            return String(stage?.local_id || stage?.etapa_id || `empresa-stage-${index}`);
        }

        function findEmpresaWorkflowStageIndex(stageKey, fallbackIndex = null) {
            const stages = empresaWorkflowState.customStages || [];
            const normalizedKey = String(stageKey || '');
            if (normalizedKey) {
                const stableIndex = stages.findIndex((stage, index) => getEmpresaWorkflowStageKey(stage, index) === normalizedKey);
                if (stableIndex >= 0) return stableIndex;
            }
            const numericIndex = Number(fallbackIndex);
            return Number.isInteger(numericIndex) && numericIndex >= 0 && numericIndex < stages.length ? numericIndex : -1;
        }

        function getEmpresaWorkflowModelKind(preview) {
            const tipo = String(preview?.tipo_fluxo || '').toUpperCase();
            const nome = String(preview?.workflow_nome || '').toLowerCase();
            if (preview?.aprovacao_paralela || tipo === 'PARALELO') return 'paralelo';
            if (['SEQUENCIAL', 'HIERARQUICO', 'HIERARQUICA'].includes(tipo) || nome.includes('hierar')) return 'hierarquico';
            return 'simples';
        }

        function getEmpresaWorkflowRules() {
            const tipo = String(empresaWorkflowState.selectedWorkflowModel || 'simples').toLowerCase();
            return {
                tipo,
                isSimple: tipo === 'simples',
                isSequential: tipo === 'hierarquico',
                isParallel: tipo === 'paralelo',
                canAddStages: tipo === 'hierarquico',
                canDragStages: tipo === 'hierarquico',
            };
        }

        function cloneEmpresaWorkflowStage(stage, index) {
            return {
                local_id: stage.local_id || `empresa-stage-${Date.now()}-${index}-${Math.random().toString(16).slice(2, 8)}`,
                etapa_id: stage.etapa_id || null,
                nivel: index + 1,
                nome: stage.nome || `Etapa ${index + 1}`,
                tipo_aprovador: 'PAPEL',
                papel_id: stage.papel_id || '',
                workflow_group: String(stage.workflow_group || stage.grupo_visual || stage.grupo_paralelo || stage.nivel || index + 1),
                grupo_paralelo: stage.grupo_paralelo || null,
                regra_aprovacao: normalizeEmpresaWorkflowGroupRule(stage.regra_aprovacao || stage.regra_etapa || 'TODOS'),
            };
        }

        function normalizeEmpresaWorkflowGroupRule(value) {
            const normalized = String(value || 'TODOS').trim().toUpperCase();
            return ['QUALQUER', 'PRIMEIRO', 'OU'].includes(normalized) ? 'QUALQUER' : 'TODOS';
        }

        function getEmpresaWorkflowStageGroupKey(stage, index) {
            if (getEmpresaWorkflowRules().isSimple) return '1';
            return String(stage.workflow_group || stage.grupo_visual || stage.grupo_paralelo || stage.nivel || index + 1);
        }

        function getEmpresaWorkflowVisualGroups() {
            const groupsMap = new Map();
            (empresaWorkflowState.customStages || []).forEach((stage, index) => {
                const key = getEmpresaWorkflowStageGroupKey(stage, index);
                if (!groupsMap.has(key)) groupsMap.set(key, { key, items: [] });
                groupsMap.get(key).items.push({ stage, index });
            });
            return Array.from(groupsMap.values()).sort((a, b) => Number(a.key) - Number(b.key));
        }

        function getEmpresaWorkflowGroupRule(group) {
            const firstStage = group?.items?.[0]?.stage || null;
            return normalizeEmpresaWorkflowGroupRule(firstStage?.regra_aprovacao || firstStage?.regra_etapa || 'TODOS');
        }

        function setEmpresaWorkflowGroupRule(groupKey, value) {
            const normalizedRule = normalizeEmpresaWorkflowGroupRule(value);
            (empresaWorkflowState.customStages || []).forEach((stage, index) => {
                if (getEmpresaWorkflowStageGroupKey(stage, index) === String(groupKey)) {
                    stage.regra_aprovacao = normalizedRule;
                    stage.regra_etapa = normalizedRule;
                }
            });
        }

        function getEmpresaWorkflowTypeLabel() {
            const rules = getEmpresaWorkflowRules();
            if (rules.isParallel) return 'Aprovação paralela';
            if (rules.isSequential) return 'Aprovação hierárquica';
            return 'Aprovação simples';
        }

        function getEmpresaWorkflowRuleLabel() {
            return 'Entre grupos/etapas: E';
        }

        function joinEmpresaWorkflowDiagramApprovers(papeis, regra) {
            const labels = (Array.isArray(papeis) ? papeis : [])
                .map((papel) => normalizeWorkflowStageDisplay(papel))
                .filter(Boolean);
            if (!labels.length) return 'Papel nao definido';
            if (labels.length === 1) return labels[0];
            const connector = normalizeEmpresaWorkflowGroupRule(regra) === 'QUALQUER' ? ' ou ' : ' e ';
            return `${labels.slice(0, -1).join(connector)}${connector}${labels[labels.length - 1]}`;
        }

        function getEmpresaWorkflowDiagramEtapas() {
            const rules = getEmpresaWorkflowRules();
            return getEmpresaWorkflowVisualGroups().map((group, groupIndex) => {
                const regra = getEmpresaWorkflowGroupRule(group);
                const papeis = group.items
                    .map(({ stage }) => getEmpresaWorkflowRoleById(stage.papel_id)?.nome || stage.nome || 'Papel não definido')
                    .filter(Boolean);
                const nome = joinEmpresaWorkflowDiagramApprovers(papeis, regra);
                const entityLabel = rules.isParallel ? 'Grupo' : 'Etapa';
                return {
                    nivel: groupIndex + 1,
                    nome,
                    papel: nome,
                    rotulo: `${entityLabel} ${groupIndex + 1}`,
                    regra_aprovacao: regra,
                    regra_etapa: regra,
                };
            });
        }

        function renderEmpresaWorkflowParallelDiagram(etapas) {
            const cardWidth = 240;
            const cardHeight = 96;
            const laneGap = 44;
            const startRadius = 26;
            const topPadding = 48;
            const leftPadding = 84;
            const width = 980;
            const height = Math.max(240, topPadding * 2 + (etapas.length * cardHeight) + ((etapas.length - 1) * laneGap));
            const startX = leftPadding;
            const firstCardX = 170;
            const decisionCx = firstCardX + cardWidth + 84;
            const endX = decisionCx + 302;
            const neutral = '#475569';
            const green = '#15803d';
            const dark = '#0f172a';
            const slate = '#64748b';

            const connectors = [];
            const shapes = [];
            const labels = [];
            const centerY = height / 2;

            connectors.push(`<path d="M ${startX + startRadius} ${centerY} H ${firstCardX - 24}" fill="none" stroke="${neutral}" stroke-width="2" stroke-linecap="round" marker-end="url(#workflow-parallel-arrow)"></path>`);
            shapes.push(`<circle cx="${startX}" cy="${centerY}" r="${startRadius}" fill="${slate}"></circle>`);
            labels.push(`<text x="${startX}" y="${centerY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Início</text>`);

            etapas.forEach((etapa, index) => {
                const cardY = topPadding + (index * (cardHeight + laneGap));
                const rowCenterY = cardY + (cardHeight / 2);
                const badgeX = decisionCx + 28;
                const badgeY = rowCenterY - 11;
                const stageName = normalizeWorkflowStageDisplay(etapa.papel || etapa.nome || `Grupo ${index + 1}`);

                connectors.push(`<path d="M ${firstCardX - 24} ${centerY} V ${rowCenterY} H ${firstCardX}" fill="none" stroke="${neutral}" stroke-width="2" stroke-linecap="round"></path>`);
                connectors.push(`<path d="M ${firstCardX + cardWidth} ${rowCenterY} H ${decisionCx - 42}" fill="none" stroke="${neutral}" stroke-width="2" stroke-linecap="round" marker-end="url(#workflow-parallel-arrow)"></path>`);
                connectors.push(`<path d="M ${decisionCx + 42} ${rowCenterY} H ${badgeX}" fill="none" stroke="${green}" stroke-width="2" stroke-linecap="round"></path>`);
                connectors.push(`<path d="M ${badgeX + 94} ${rowCenterY} H ${endX - 18}" fill="none" stroke="${green}" stroke-width="2" stroke-linecap="round" marker-end="url(#workflow-parallel-arrow-approved)"></path>`);

                shapes.push(`<rect x="${firstCardX}" y="${cardY}" width="${cardWidth}" height="${cardHeight}" rx="10" fill="#ffffff" stroke="#cbd5e1"></rect>`);
                shapes.push(`<polygon points="${decisionCx},${rowCenterY - 32} ${decisionCx + 32},${rowCenterY} ${decisionCx},${rowCenterY + 32} ${decisionCx - 32},${rowCenterY}" fill="${slate}"></polygon>`);
                shapes.push(`<rect x="${badgeX}" y="${badgeY}" width="94" height="22" rx="11" fill="#ffffff" stroke="${green}" stroke-width="1.4"></rect>`);

                labels.push(`<text x="${firstCardX + 16}" y="${cardY + 28}" fill="#475569" font-size="12" font-weight="800">GRUPO ${index + 1}</text>`);
                labels.push(window.empresaApp().renderWorkflowSvgTextLines(
                    wrapWorkflowSvgText(stageName, 22, 2),
                    firstCardX + 16,
                    cardY + 56,
                    20,
                    `fill="${dark}" font-size="15" font-weight="800"`
                ));
                labels.push(`<text x="${decisionCx}" y="${rowCenterY + 4}" fill="#ffffff" text-anchor="middle" font-size="11" font-weight="800">Decisão</text>`);
                labels.push(`<text x="${badgeX + 47}" y="${rowCenterY + 4}" fill="${green}" text-anchor="middle" font-size="10" font-weight="800">APROVADO</text>`);
            });

            shapes.push(`<circle cx="${endX}" cy="${centerY}" r="18" fill="#16a34a"></circle>`);
            labels.push(`<path d="M ${endX - 8} ${centerY} L ${endX - 2} ${centerY + 6} L ${endX + 9} ${centerY - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
            labels.push(`<text x="${endX + 28}" y="${centerY + 6}" fill="${green}" font-size="17" font-weight="800">Fim aprovado</text>`);

            return `
                <svg class="workflow-board-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Diagrama de aprovação paralela" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <marker id="workflow-parallel-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                            <path d="M 0 0 L 8 4 L 0 8 z" fill="${neutral}"></path>
                        </marker>
                        <marker id="workflow-parallel-arrow-approved" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                            <path d="M 0 0 L 8 4 L 0 8 z" fill="${green}"></path>
                        </marker>
                    </defs>
                    <g font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
                        ${shapes.join('')}
                        ${connectors.join('')}
                        ${labels.join('')}
                    </g>
                </svg>
            `;
        }

        function renderEmpresaWorkflowDiagramPreview() {
            const countEl = workflowEl('workflowCompanyOverviewCount');
            const diagramEl = workflowEl('workflowCompanyDiagram');
            const emptyEl = workflowEl('workflowCompanyDiagramEmpty');
            const etapas = getEmpresaWorkflowDiagramEtapas();
            const rules = getEmpresaWorkflowRules();

            if (countEl) {
                countEl.textContent = `${etapas.length} ${etapas.length === 1 ? 'etapa' : 'etapas'}`;
            }

            if (!diagramEl || !emptyEl) return;

            if (!etapas.length) {
                diagramEl.innerHTML = '';
                diagramEl.removeAttribute('style');
                emptyEl.classList.remove('hidden');
                syncEmpresaWorkflowDiagramViewport();
                return;
            }

            emptyEl.classList.add('hidden');
            diagramEl.innerHTML = window.empresaApp().getSafeWorkflowDiagramSvg(getEmpresaWorkflowDiagramPayload());
            syncEmpresaWorkflowDiagramViewport();
        }

        function isEmpresaWorkflowGroupCollapsed(groupKey) {
            return Boolean(empresaWorkflowState.collapsedGroups?.[String(groupKey)]);
        }

        function toggleEmpresaWorkflowGroupCollapsed(groupKey) {
            const key = String(groupKey);
            empresaWorkflowState.collapsedGroups = {
                ...(empresaWorkflowState.collapsedGroups || {}),
                [key]: !empresaWorkflowState.collapsedGroups?.[key],
            };
            renderEmpresaWorkflowCards();
        }

        function normalizeEmpresaWorkflowStagesOrder() {
            const rules = getEmpresaWorkflowRules();
            let stages = empresaWorkflowState.customStages || [];
            if (rules.isSimple) stages = stages.slice(0, 1);
            const rawKeys = [];
            stages.forEach((stage, index) => {
                const key = getEmpresaWorkflowStageGroupKey(stage, index);
                if (!rawKeys.includes(key)) rawKeys.push(key);
            });
            const groupMap = new Map(rawKeys.map((key, index) => [key, String(index + 1)]));
            empresaWorkflowState.customStages = stages.map((stage, index) => {
                const groupKey = rules.isSimple ? '1' : (groupMap.get(getEmpresaWorkflowStageGroupKey(stage, index)) || String(index + 1));
                return {
                    ...cloneEmpresaWorkflowStage(stage, index),
                    nivel: index + 1,
                    nome: rules.isSimple ? 'Etapa 1' : (rules.isParallel ? `Grupo ${groupKey}` : `Etapa ${groupKey}`),
                    tipo_aprovador: 'PAPEL',
                    workflow_group: groupKey,
                    grupo_paralelo: rules.isSimple ? null : Number(groupKey),
                    regra_aprovacao: normalizeEmpresaWorkflowGroupRule(stage.regra_aprovacao || stage.regra_etapa || 'TODOS'),
                };
            });
        }

        function hydrateEmpresaWorkflowStages(preview) {
            const etapas = Array.isArray(preview?.etapas) ? preview.etapas : [];
            const grupos = Array.isArray(preview?.grupos) ? preview.grupos : [];
            const regrasPorGrupo = new Map(grupos.map((grupo) => [
                String(grupo.ordem || grupo.workflow_group || grupo.grupo_paralelo || grupo.id),
                normalizeEmpresaWorkflowGroupRule(grupo.regra_aprovacao || grupo.regra_etapa),
            ]));
            empresaWorkflowState.customStages = etapas.map((stage, index) => {
                const cloned = cloneEmpresaWorkflowStage(stage, index);
                const groupKey = String(cloned.workflow_group || cloned.grupo_paralelo || cloned.nivel || index + 1);
                cloned.regra_aprovacao = regrasPorGrupo.get(groupKey) || normalizeEmpresaWorkflowGroupRule(stage.regra_aprovacao || stage.regra_etapa);
                cloned.regra_etapa = cloned.regra_aprovacao;
                return cloned;
            });
            if (!empresaWorkflowState.customStages.length) empresaWorkflowState.customStages = [createEmpresaWorkflowApprover('1')];
            empresaWorkflowState.globalSignature = Boolean(preview?.assinatura_obrigatoria);
            empresaWorkflowState.globalRule = 'TODOS';
            empresaWorkflowState.collapsedGroups = {};
            normalizeEmpresaWorkflowStagesOrder();
            empresaWorkflowState.dirty = false;
        }

        function syncEmpresaWorkflowStageDerivedFields(stage) {
            stage.tipo_aprovador = 'PAPEL';
        }

        function createEmpresaWorkflowApprover(groupKey) {
            const nextIndex = (empresaWorkflowState.customStages || []).length;
            return {
                local_id: `empresa-stage-${Date.now()}-${nextIndex}`,
                etapa_id: null,
                nivel: nextIndex + 1,
                nome: getEmpresaWorkflowRules().isParallel ? `Grupo ${groupKey}` : `Etapa ${groupKey}`,
                tipo_aprovador: 'PAPEL',
                papel_id: empresaWorkflowRoleOptions[0]?.id || '',
                workflow_group: String(groupKey || 1),
                grupo_paralelo: getEmpresaWorkflowRules().isSimple ? null : Number(groupKey || 1),
                regra_aprovacao: 'TODOS',
                regra_etapa: 'TODOS',
            };
        }

        function markEmpresaWorkflowDirty(value = true) {
            empresaWorkflowState.dirty = value;
            workflowEl('workflowCompanyDirtyBadge')?.classList.toggle('hidden', !value);
            workflowEl('workflowCompanyOwnConfigNotice')?.classList.toggle('hidden', !value);
        }

        function renderEmpresaWorkflowSummary() {
            const summary = workflowEl('workflowCompanySummary');
            const title = workflowEl('workflowCompanyStagesTitle');
            const addButton = workflowEl('workflowCompanyAddStageButton');
            if (!summary) return;
            const groups = getEmpresaWorkflowVisualGroups();
            const total = groups.length;
            const totalApprovers = groups.reduce((sum, group) => sum + group.items.length, 0);
            const rules = getEmpresaWorkflowRules();
            if (title) {
                title.textContent = rules.isParallel ? 'Grupos e papéis' : 'Etapas e papéis';
            }
            if (addButton) {
                addButton.classList.toggle('hidden', rules.isSimple || !isEmpresaWorkflowEditing());
                const icon = addButton.querySelector('i');
                if (icon) icon.className = 'fas fa-plus';
                const actionLabel = rules.isParallel ? 'Adicionar grupo' : 'Adicionar etapa';
                addButton.setAttribute('aria-label', actionLabel);
                addButton.setAttribute('title', actionLabel);
                const label = addButton.querySelector('.workflow-add-label');
                if (label) {
                    label.textContent = actionLabel;
                }
            }
            const estruturaLabel = rules.isParallel ? 'grupo' : 'etapa';
            summary.textContent = `${total} ${estruturaLabel}${total === 1 ? '' : 's'} · ${totalApprovers} ${totalApprovers === 1 ? 'papel' : 'papéis'}`;
        }

        function addEmpresaWorkflowApproverToGroup(groupKey) {
            if (getEmpresaWorkflowRules().isSimple || !isEmpresaWorkflowEditing()) return;
            empresaWorkflowState.customStages.push(createEmpresaWorkflowApprover(groupKey));
            normalizeEmpresaWorkflowStagesOrder();
            markEmpresaWorkflowDirty();
            renderEmpresaWorkflowCards();
        }

        function removeEmpresaWorkflowApprover(stageKey, fallbackIndex = null) {
            if (!isEmpresaWorkflowEditing()) return;
            const index = findEmpresaWorkflowStageIndex(stageKey, fallbackIndex);
            if (index < 0) return;
            const groups = getEmpresaWorkflowVisualGroups();
            const group = groups.find((item) => item.items.some((row) => row.index === index));
            if (!group || group.items.length <= 1) {
                showWarning('Grupo mínimo', 'Cada etapa ou grupo deve ter ao menos um papel.');
                return;
            }
            empresaWorkflowState.customStages.splice(index, 1);
            normalizeEmpresaWorkflowStagesOrder();
            markEmpresaWorkflowDirty();
            renderEmpresaWorkflowCards();
        }

        function removeEmpresaWorkflowGroup(groupKey) {
            if (!isEmpresaWorkflowEditing()) return;
            const groups = getEmpresaWorkflowVisualGroups();
            if (groups.length <= 1) {
                showWarning('Workflow mínimo', 'O workflow deve ter pelo menos uma etapa ou grupo.');
                return;
            }
            empresaWorkflowState.customStages = (empresaWorkflowState.customStages || []).filter((stage, index) => getEmpresaWorkflowStageGroupKey(stage, index) !== String(groupKey));
            normalizeEmpresaWorkflowStagesOrder();
            markEmpresaWorkflowDirty();
            renderEmpresaWorkflowCards();
        }

        function bindEmpresaWorkflowStageListeners() {
            const container = workflowEl('workflowCompanyStagesContainer');
            if (!container || container.dataset.workflowBound === 'true') return;
            container.addEventListener('change', (event) => {
                const groupRuleSelect = event.target.closest('.empresa-workflow-group-rule');
                if (groupRuleSelect) {
                    if (!isEmpresaWorkflowEditing()) return;
                    setEmpresaWorkflowGroupRule(groupRuleSelect.dataset.groupKey, groupRuleSelect.value);
                    markEmpresaWorkflowDirty();
                    renderEmpresaWorkflowCards();
                    return;
                }

                const select = event.target.closest('.empresa-workflow-stage-role');
                if (!select) return;
                const index = findEmpresaWorkflowStageIndex(select.dataset.stageKey, select.dataset.stageIndex);
                const stage = empresaWorkflowState.customStages[index];
                if (!stage || !isEmpresaWorkflowEditing()) return;
                stage.papel_id = select.value || '';
                syncEmpresaWorkflowStageDerivedFields(stage);
                markEmpresaWorkflowDirty();
                renderEmpresaWorkflowCards();
            });
            container.addEventListener('click', (event) => {
                const actionButton = event.target.closest('[data-workflow-action]');
                if (!actionButton) return;
                const action = actionButton.dataset.workflowAction;
                if (action === 'remove-approver') {
                    removeEmpresaWorkflowApprover(actionButton.dataset.stageKey, Number(actionButton.dataset.stageIndex));
                    return;
                }
                if (action === 'add-approver') {
                    addEmpresaWorkflowApproverToGroup(actionButton.dataset.groupKey);
                    return;
                }
                if (action === 'toggle-group') {
                    toggleEmpresaWorkflowGroupCollapsed(actionButton.dataset.groupKey);
                    return;
                }
                if (action === 'remove-group') {
                    if (!isEmpresaWorkflowEditing()) return;
                    removeEmpresaWorkflowGroup(actionButton.dataset.groupKey);
                }
            });
            container.dataset.workflowBound = 'true';
        }

        function bindEmpresaWorkflowDragSorting() {
            const groupCards = Array.from(document.querySelectorAll('.empresa-workflow-group-card'));
            const rules = getEmpresaWorkflowRules();
            if (rules.isSimple || !isEmpresaWorkflowEditing()) return;
            let dragKey = null;

            groupCards.forEach((card) => {
                card.addEventListener('dragstart', () => {
                    dragKey = String(card.dataset.workflowGroupKey || '');
                    card.classList.add('opacity-40');
                });
                card.addEventListener('dragend', () => {
                    card.classList.remove('opacity-40');
                });
                card.addEventListener('dragover', (event) => {
                    event.preventDefault();
                });
                card.addEventListener('drop', (event) => {
                    event.preventDefault();
                    const dropKey = String(card.dataset.workflowGroupKey || '');
                    if (!dragKey || dragKey === dropKey) return;
                    const groups = getEmpresaWorkflowVisualGroups();
                    const orderedKeys = groups.map((group) => String(group.key));
                    const fromIndex = orderedKeys.indexOf(dragKey);
                    const toIndex = orderedKeys.indexOf(dropKey);
                    if (fromIndex < 0 || toIndex < 0) return;
                    const movedKey = orderedKeys.splice(fromIndex, 1)[0];
                    orderedKeys.splice(toIndex, 0, movedKey);
                    const keyedGroups = new Map(groups.map((group) => [String(group.key), group.items.map((item) => item.stage)]));
                    empresaWorkflowState.customStages = orderedKeys.flatMap((key) => keyedGroups.get(key) || []);
                    dragKey = null;
                    normalizeEmpresaWorkflowStagesOrder();
                    markEmpresaWorkflowDirty();
                    renderEmpresaWorkflowCards();
                });
            });
        }

        function formatWorkflowRoleLabel(label) {
            const raw = String(label || '').trim();
            return raw;
            const normalized = raw.toUpperCase();
            const knownLabels = {
                FISCAL: 'Fiscal',
                COORDENADOR: 'Coordenador',
                CLIENTE_OBRA: 'Cliente da obra',
                GESTOR_CONTRATO: 'Gestor de contrato',
                RESPONSAVEL_OBRA: 'Responsável pela obra',
            };
            if (knownLabels[normalized]) return knownLabels[normalized];
            if (!raw.includes('_')) return raw;
            const readable = raw.toLowerCase().replace(/_/g, ' ');
            return readable.charAt(0).toUpperCase() + readable.slice(1);
        }

        const formatEmpresaWorkflowRoleLabel = formatWorkflowRoleLabel;

        function renderEmpresaWorkflowRoleSelect(stage, stageIndex, disabled) {
            const stageKey = getEmpresaWorkflowStageKey(stage, stageIndex);
            const editClasses = 'bg-white border-slate-200 text-slate-700 shadow-sm placeholder:text-slate-400';
            const viewClasses = 'bg-transparent border-transparent text-slate-800 font-bold shadow-none cursor-default pointer-events-none select-none';
            const selectedRole = getEmpresaWorkflowRoleById(stage.papel_id);
            const selectedLabel = formatEmpresaWorkflowRoleLabel(selectedRole?.nome || 'Selecione o papel');
            const buttonClasses = `flex h-9 min-w-0 w-full items-center gap-2 rounded-xl border px-3 pr-9 text-left text-xs font-semibold ${disabled ? viewClasses : editClasses}`;
            const optionClasses = 'flex h-9 w-full items-center gap-2 px-3 text-left text-xs font-semibold text-slate-700 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none';
            const optionHtml = [
                `<button type="button" class="${optionClasses}" data-workflow-dropdown-option data-value=""><span class="min-w-0 flex-1 truncate">Selecione o papel</span><i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check aria-hidden="true"></i></button>`,
                ...empresaWorkflowRoleOptions.map((papel) => `
                    <button type="button" class="${optionClasses}" data-workflow-dropdown-option data-value="${escapeEmpresaWorkflowHtml(papel.id)}">
                        <span class="min-w-0 flex-1 truncate">${escapeEmpresaWorkflowHtml(formatEmpresaWorkflowRoleLabel(papel.nome))}</span>
                        <i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check aria-hidden="true"></i>
                    </button>
                `),
            ].join('');
            return `
                <div class="relative" data-workflow-custom-dropdown data-workflow-dropdown-mode="edit">
                    <select id="workflow-stage-role-${stageIndex}" class="empresa-workflow-stage-role hidden" data-no-tom-select="true" data-stage-index="${stageIndex}" data-stage-key="${escapeEmpresaWorkflowHtml(stageKey)}" tabindex="${disabled ? '-1' : '0'}" aria-disabled="${disabled ? 'true' : 'false'}">
                        <option value="">Selecione o papel</option>
                        ${empresaWorkflowRoleOptions.map((papel) => `
                            <option value="${escapeEmpresaWorkflowHtml(papel.id)}" ${Number(papel.id) === Number(stage.papel_id) ? 'selected' : ''}>${escapeEmpresaWorkflowHtml(formatEmpresaWorkflowRoleLabel(papel.nome))}</option>
                        `).join('')}
                    </select>
                    <button type="button" class="${buttonClasses}" data-workflow-dropdown-button tabindex="${disabled ? '-1' : '0'}" aria-haspopup="listbox" aria-expanded="false" aria-disabled="${disabled ? 'true' : 'false'}">
                        <span class="min-w-0 flex-1 truncate" data-workflow-dropdown-label>${escapeEmpresaWorkflowHtml(selectedLabel)}</span>
                    </button>
                    ${disabled ? '' : '<div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400"><i class="fas fa-chevron-down text-[10px]" aria-hidden="true"></i></div>'}
                    <div class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 hidden max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl" data-workflow-dropdown-menu role="listbox">
                        ${optionHtml}
                    </div>
                </div>
            `;
        }

        function renderEmpresaWorkflowApproverCard(stage, stageIndex, groupSize, rules) {
            const editing = isEmpresaWorkflowEditing();
            const stageKey = getEmpresaWorkflowStageKey(stage, stageIndex);
            const selectedRole = getEmpresaWorkflowRoleById(stage.papel_id);
            const roleLabel = formatEmpresaWorkflowRoleLabel(selectedRole?.nome || `papel ${stageIndex + 1}`);
            const removeDisabled = groupSize <= 1;
            const showStageHandle = editing && !rules.isSimple;
            return `
                <div class="empresa-workflow-stage-card flex min-w-0 items-center gap-2 border-t border-slate-100 px-2 py-1.5" data-stage-index="${stageIndex}" data-stage-key="${escapeEmpresaWorkflowHtml(stageKey)}" data-etapa-id="${String(stage.etapa_id || '')}">
                    ${showStageHandle ? `<span class="inline-flex h-8 w-5 shrink-0 cursor-grab items-center justify-center text-slate-300" aria-label="Arrastar papel" role="img">
                        <i class="fas fa-grip-vertical text-xs" aria-hidden="true"></i>
                    </span>` : ''}
                    <label class="sr-only" for="workflow-stage-role-${stageIndex}">Papel ${stageIndex + 1}</label>
                    <div class="min-w-0 flex-1">
                        ${renderEmpresaWorkflowRoleSelect(stage, stageIndex, !editing)}
                    </div>
                    ${rules.isSimple || !editing ? '' : `
                        <button type="button" data-workflow-action="remove-approver" data-stage-index="${stageIndex}" data-stage-key="${escapeEmpresaWorkflowHtml(stageKey)}" ${removeDisabled ? 'disabled' : ''} aria-label="Excluir papel ${escapeEmpresaWorkflowHtml(roleLabel)}" title="Excluir papel" class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-200 disabled:cursor-not-allowed disabled:opacity-35">
                            <i class="fas fa-times text-xs" aria-hidden="true"></i>
                        </button>
                    `}
                </div>
            `;
        }

        function renderEmpresaWorkflowAddApproverButton(groupKey, rules) {
            if (rules.isSimple || !isEmpresaWorkflowEditing()) return '';
            return `
                <button type="button" data-workflow-action="add-approver" data-group-key="${String(groupKey)}" class="flex h-9 w-full items-center justify-center gap-2 border-t border-dashed border-slate-200 px-2 text-xs font-bold text-slate-500 transition hover:bg-blue-50 hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-200">
                    <i class="fas fa-plus text-[10px]" aria-hidden="true"></i>
                    <span>Adicionar papel</span>
                </button>
            `;
        }

        function renderEmpresaWorkflowCollapsedState(rules) {
            const entityLabel = rules.isParallel ? 'Grupo' : 'Etapa';
            return `
                <div class="border-t border-slate-100 px-2.5 py-2 text-[11px] font-semibold text-slate-500">
                    ${entityLabel} recolhido.
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupContent(group, rules) {
            if (isEmpresaWorkflowGroupCollapsed(group.key)) {
                return renderEmpresaWorkflowCollapsedState(rules);
            }
            return `
                <div>
                    ${group.items.map((item) => renderEmpresaWorkflowApproverCard(item.stage, item.index, group.items.length, rules)).join('')}
                    ${renderEmpresaWorkflowAddApproverButton(group.key, rules)}
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupRuleControl(group, rules) {
            if (rules.isSimple) return '';
            const editing = isEmpresaWorkflowEditing();
            const value = getEmpresaWorkflowGroupRule(group);
            const label = value === 'QUALQUER' ? 'Qualquer um aprova' : 'Todos devem aprovar';
            const groupKey = escapeEmpresaWorkflowHtml(String(group.key));
            const buttonClasses = editing
                ? 'flex h-9 min-w-0 w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 pr-9 text-left text-xs font-semibold text-slate-700 shadow-sm placeholder:text-slate-400'
                : 'flex h-9 min-w-0 w-full items-center gap-2 rounded-xl border border-transparent bg-transparent px-3 pr-9 text-left text-xs font-bold text-slate-800 shadow-none cursor-default pointer-events-none select-none';
            const optionClasses = 'flex h-9 w-full items-center gap-2 px-3 text-left text-xs font-semibold text-slate-700 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none';
            return `
                <div class="relative" data-workflow-custom-dropdown data-workflow-dropdown-mode="edit">
                    <label class="sr-only" for="workflow-group-rule-${groupKey}">Regra do grupo</label>
                    <select id="workflow-group-rule-${groupKey}" data-no-tom-select="true" data-group-key="${groupKey}" class="empresa-workflow-group-rule hidden" tabindex="${editing ? '0' : '-1'}" aria-disabled="${editing ? 'false' : 'true'}">
                        <option value="TODOS" ${value === 'TODOS' ? 'selected' : ''}>Todos devem aprovar</option>
                        <option value="QUALQUER" ${value === 'QUALQUER' ? 'selected' : ''}>Qualquer um aprova</option>
                    </select>
                    <button type="button" class="${buttonClasses}" data-workflow-dropdown-button tabindex="${editing ? '0' : '-1'}" aria-haspopup="listbox" aria-expanded="false" aria-disabled="${editing ? 'false' : 'true'}">
                        <span class="min-w-0 flex-1 truncate" data-workflow-dropdown-label>${escapeEmpresaWorkflowHtml(label)}</span>
                    </button>
                    ${editing ? '<div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400"><i class="fas fa-chevron-down text-[10px]" aria-hidden="true"></i></div>' : ''}
                    <div class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 hidden overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl" data-workflow-dropdown-menu role="listbox">
                        <button type="button" class="${optionClasses}" data-workflow-dropdown-option data-value="TODOS">
                            <span class="min-w-0 flex-1 truncate">Todos devem aprovar</span>
                            <i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check aria-hidden="true"></i>
                        </button>
                        <button type="button" class="${optionClasses}" data-workflow-dropdown-option data-value="QUALQUER">
                            <span class="min-w-0 flex-1 truncate">Qualquer um aprova</span>
                            <i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupHeader(group, groupIndex, groupsLength, rules) {
            const entityLabel = rules.isParallel ? 'Grupo' : 'Etapa';
            const dragLabel = rules.isParallel ? 'Arrastar grupo' : 'Arrastar etapa';
            const removeLabel = rules.isParallel ? 'Excluir grupo' : 'Excluir etapa';
            const title = rules.isSimple ? 'Etapa 1' : `${entityLabel} ${groupIndex + 1}`;
            const editing = isEmpresaWorkflowEditing();
            const showGroupHandle = !rules.isSimple && editing;
            const canRemoveGroup = !rules.isSimple && groupsLength > 1 && editing;
            const collapsed = isEmpresaWorkflowGroupCollapsed(group.key);
            const ruleBadge = rules.isParallel
                ? (empresaWorkflowState.globalRule === 'PRIMEIRO' ? 'Primeiro' : 'Todos')
                : (rules.isSequential ? 'Sequencial' : 'Única');
            const toggleLabel = collapsed ? `Expandir ${title}` : `Recolher ${title}`;
            const headerMinHeight = rules.isSimple ? 'min-h-[44px]' : 'min-h-[76px]';

            return `
                <div class="flex ${headerMinHeight} flex-col gap-2 px-3 py-2.5">
                    <div class="flex items-center justify-between gap-2">
                        <div class="flex min-w-0 items-center gap-2">
                            ${showGroupHandle ? `<button type="button" class="inline-flex h-7 w-6 cursor-grab items-center justify-center rounded-lg text-slate-400 active:cursor-grabbing" aria-label="${dragLabel}">
                                <i class="fas fa-grip-vertical text-xs" aria-hidden="true"></i>
                            </button>` : ''}
                            <h5 class="min-w-0 truncate text-xs font-black text-slate-900">${title}</h5>
                            <span class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">${group.items.length} papel${group.items.length === 1 ? '' : 's'}</span>
                        </div>
                        <div class="flex shrink-0 items-center gap-1">
                            <button type="button" data-workflow-action="toggle-group" data-group-key="${String(group.key)}" aria-label="${toggleLabel}" aria-expanded="${collapsed ? 'false' : 'true'}" title="${toggleLabel}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200">
                                <i class="fas ${collapsed ? 'fa-chevron-down' : 'fa-chevron-up'} text-[10px]" aria-hidden="true"></i>
                            </button>
                            ${canRemoveGroup ? `<button type="button" data-workflow-action="remove-group" data-group-key="${String(group.key)}" aria-label="${removeLabel}" title="${removeLabel}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-200"><i class="fas fa-trash-alt text-xs" aria-hidden="true"></i></button>` : ''}
                        </div>
                    </div>
                    ${rules.isSimple ? '' : `<div class="${showGroupHandle ? 'pl-8' : ''}">
                        ${renderEmpresaWorkflowGroupRuleControl(group, rules)}
                    </div>`}
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupCard(group, groupIndex, groupsLength, rules) {
            const draggable = rules.isSimple || !isEmpresaWorkflowEditing() ? 'false' : 'true';
            return `
                <div class="empresa-workflow-group-card overflow-visible rounded-xl border border-slate-200 bg-white shadow-none" data-workflow-group-key="${String(group.key)}" draggable="${draggable}">
                    ${renderEmpresaWorkflowGroupHeader(group, groupIndex, groupsLength, rules)}
                    ${renderEmpresaWorkflowGroupContent(group, rules)}
                </div>
            `;
        }

        function renderEmpresaWorkflowCards() {
            const container = workflowEl('workflowCompanyStagesContainer');
            if (!container) return;
            const rules = getEmpresaWorkflowRules();
            normalizeEmpresaWorkflowStagesOrder();
            const groups = getEmpresaWorkflowVisualGroups();

            if (rules.isParallel) {
                container.className = 'space-y-2';
                container.innerHTML = `
                    <div class="space-y-2">
                        ${groups.map((group, groupIndex) => renderEmpresaWorkflowGroupCard(group, groupIndex, groups.length, rules)).join('')}
                    </div>
                `;
            } else {
                container.className = 'space-y-2';
                container.innerHTML = groups
                    .map((group, groupIndex) => renderEmpresaWorkflowGroupCard(group, groupIndex, groups.length, rules))
                    .join(rules.isSequential ? '<div class="flex justify-center text-[10px] text-slate-300"><i class="fas fa-arrow-down" aria-hidden="true"></i></div>' : '');
            }

            renderEmpresaWorkflowSummary();
            renderEmpresaWorkflowDiagramPreview();
            bindEmpresaWorkflowStageListeners();
            bindEmpresaWorkflowDragSorting();
            syncEmpresaWorkflowDropdowns(container);
        }

        function syncEmpresaWorkflowControls() {
            const select = workflowEl('workflowCompanySelect');
            const previewInput = workflowEl('workflowCompanySelectPreview');
            const dropdownLabel = workflowEl('workflowCompanyTypeDropdownLabel');
            const signature = workflowEl('workflowCompanySignature');
            const signaturePreviewInput = workflowEl('workflowCompanySignaturePreview');
            if (select) {
                select.value = String(empresaWorkflowState.selectedWorkflowModel || 'simples');
                const selectedOption = select.options[select.selectedIndex];
                const selectedLabel = selectedOption ? selectedOption.text : 'Selecione';
                if (previewInput) previewInput.value = selectedLabel;
                if (dropdownLabel) dropdownLabel.textContent = selectedLabel;
                document.querySelectorAll('.workflow-company-type-option').forEach((option) => {
                    const isActive = option.dataset.value === select.value;
                    option.classList.toggle('bg-blue-50', isActive);
                    option.classList.toggle('text-blue-700', isActive);
                    option.querySelector('.workflow-company-type-check')?.classList.toggle('hidden', !isActive);
                });
            }
            setEmpresaWorkflowSelectValue(signature, empresaWorkflowState.globalSignature ? '1' : '0');
            if (signature && signaturePreviewInput) {
                signaturePreviewInput.value = getEmpresaWorkflowDropdownLabel(signature);
            }
            syncEmpresaWorkflowDropdowns(workflowEl('empresa-panel-workflow') || document);
        }

        function loadEmpresaWorkflowPreview(model) {
            const preview = getEmpresaWorkflowPreviewByModel(model);
            if (!preview) return;
            empresaWorkflowState.selectedWorkflowId = Number(preview.workflow_id || 0);
            empresaWorkflowState.selectedWorkflowModel = model;
            empresaWorkflowState.preview = preview;
            hydrateEmpresaWorkflowStages(preview);
            syncEmpresaWorkflowControls();
            markEmpresaWorkflowDirty(false);
            renderEmpresaWorkflowCards();
        }

        function loadEmpresaWorkflowPreviewById(workflowId) {
            const preview = getEmpresaWorkflowPreview(workflowId);
            if (!preview) return false;
            empresaWorkflowState.selectedWorkflowId = Number(preview.workflow_id || 0);
            empresaWorkflowState.selectedWorkflowModel = getEmpresaWorkflowModelKind(preview);
            empresaWorkflowState.preview = preview;
            hydrateEmpresaWorkflowStages(preview);
            syncEmpresaWorkflowControls();
            markEmpresaWorkflowDirty(false);
            renderEmpresaWorkflowCards();
            return true;
        }

        async function saveEmpresaWorkflow() {
            const workflowId = empresaWorkflowState.selectedWorkflowId;
            if (!workflowId) {
                return await showWarning('Workflow ausente', 'Selecione um workflow para salvar.');
            }

            const rules = getEmpresaWorkflowRules();
            const groups = getEmpresaWorkflowVisualGroups();

            for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
                const group = groups[groupIndex];
                if (!group.items.length) {
                    return await showWarning('Etapa incompleta', 'Cada etapa ou grupo deve ter ao menos um papel.');
                }
                for (const item of group.items) {
                    if (!item.stage.papel_id) {
                        return await showWarning('Etapa incompleta', `Selecione o papel de todos os cards da ${rules.isParallel ? 'grupo' : 'etapa'} ${groupIndex + 1}.`);
                    }
                }
            }

            const tipoFluxo = rules.isParallel ? 'PARALELO' : (rules.isSequential ? 'SEQUENCIAL' : 'SIMPLES');
            const payload = {
                assinatura_obrigatoria: empresaWorkflowState.globalSignature,
                aprovacao_paralela: rules.isParallel,
                regra_etapa: 'TODOS',
                tipo_fluxo: tipoFluxo,
                grupos: groups.map((group, groupIndex) => ({
                    key: String(group.key),
                    nome: rules.isSimple ? 'Etapa 1' : (rules.isParallel ? `Grupo ${groupIndex + 1}` : `Etapa ${groupIndex + 1}`),
                    ordem: groupIndex + 1,
                    regra_aprovacao: getEmpresaWorkflowGroupRule(group),
                })),
                etapas: groups.flatMap((group, groupIndex) => group.items.map((item, itemIndex) => ({
                    nome: rules.isParallel ? `Grupo ${groupIndex + 1}` : `Etapa ${groupIndex + 1}`,
                    tipo_aprovador: 'PAPEL',
                    papel_id: item.stage.papel_id || null,
                    usuario_aprovador_id: null,
                    workflow_group: String(group.key),
                    grupo_paralelo: rules.isSimple ? null : (groupIndex + 1),
                    regra_aprovacao: getEmpresaWorkflowGroupRule(group),
                    regra_etapa: getEmpresaWorkflowGroupRule(group),
                    ordem_visual: itemIndex + 1,
                }))),
            };

            try {
                const { response, data } = await fetchJson(String(empresaUrls.updateWorkflowEmpresa || '').replace(/0$/, String(workflowId)), {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || 'Não foi possível salvar o workflow.');
                }

                const defaultResult = await fetchJson(empresaUrls.updateWorkflowDefault, {
                    method: 'POST',
                    body: JSON.stringify({ workflow_id: workflowId }),
                });
                if (!defaultResult.response.ok || !defaultResult.data.ok) {
                    throw new Error(defaultResult.data.error || 'Não foi possível definir este workflow como padrão.');
                }

                window.location.assign(empresaUrls.empresaView || window.location.href);
            } catch (error) {
                console.error(error);
                await showError('Erro ao salvar workflow', error.message || 'Não foi possível salvar o workflow.');
            }
        }

        function resetEmpresaWorkflowEditor() {
            if (!empresaWorkflowState.preview) return;
            hydrateEmpresaWorkflowStages(empresaWorkflowState.preview);
            syncEmpresaWorkflowControls();
            markEmpresaWorkflowDirty(false);
            renderEmpresaWorkflowCards();
        }

        window.saveEmpresaWorkflowAction = saveEmpresaWorkflow;
        window.resetEmpresaWorkflowEditor = resetEmpresaWorkflowEditor;
        window.hasEmpresaWorkflowChanges = () => empresaWorkflowState.dirty;

        function bootstrapEmpresaWorkflowEditor() {
            const select = workflowEl('workflowCompanySelect');
            if (!select) return;

            const handleWorkflowTypeChange = async (value) => {
                if (!value || value === String(empresaWorkflowState.selectedWorkflowModel || 'simples')) {
                    syncEmpresaWorkflowControls();
                    closeEmpresaWorkflowTypeDropdown();
                    return;
                }
                if (empresaWorkflowState.dirty) {
                    const confirmed = await showConfirm('Alterar workflow', 'As alterações não salvas serão descartadas. Deseja continuar?');
                    if (!confirmed) {
                        syncEmpresaWorkflowControls();
                        closeEmpresaWorkflowTypeDropdown();
                        return;
                    }
                }
                closeEmpresaWorkflowTypeDropdown();
                loadEmpresaWorkflowPreview(value);
            };

            select.addEventListener('change', async (event) => {
                if (!isEmpresaWorkflowEditing()) {
                    syncEmpresaWorkflowControls();
                    return;
                }
                await handleWorkflowTypeChange(event.target.value);
            });

            document.addEventListener('click', (event) => {
                const option = event.target.closest('[data-workflow-dropdown-option]');
                if (option) {
                    selectEmpresaWorkflowDropdownOption(option);
                    return;
                }

                const button = event.target.closest('[data-workflow-dropdown-button]');
                if (button) {
                    toggleEmpresaWorkflowDropdown(getEmpresaWorkflowDropdownWrapper(button));
                    return;
                }

                if (!event.target.closest('[data-workflow-custom-dropdown]')) {
                    closeEmpresaWorkflowDropdowns();
                }
            });

            document.addEventListener('keydown', (event) => {
                const dropdownTarget = event.target.closest?.('[data-workflow-dropdown-button], [data-workflow-dropdown-option]');
                if (!dropdownTarget) return;
                const wrapper = getEmpresaWorkflowDropdownWrapper(dropdownTarget) || activeEmpresaWorkflowDropdown?.wrapper;
                if (!wrapper || !canOpenEmpresaWorkflowDropdown(wrapper)) return;

                if (dropdownTarget.matches('[data-workflow-dropdown-button]') && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
                    event.preventDefault();
                    const menu = getEmpresaWorkflowDropdownParts(wrapper).menu;
                    if (menu?.classList.contains('hidden')) {
                        toggleEmpresaWorkflowDropdown(wrapper);
                    }
                    focusEmpresaWorkflowDropdownOption(wrapper, event.key === 'ArrowUp' ? 'previous' : event.key === 'Home' ? 'first' : event.key === 'End' ? 'last' : 'current');
                    return;
                }

                if (!dropdownTarget.matches('[data-workflow-dropdown-option]')) return;
                if (event.key === 'Escape') {
                    event.preventDefault();
                    const button = getEmpresaWorkflowDropdownParts(wrapper).button;
                    closeEmpresaWorkflowDropdowns();
                    button?.focus({ preventScroll: true });
                    return;
                }
                if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
                    event.preventDefault();
                    focusEmpresaWorkflowDropdownOption(wrapper, event.key === 'ArrowUp' ? 'previous' : event.key === 'Home' ? 'first' : event.key === 'End' ? 'last' : 'next');
                    return;
                }
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    selectEmpresaWorkflowDropdownOption(dropdownTarget);
                }
            });

            window.addEventListener('scroll', () => {
                if (activeEmpresaWorkflowDropdown) {
                    positionEmpresaWorkflowDropdownMenu(activeEmpresaWorkflowDropdown.wrapper, activeEmpresaWorkflowDropdown.menu);
                }
            }, true);

            window.addEventListener('resize', () => {
                if (activeEmpresaWorkflowDropdown) {
                    positionEmpresaWorkflowDropdownMenu(activeEmpresaWorkflowDropdown.wrapper, activeEmpresaWorkflowDropdown.menu);
                }
            });

            workflowEl('workflowCompanySignature')?.addEventListener('change', (event) => {
                empresaWorkflowState.globalSignature = event.target.value === '1';
                markEmpresaWorkflowDirty();
            });

            workflowEl('workflowCompanyAddStageButton')?.addEventListener('click', () => {
                if (!isEmpresaWorkflowEditing()) return;
                const nextGroupKey = String(getEmpresaWorkflowVisualGroups().length + 1);
                empresaWorkflowState.customStages.push(createEmpresaWorkflowApprover(nextGroupKey));
                normalizeEmpresaWorkflowStagesOrder();
                markEmpresaWorkflowDirty();
                renderEmpresaWorkflowCards();
            });

            workflowEl('workflowCompanyDiagramZoomOut')?.addEventListener('click', () => {
                alterarEmpresaWorkflowDiagramZoom(-0.1);
            });
            workflowEl('workflowCompanyDiagramZoomReset')?.addEventListener('click', () => {
                resetEmpresaWorkflowDiagramZoom();
            });
            workflowEl('workflowCompanyDiagramZoomIn')?.addEventListener('click', () => {
                alterarEmpresaWorkflowDiagramZoom(0.1);
            });

            const diagramCanvas = workflowEl('workflowCompanyDiagramCanvas');
            if (diagramCanvas) {
                diagramCanvas.addEventListener('wheel', zoomEmpresaWorkflowDiagramPorWheel, { passive: false });
                diagramCanvas.addEventListener('pointerdown', iniciarArrasteEmpresaWorkflowDiagram);
                window.addEventListener('pointermove', arrastarEmpresaWorkflowDiagram);
                window.addEventListener('pointerup', encerrarArrasteEmpresaWorkflowDiagram);
                window.addEventListener('pointercancel', encerrarArrasteEmpresaWorkflowDiagram);
                diagramCanvas.addEventListener('dragstart', (event) => event.preventDefault());
            }

            if (!loadEmpresaWorkflowPreviewById(empresaWorkflowDefaultId)) {
                loadEmpresaWorkflowPreview(select.value || 'simples');
            }
            syncEmpresaWorkflowDiagramViewport();
            syncEmpresaWorkflowDropdowns(workflowEl('empresa-panel-workflow') || document);
        }

        document.addEventListener('DOMContentLoaded', bootstrapEmpresaWorkflowEditor);


        // Modulo de Edicao Inline via AJAX
        (function () {
            const timers = {};
            const controllers = {};

            function showStatus(container, text, cls) {
                const s = container.querySelector('[data-role="status"]');
                if (!s) return;
                s.textContent = text;
                s.className = 'text-xs font-bold ' + (cls || 'text-slate-400');
            }

            async function saveConfig(chave, valor, container) {
                showStatus(container, 'Salvando...', 'text-blue-500');
                try {
                    if (controllers[chave]) {
                        try { controllers[chave].abort(); } catch (_) { }
                    }
                    const controller = new AbortController();
                    controllers[chave] = controller;

                    const { response, data } = await fetchJson(empresaUrls.updateEmpresaConfig, {
                        method: 'POST',
                        headers: buildJsonHeaders(),
                        body: JSON.stringify({ chave: chave, valor: valor }),
                        signal: controller.signal
                    });
                    delete controllers[chave];

                    if (response.ok && data.ok) {
                        const valEl = container.querySelector('[data-role="valor"]');
                        if (valEl) valEl.textContent = data.valor;
                        showStatus(container, 'Salvo', 'text-emerald-500');
                        setTimeout(() => showStatus(container, ''), 1500);
                    } else {
                        showStatus(container, data.error || 'Erro', 'text-rose-500');
                    }
                } catch (e) {
                    if (e.name === 'AbortError') return;
                    showStatus(container, 'Erro', 'text-rose-500');
                }
            }

            function makeEditable(row) {
                const chave = row.getAttribute('data-chave');
                const valEl = row.querySelector('[data-role="valor"]');
                const editBtn = row.querySelector('[data-action="edit"]');
                if (!valEl || !editBtn) return;

                editBtn.addEventListener('click', () => {
                    if (row.querySelector('input')) return;
                    const cur = valEl.textContent || '';
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = cur.trim() === 'Nao definido' ? '' : cur.trim();
                    input.className = 'form-control-std h-9 text-sm block w-full rounded-2xl appearance-none bg-white border-slate-300 text-slate-600 shadow-sm placeholder:text-slate-400 font-mono';
                    input.style.maxWidth = '200px';

                    const save = document.createElement('button');
                    save.innerHTML = '<i class="fas fa-check text-[10px]" aria-hidden="true"></i>';
                    save.className = 'w-7 h-7 bg-blue-600 text-white rounded-lg flex items-center justify-center hover:bg-blue-700 ml-2 shadow-sm shrink-0';

                    const cancel = document.createElement('button');
                    cancel.innerHTML = '<i class="fas fa-times text-[10px]" aria-hidden="true"></i>';
                    cancel.className = 'w-7 h-7 bg-white border border-slate-200 text-slate-500 rounded-lg flex items-center justify-center hover:bg-slate-50 ml-1 shadow-sm shrink-0';

                    const container = valEl.parentElement;
                    container.insertBefore(input, valEl);
                    container.insertBefore(save, valEl.nextSibling);
                    container.insertBefore(cancel, save.nextSibling);
                    valEl.style.display = 'none';

                    input.addEventListener('input', () => {
                        if (timers[chave]) clearTimeout(timers[chave]);
                        timers[chave] = setTimeout(() => { saveConfig(chave, input.value, row); }, 1000);
                    });

                    save.addEventListener('click', () => {
                        if (timers[chave]) clearTimeout(timers[chave]);
                        saveConfig(chave, input.value, row);
                        cleanup();
                    });

                    cancel.addEventListener('click', () => cleanup(true));

                    function cleanup(rollback = false) {
                        if (rollback) input.value = cur;
                        input.remove(); save.remove(); cancel.remove();
                        valEl.style.display = '';
                    }
                });
            }

            document.querySelectorAll('div[data-chave]').forEach(makeEditable);
        })();
})();

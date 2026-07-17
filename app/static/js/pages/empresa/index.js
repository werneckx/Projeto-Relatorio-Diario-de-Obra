(function () {
    const pageData = window.__empresaPageData || {};
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
    }

    function previewImage(input, imgId) {
        const [file] = input.files;
        if (file) {
            const preview = document.getElementById(imgId);
            const previewContainer = preview?.parentElement || document.getElementById(`preview-${String(imgId).replace(/^img-/, '')}`);
            const objectUrl = URL.createObjectURL(file);
            if (previewObjectUrls[imgId]) {
                URL.revokeObjectURL(previewObjectUrls[imgId]);
            }
            previewObjectUrls[imgId] = objectUrl;
            if (!previewContainer) return;
            if (!preview || preview.tagName !== 'IMG') {
                previewContainer.innerHTML = `<img src="${objectUrl}" id="${imgId}" class="max-w-full max-h-full object-contain p-4 animate-fade-in">`;
            } else if (preview) {
                preview.src = objectUrl;
            }
        }
    }
    window.previewImage = previewImage;

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

    function normalizeObraDetalhe(item) {
        if (!item) return null;
        const workflowEtapas = Array.isArray(item.workflow_etapas)
            ? item.workflow_etapas.map((etapa, index) => ({
                nivel: toNonNegativeNumber(etapa?.nivel) || (index + 1),
                nome: String(etapa?.nome || `Etapa ${index + 1}`),
                papel: String(etapa?.papel || etapa?.nome || `Etapa ${index + 1}`),
                tempo_medio: String(etapa?.tempo_medio || 'Sem histórico'),
            }))
            : [];
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
                tabOrder: ['geral', 'definicoes', 'papeis', 'workflow'],
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
                filtroObras: '',
                filtroWorkflow: '',
                filtroResponsavel: '',
                filtroStatus: '',
                obrasWorkflowData: pageData.obrasWorkflowData || [],
                workflowDefaultCodigo: pageData.workflowDefaultCodigo || 'SIMPLES',
                empresaEditing: Boolean(pageData.startInEditMode),

                init() {
                    this.abaAtiva = localStorage.getItem('empresa_aba_ativa') || this.abaAtiva || 'geral';
                    prepareEmpresaRouteTransition();
                    initializeEmpresaGeneralFormState();
                    setEmpresaEditingDataset(this.empresaEditing);
                    window.applyRequiredMarkers?.(document);
                    if (typeof this.$watch === 'function') {
                        this.$watch('filtroStatus', syncEmpresaStatusFilterPickers);
                    }
                },
                mudarAba(aba) {
                    this.abaAtiva = aba;
                    localStorage.setItem('empresa_aba_ativa', aba);
                    if (aba !== 'workflow') closeEmpresaWorkflowTypeDropdown();
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
                isSectionEditing() {
                    return this.empresaEditing;
                },
                hasGlobalActions() {
                    return true;
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
                        return this.empresaEditing
                            ? 'Agora os botoes de criar e editar definicoes estao habilitados.'
                            : 'Ative a edicao para habilitar os botoes desta secao.';
                    }
                    if (this.abaAtiva === 'papeis') {
                        return this.empresaEditing
                            ? 'Agora os botoes de criar e editar papeis estao habilitados.'
                            : 'Ative a edicao para habilitar os botoes desta secao.';
                    }
                    return 'Use os controles disponiveis nesta secao.';
                },
                isSaveDisabled() {
                    if (!this.empresaEditing) return true;
                    if (this.abaAtiva === 'workflow') {
                        return !window.hasEmpresaWorkflowChanges?.();
                    }
                    return false;
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
                    if (this.abaAtiva === 'geral') {
                        document.getElementById('empresaForm')?.requestSubmit();
                        return;
                    }
                    if (this.abaAtiva === 'workflow') {
                        window.saveEmpresaWorkflowAction?.();
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
                    const termoStatus = normalizeSearchText(this.filtroStatus);
                    return this.obrasWorkflowData.filter((obra) => {
                        const matchObra = !termoObra || normalizeSearchText(obra.obra_nome).includes(termoObra);
                        const matchWorkflow = !termoWorkflow || normalizeSearchText(obra.workflow_nome).includes(termoWorkflow);
                        const matchResponsavel = !termoResponsavel || normalizeSearchText(obra.responsavel).includes(termoResponsavel);
                        const matchStatus = !termoStatus || normalizeSearchText(obra.status) === termoStatus;
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
                    this.obraDetalheVisible = !!this.obraSelecionada;
                },
                fecharDetalhesObra() {
                    this.obraDetalheVisible = false;
                    this.obraSelecionada = null;
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
                        cardH: 110,
                        cardW: 190,
                        cardX: 130,
                        columnWidth: 460,
                        columns,
                        decisionGap: 88,
                        diamondHalf: 42,
                        firstRowY,
                        height: firstRowY + ((rows - 1) * rowHeight) + 184,
                        rejectedBadgeW: 94,
                        rowHeight,
                        startCx: 54,
                        startR: 28,
                        width: columns === 1 ? 790 : 1270,
                    };
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
                getWorkflowDiagramSvg(obra) {
                    const etapas = this.getObraFluxoEtapas(obra);
                    if (!etapas.length) return '';

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

                    connectors.push(this.renderWorkflowSvgPath(
                        `M ${layout.startCx + layout.startR} ${layout.firstRowY} H ${stagePositions[0].cardX}`,
                        neutral,
                        'workflow-arrow-neutral',
                    ));
                    shapes.push(`<circle cx="${layout.startCx}" cy="${layout.firstRowY}" r="${layout.startR}" fill="${slate}" filter="url(#workflow-node-shadow)"></circle>`);
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

                        connectors.push(this.renderWorkflowSvgPath(`M ${cardRight} ${stage.rowY} H ${decisionLeft}`, neutral, 'workflow-arrow-neutral'));
                        connectors.push(this.renderWorkflowSvgPath(`M ${decisionRight} ${stage.rowY} H ${stage.approvedBadgeX}`, green));
                        connectors.push(this.renderWorkflowSvgPath(`M ${stage.decisionCx} ${decisionBottom} V ${rejectedBadgeY}`, red));
                        connectors.push(this.renderWorkflowSvgPath(`M ${stage.decisionCx} ${rejectedBadgeY + layout.badgeH} V ${rejectedCircleY - 22}`, red, 'workflow-arrow-rejected'));

                        if (!isLast) {
                            const nextStage = stagePositions[index + 1];
                            connectors.push(this.renderWorkflowSvgPath(
                                this.getWorkflowApprovedConnectorPath(stage, nextStage, layout),
                                green,
                                'workflow-arrow-approved',
                            ));
                        } else {
                            const finalCircleX = approvedBadgeRight + 76;
                            const finalCircleY = stage.rowY;
                            connectors.push(this.renderWorkflowSvgPath(`M ${approvedBadgeRight} ${stage.rowY} H ${finalCircleX - 24}`, green, 'workflow-arrow-approved'));
                            shapes.push(`<circle cx="${finalCircleX}" cy="${finalCircleY}" r="18" fill="#16a34a"></circle>`);
                            labels.push(`<path d="M ${finalCircleX - 8} ${finalCircleY} L ${finalCircleX - 2} ${finalCircleY + 6} L ${finalCircleX + 9} ${finalCircleY - 7}" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`);
                            labels.push(`<text x="${finalCircleX + 28}" y="${finalCircleY + 6}" fill="${green}" font-size="17" font-weight="800">Fim aprovado</text>`);
                        }

                        shapes.push(`<rect x="${stage.cardX}" y="${stage.cardY}" width="${layout.cardW}" height="${layout.cardH}" rx="8" fill="#ffffff" stroke="#cbd5e1" filter="url(#workflow-card-shadow)"></rect>`);
                        shapes.push(`<polygon points="${stage.decisionCx},${stage.decisionCy - layout.diamondHalf} ${stage.decisionCx + layout.diamondHalf},${stage.decisionCy} ${stage.decisionCx},${stage.decisionCy + layout.diamondHalf} ${stage.decisionCx - layout.diamondHalf},${stage.decisionCy}" fill="${slate}" filter="url(#workflow-node-shadow)"></polygon>`);
                        shapes.push(`<circle cx="${stage.decisionCx}" cy="${rejectedCircleY}" r="21" fill="${red}"></circle>`);
                        labels.push(`<text x="${stage.cardX + 16}" y="${stage.cardY + 30}" fill="#475569" font-size="12" font-weight="800">ETAPA ${escapeSvgText(etapa.nivel || index + 1)}</text>`);
                        labels.push(this.renderWorkflowSvgTextLines(
                            wrapWorkflowSvgText(stageName, 18, 3),
                            stage.cardX + 16,
                            stage.cardY + 62,
                            22,
                            `fill="${dark}" font-size="17" font-weight="800"`,
                        ));
                        labels.push(`<text x="${stage.decisionCx}" y="${stage.decisionCy + 4}" fill="#ffffff" text-anchor="middle" font-size="11" font-weight="800">Decisão</text>`);
                        labels.push(this.renderWorkflowSvgBadge('Aprovado', stage.approvedBadgeX, stage.approvedBadgeY, layout.badgeW, layout.badgeH, green));
                        labels.push(this.renderWorkflowSvgBadge('Recusado', rejectedBadgeX, rejectedBadgeY, layout.rejectedBadgeW, layout.badgeH, red));
                        labels.push(`<text x="${stage.decisionCx}" y="${rejectedCircleY + 4}" fill="#ffffff" text-anchor="middle" font-size="12" font-weight="800">Fim</text>`);
                    });

                    return `
                        <svg class="workflow-board-svg" viewBox="0 0 ${layout.width} ${layout.height}" role="img" aria-label="Diagrama de aprovação" xmlns="http://www.w3.org/2000/svg">
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
        };

        function workflowEl(id) {
            return document.getElementById(id);
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

        function resetEmpresaWorkflowDropdownMenu(menu) {
            if (!menu) return;
            menu.classList.add('hidden');
            menu.style.position = '';
            menu.style.left = '';
            menu.style.top = '';
            menu.style.width = '';
            menu.style.maxHeight = '';
            menu.style.zIndex = '';
        }

        function restoreEmpresaWorkflowDropdownMenu() {
            if (!activeEmpresaWorkflowDropdown) return;
            const { wrapper, menu } = activeEmpresaWorkflowDropdown;
            resetEmpresaWorkflowDropdownMenu(menu);
            if (wrapper && menu && !wrapper.contains(menu)) {
                wrapper.appendChild(menu);
            }
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

            wrapper.querySelectorAll('[data-workflow-dropdown-option]').forEach((option) => {
                const isActive = String(option.dataset.value ?? '') === value;
                option.classList.toggle('bg-blue-50', isActive);
                option.classList.toggle('text-blue-700', isActive);
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
            };
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
                };
            });
        }

        function hydrateEmpresaWorkflowStages(preview) {
            const etapas = Array.isArray(preview?.etapas) ? preview.etapas : [];
            empresaWorkflowState.customStages = etapas.map((stage, index) => cloneEmpresaWorkflowStage(stage, index));
            if (!empresaWorkflowState.customStages.length) empresaWorkflowState.customStages = [createEmpresaWorkflowApprover('1')];
            empresaWorkflowState.globalSignature = Boolean(preview?.assinatura_obrigatoria);
            empresaWorkflowState.globalRule = String((etapas[0]?.regra_etapa) || (preview?.aprovacao_paralela ? 'TODOS' : 'PRIMEIRO')).toUpperCase() === 'PRIMEIRO' ? 'PRIMEIRO' : 'TODOS';
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
            const preview = empresaWorkflowState.preview || {};
            const groups = getEmpresaWorkflowVisualGroups();
            const total = groups.length;
            const origem = preview.workflow_origem || 'Workflow da Empresa';
            const rules = getEmpresaWorkflowRules();
            if (title) {
                title.textContent = rules.isParallel ? 'Grupos e Papeis' : 'Etapas e Papeis';
            }
            if (addButton) {
                addButton.classList.toggle('hidden', rules.isSimple || !isEmpresaWorkflowEditing());
                const icon = addButton.querySelector('i');
                if (icon) icon.className = 'fas fa-plus';
                let label = addButton.querySelector('.workflow-add-label');
                if (!label) {
                    label = document.createElement('span');
                    label.className = 'workflow-add-label';
                    addButton.appendChild(label);
                }
                label.textContent = rules.isParallel ? 'Adicionar grupo' : 'Adicionar etapa';
            }
            const estruturaLabel = rules.isParallel ? 'grupo' : 'etapa';
            const definicaoLabel = rules.isSequential
                ? 'com aprovacao em ordem hierarquica'
                : rules.isParallel
                    ? 'com aprovacao paralela por papel'
                    : 'com definicao por papel';
            summary.textContent = `${origem} com ${total} ${estruturaLabel}${total === 1 ? '' : 's'} ${definicaoLabel}.`;
        }

        function addEmpresaWorkflowApproverToGroup(groupKey) {
            if (getEmpresaWorkflowRules().isSimple || !isEmpresaWorkflowEditing()) return;
            empresaWorkflowState.customStages.push(createEmpresaWorkflowApprover(groupKey));
            normalizeEmpresaWorkflowStagesOrder();
            markEmpresaWorkflowDirty();
            renderEmpresaWorkflowCards();
        }

        function removeEmpresaWorkflowApprover(index) {
            if (!isEmpresaWorkflowEditing()) return;
            const groups = getEmpresaWorkflowVisualGroups();
            const group = groups.find((item) => item.items.some((row) => row.index === index));
            if (!group || group.items.length <= 1) {
                showWarning('Grupo minimo', 'Cada etapa ou grupo deve ter ao menos um papel.');
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
                showWarning('Workflow minimo', 'O workflow deve ter pelo menos uma etapa ou grupo.');
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
                const select = event.target.closest('.empresa-workflow-stage-role');
                if (!select) return;
                const index = Number(select.dataset.stageIndex);
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
                    removeEmpresaWorkflowApprover(Number(actionButton.dataset.stageIndex));
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

        function renderEmpresaWorkflowRoleSelect(stage, stageIndex, disabled) {
            const baseClasses = 'form-control-std h-9 text-sm block w-full rounded-2xl appearance-none';
            const editClasses = 'bg-white border-slate-300 text-slate-600 shadow-sm placeholder:text-slate-400';
            const viewClasses = 'bg-slate-100/60 border-slate-200 text-slate-800 font-semibold shadow-none cursor-default pointer-events-none select-none';
            const selectedRole = getEmpresaWorkflowRoleById(stage.papel_id);
            const selectedLabel = selectedRole?.nome || 'Selecione o papel';
            const buttonClasses = `${baseClasses} flex h-11 w-full items-center gap-2 rounded-2xl border px-4 pr-12 text-left font-semibold ${disabled ? viewClasses : editClasses}`;
            const optionHtml = [
                '<button type="button" class="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50" data-workflow-dropdown-option data-value=""><span class="min-w-0 flex-1 truncate">Selecione o papel</span><i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check></i></button>',
                ...empresaWorkflowRoleOptions.map((papel) => `
                    <button type="button" class="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50" data-workflow-dropdown-option data-value="${escapeEmpresaWorkflowHtml(papel.id)}">
                        <span class="min-w-0 flex-1 truncate">${escapeEmpresaWorkflowHtml(papel.nome)}</span>
                        <i class="fas fa-check hidden text-blue-600" data-workflow-dropdown-check></i>
                    </button>
                `),
            ].join('');
            return `
                <div class="relative" data-workflow-custom-dropdown data-workflow-dropdown-mode="edit">
                    <select class="empresa-workflow-stage-role hidden" data-no-tom-select="true" data-stage-index="${stageIndex}" tabindex="${disabled ? '-1' : '0'}" aria-disabled="${disabled ? 'true' : 'false'}">
                        <option value="">Selecione o papel</option>
                        ${empresaWorkflowRoleOptions.map((papel) => `
                            <option value="${escapeEmpresaWorkflowHtml(papel.id)}" ${Number(papel.id) === Number(stage.papel_id) ? 'selected' : ''}>${escapeEmpresaWorkflowHtml(papel.nome)}</option>
                        `).join('')}
                    </select>
                    <button type="button" class="${buttonClasses}" data-workflow-dropdown-button tabindex="${disabled ? '-1' : '0'}" aria-disabled="${disabled ? 'true' : 'false'}">
                        <span class="min-w-0 flex-1 truncate" data-workflow-dropdown-label>${escapeEmpresaWorkflowHtml(selectedLabel)}</span>
                    </button>
                    ${disabled ? '' : '<div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4 text-slate-400"><i class="fas fa-chevron-down text-xs"></i></div>'}
                    <div class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 hidden max-h-72 overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl" data-workflow-dropdown-menu>
                        ${optionHtml}
                    </div>
                </div>
            `;
        }

        function renderEmpresaWorkflowApproverCard(stage, stageIndex, groupSize, rules) {
            const editing = isEmpresaWorkflowEditing();
            return `
                <div class="empresa-workflow-stage-card min-w-[280px] flex-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-none" data-stage-index="${stageIndex}" data-etapa-id="${String(stage.etapa_id || '')}">
                    <div class="space-y-3">
                        <div>
                            <label class="mb-1 block text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">Papel</label>
                            ${renderEmpresaWorkflowRoleSelect(stage, stageIndex, !editing)}
                        </div>
                        ${rules.isSimple || !editing ? '' : `<button type="button" data-workflow-action="remove-approver" data-stage-index="${stageIndex}" ${groupSize <= 1 ? 'disabled' : ''} class="h-9 w-full rounded-xl border border-rose-300 bg-white text-xs font-bold text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40">Excluir</button>`}
                    </div>
                </div>
            `;
        }

        function renderEmpresaWorkflowAddApproverButton(groupKey, rules) {
            if (rules.isSimple || !isEmpresaWorkflowEditing()) return '';
            return `
                <button type="button" data-workflow-action="add-approver" data-group-key="${String(groupKey)}" class="my-1 flex min-h-[148px] w-20 shrink-0 self-stretch items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50/60 text-3xl font-black text-slate-400 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-500">
                    <i class="fas fa-plus"></i>
                </button>
            `;
        }

        function renderEmpresaWorkflowCollapsedState(rules) {
            const entityLabel = rules.isParallel ? 'Grupo' : 'Etapa';
            return `
                <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500">
                    ${entityLabel} recolhido. Arraste pelo icone para alterar a ordem.
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupContent(group, rules) {
            if (isEmpresaWorkflowGroupCollapsed(group.key)) {
                return renderEmpresaWorkflowCollapsedState(rules);
            }
            const separator = empresaWorkflowState.globalRule === 'PRIMEIRO'
                ? '<span class="text-xs font-black text-slate-400">OU</span>'
                : '<span class="text-xs font-black text-slate-400">E</span>';
            return `
                <div class="flex flex-wrap items-start gap-3">
                    ${group.items.map((item) => renderEmpresaWorkflowApproverCard(item.stage, item.index, group.items.length, rules)).join(separator)}
                    ${renderEmpresaWorkflowAddApproverButton(group.key, rules)}
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupHeader(group, groupIndex, groupsLength, rules) {
            const entityLabel = rules.isParallel ? 'Grupo' : 'Etapa';
            const dragLabel = rules.isParallel ? 'Arrastar grupo' : 'Arrastar etapa';
            const removeLabel = rules.isParallel ? 'Excluir grupo' : 'Excluir etapa';
            const title = rules.isSimple ? 'Etapa 1' : `${entityLabel} ${groupIndex + 1}`;
            const editing = isEmpresaWorkflowEditing();
            const dragClasses = rules.isSimple || !editing ? 'cursor-default' : 'cursor-grab';
            const canRemoveGroup = !rules.isSimple && groupsLength > 1 && editing;

            return `
                <div class="mb-3 flex items-center justify-between gap-3">
                    <div class="flex items-center gap-2">
                        <button type="button" class="inline-flex h-7 w-7 ${dragClasses} items-center justify-center rounded-lg bg-slate-100 text-slate-500 active:cursor-grabbing" aria-label="${dragLabel}">
                            <i class="fas fa-grip-vertical"></i>
                        </button>
                        <h5 class="text-sm font-black text-slate-900">${title}</h5>
                        <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">${group.items.length} papel${group.items.length === 1 ? '' : 's'}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <button type="button" data-workflow-action="toggle-group" data-group-key="${String(group.key)}" class="text-xs font-bold text-slate-500 hover:text-slate-700">${isEmpresaWorkflowGroupCollapsed(group.key) ? 'Expandir' : 'Encolher'}</button>
                        ${canRemoveGroup ? `<button type="button" data-workflow-action="remove-group" data-group-key="${String(group.key)}" class="text-xs font-bold text-rose-600 hover:text-rose-700">${removeLabel}</button>` : ''}
                    </div>
                </div>
            `;
        }

        function renderEmpresaWorkflowGroupCard(group, groupIndex, groupsLength, rules) {
            const minWidthClass = rules.isParallel ? 'min-w-[520px]' : '';
            const draggable = rules.isSimple || !isEmpresaWorkflowEditing() ? 'false' : 'true';
            return `
                <div class="empresa-workflow-group-card ${minWidthClass} rounded-2xl border border-slate-200 bg-white p-5 shadow-none" data-workflow-group-key="${String(group.key)}" draggable="${draggable}">
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
                container.className = 'overflow-x-auto px-4 py-5';
                container.innerHTML = `
                    <div class="flex min-w-full items-start gap-5">
                        ${groups.map((group, groupIndex) => renderEmpresaWorkflowGroupCard(group, groupIndex, groups.length, rules)).join('')}
                    </div>
                `;
            } else {
                container.className = 'space-y-5 p-4';
                container.innerHTML = groups
                    .map((group, groupIndex) => renderEmpresaWorkflowGroupCard(group, groupIndex, groups.length, rules))
                    .join(rules.isSequential ? '<div class="flex justify-center text-slate-300"><i class="fas fa-arrow-down"></i></div>' : '');
            }

            renderEmpresaWorkflowSummary();
            bindEmpresaWorkflowStageListeners();
            bindEmpresaWorkflowDragSorting();
            syncEmpresaWorkflowDropdowns(container);
        }

        function syncEmpresaWorkflowControls() {
            const select = workflowEl('workflowCompanySelect');
            const previewInput = workflowEl('workflowCompanySelectPreview');
            const dropdownLabel = workflowEl('workflowCompanyTypeDropdownLabel');
            const signature = workflowEl('workflowCompanySignature');
            const rule = workflowEl('workflowCompanyRule');
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
            setEmpresaWorkflowSelectValue(rule, empresaWorkflowState.globalRule);
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
                regra_etapa: empresaWorkflowState.globalRule,
                tipo_fluxo: tipoFluxo,
                etapas: groups.flatMap((group, groupIndex) => group.items.map((item, itemIndex) => ({
                    nome: rules.isParallel ? `Grupo ${groupIndex + 1}` : `Etapa ${groupIndex + 1}`,
                    tipo_aprovador: 'PAPEL',
                    papel_id: item.stage.papel_id || null,
                    usuario_aprovador_id: null,
                    grupo_paralelo: rules.isSimple ? null : (groupIndex + 1),
                    ordem_visual: itemIndex + 1,
                }))),
            };

            try {
                const { response, data } = await fetchJson(String(empresaUrls.updateWorkflowEmpresa || '').replace(/0$/, String(workflowId)), {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || 'Nao foi possivel salvar o workflow.');
                }
                location.reload();
            } catch (error) {
                console.error(error);
                await showError('Erro ao salvar workflow', error.message || 'Nao foi possivel salvar o workflow.');
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
                    const confirmed = await showConfirm('Alterar workflow', 'As alteracoes nao salvas serao descartadas. Deseja continuar?');
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

            workflowEl('workflowCompanyRule')?.addEventListener('change', (event) => {
                empresaWorkflowState.globalRule = event.target.value === 'PRIMEIRO' ? 'PRIMEIRO' : 'TODOS';
                markEmpresaWorkflowDirty();
                renderEmpresaWorkflowCards();
            });

            workflowEl('workflowCompanyAddStageButton')?.addEventListener('click', () => {
                if (!isEmpresaWorkflowEditing()) return;
                const nextGroupKey = String(getEmpresaWorkflowVisualGroups().length + 1);
                empresaWorkflowState.customStages.push(createEmpresaWorkflowApprover(nextGroupKey));
                normalizeEmpresaWorkflowStagesOrder();
                markEmpresaWorkflowDirty();
                renderEmpresaWorkflowCards();
            });

            loadEmpresaWorkflowPreview(select.value || 'simples');
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
                    save.innerHTML = '<i class="fas fa-check text-[10px]"></i>';
                    save.className = 'w-7 h-7 bg-blue-600 text-white rounded-lg flex items-center justify-center hover:bg-blue-700 ml-2 shadow-xs shrink-0';

                    const cancel = document.createElement('button');
                    cancel.innerHTML = '<i class="fas fa-times text-[10px]"></i>';
                    cancel.className = 'w-7 h-7 bg-white border border-slate-200 text-slate-500 rounded-lg flex items-center justify-center hover:bg-slate-50 ml-1 shadow-xs shrink-0';

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

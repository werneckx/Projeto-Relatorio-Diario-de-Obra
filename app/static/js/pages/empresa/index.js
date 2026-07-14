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
            });
        }
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
                obraDetalheAba: 'resumo',
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
                    window.applyRequiredMarkers?.(document);
                    scheduleEmpresaWorkflowSelectPickersEditing(this.empresaEditing);
                },
                mudarAba(aba) {
                    this.abaAtiva = aba;
                    localStorage.setItem('empresa_aba_ativa', aba);
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
                    replaceEmpresaRoute(empresaUrls.empresaEdit);
                    setEmpresaWorkflowSelectPickersEditing(true);
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
                    pageData.startInEditMode = false;
                    replaceEmpresaRoute(empresaUrls.empresaView);
                    setEmpresaWorkflowSelectPickersEditing(false);
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
                    replaceEmpresaRoute(empresaUrls.empresaView);
                    setEmpresaWorkflowSelectPickersEditing(false);
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
                abrirModalObras() { this.modalObrasVisible = true; },
                fecharModalObras() { this.modalObrasVisible = false; },
                abrirDetalhesObra(obraId) {
                    this.obraSelecionada = this.obrasWorkflowData.find((obra) => obra.obra_id === obraId) || null;
                    this.obraDetalheAba = 'resumo';
                    this.obraDetalheVisible = !!this.obraSelecionada;
                },
                fecharDetalhesObra() {
                    this.obraDetalheVisible = false;
                    this.obraSelecionada = null;
                    this.obraDetalheAba = 'resumo';
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

        function getEmpresaAppState() {
            return document.getElementById('empresaPageRoot')?.__x?.$data || null;
        }

        function isEmpresaWorkflowEditing() {
            return Boolean(getEmpresaAppState()?.empresaEditing);
        }

        function setEmpresaWorkflowSelectPickersEditing(isEditing) {
            ['workflowCompanySignature', 'workflowCompanyRule'].forEach((id) => {
                const select = workflowEl(id);
                if (!select) return;
                if (select.tomselect) {
                    if (isEditing) {
                        select.tomselect.enable();
                    } else {
                        select.tomselect.disable();
                    }
                    return;
                }
                select.disabled = !isEditing;
                if (isEditing) window.refreshSelectPicker?.(select);
            });
        }

        function scheduleEmpresaWorkflowSelectPickersEditing(isEditing) {
            const applyState = () => window.setTimeout(() => setEmpresaWorkflowSelectPickersEditing(isEditing), 0);
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', applyState, { once: true });
                return;
            }
            applyState();
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
            const baseClasses = 'form-control-std h-9 text-sm block w-full rounded-2xl appearance-none empresa-form-control';
            const editClasses = 'empresa-form-control--edit';
            const viewClasses = 'empresa-form-control--view pointer-events-none select-none';
            return `
                <select class="empresa-workflow-stage-role ${baseClasses} ${disabled ? viewClasses : editClasses}" data-stage-index="${stageIndex}" tabindex="${disabled ? '-1' : '0'}" aria-disabled="${disabled ? 'true' : 'false'}">
                    <option value="">Selecione o papel</option>
                    ${empresaWorkflowRoleOptions.map((papel) => `
                        <option value="${papel.id}" ${Number(papel.id) === Number(stage.papel_id) ? 'selected' : ''}>${papel.nome}</option>
                    `).join('')}
                </select>
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
                <div class="flex items-stretch gap-4 overflow-x-auto px-2 py-4">
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
                <div class="empresa-workflow-group-card ${minWidthClass} rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_28px_rgba(15,23,42,0.06)]" data-workflow-group-key="${String(group.key)}" draggable="${draggable}">
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
                    const isActive = option.dataset.workflowModel === select.value;
                    option.classList.toggle('bg-blue-50', isActive);
                    option.querySelector('.workflow-company-type-check')?.classList.toggle('hidden', !isActive);
                });
            }
            if (signature) signature.value = empresaWorkflowState.globalSignature ? '1' : '0';
            if (rule) rule.value = empresaWorkflowState.globalRule;
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
            const dropdownButton = workflowEl('workflowCompanyTypeDropdownButton');
            const dropdownMenu = workflowEl('workflowCompanyTypeDropdownMenu');

            const closeWorkflowTypeDropdown = () => {
                dropdownMenu?.classList.add('hidden');
            };

            const toggleWorkflowTypeDropdown = () => {
                if (!isEmpresaWorkflowEditing()) return;
                dropdownMenu?.classList.toggle('hidden');
            };

            const handleWorkflowTypeChange = async (value) => {
                if (!value || value === String(empresaWorkflowState.selectedWorkflowModel || 'simples')) {
                    syncEmpresaWorkflowControls();
                    closeWorkflowTypeDropdown();
                    return;
                }
                if (empresaWorkflowState.dirty) {
                    const confirmed = await showConfirm('Alterar workflow', 'As alteracoes nao salvas serao descartadas. Deseja continuar?');
                    if (!confirmed) {
                        syncEmpresaWorkflowControls();
                        closeWorkflowTypeDropdown();
                        return;
                    }
                }
                closeWorkflowTypeDropdown();
                loadEmpresaWorkflowPreview(value);
            };

            select.addEventListener('change', async (event) => {
                if (!isEmpresaWorkflowEditing()) {
                    syncEmpresaWorkflowControls();
                    return;
                }
                await handleWorkflowTypeChange(event.target.value);
            });

            dropdownButton?.addEventListener('click', toggleWorkflowTypeDropdown);

            dropdownMenu?.addEventListener('click', async (event) => {
                const option = event.target.closest('.workflow-company-type-option');
                if (!option) return;
                await handleWorkflowTypeChange(option.dataset.workflowModel || '');
            });

            document.addEventListener('click', (event) => {
                const wrapper = workflowEl('workflowCompanyTypeDropdown');
                if (!wrapper || wrapper.contains(event.target)) return;
                closeWorkflowTypeDropdown();
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
                    input.className = 'form-control-std h-9 text-sm block w-full rounded-2xl appearance-none empresa-form-control empresa-form-control--edit font-mono';
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

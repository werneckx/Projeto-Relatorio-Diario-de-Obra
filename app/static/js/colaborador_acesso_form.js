(function () {
  const config = window.ColaboradorAcessoForm || {};
  const form = document.getElementById('colaboradorAcessoForm');
  if (!form) return;

  const submitBtn = document.getElementById('submitBtn');
  const obrasDisponiveis = Array.isArray(config.obras) ? config.obras : [];
  const emailDomains = Array.isArray(config.emailDomains) && config.emailDomains.length
    ? config.emailDomains
    : ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com.br', 'empresa.com'];

  function warn(title, message) {
    if (window.showWarning) return window.showWarning(title, message);
    alert(message);
    return Promise.resolve(false);
  }

  function confirmAction(title, message) {
    if (window.showConfirm) return window.showConfirm(title, message);
    return Promise.resolve(window.confirm(message));
  }

  function formatCpf(value) {
    const digits = String(value || '').replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
    if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
  }

  function snapshotRow(row) {
    if (!row) return;
    row.dataset.originalObra = rowObraSelect(row)?.value || '';
    row.dataset.originalPapel = rowPapelSelect(row)?.value || '';
    row.dataset.originalAtivo = rowAtivoSelect(row)?.value || '1';
  }

  function restoreRow(row) {
    if (!row) return;
    const obraSelect = rowObraSelect(row);
    const papelSelect = rowPapelSelect(row);
    const ativoSelect = rowAtivoSelect(row);
    if (obraSelect) obraSelect.value = row.dataset.originalObra || '';
    if (papelSelect) papelSelect.value = row.dataset.originalPapel || '';
    if (ativoSelect) ativoSelect.value = row.dataset.originalAtivo || '1';
    row.classList.remove('bg-blue-50/40');
    setRowRemoved(row, false);
    setRowEditable(row, false);
  }

  function setButtonVisible(row, selector, visible) {
    row?.querySelector(selector)?.classList.toggle('hidden', !visible);
  }

  function setRowEditable(row, editable) {
    if (!row) return;
    row.querySelectorAll('.obra-row-control').forEach((control) => {
      control.disabled = !editable;
    });
    row.classList.toggle('bg-blue-50/40', editable);
    if (!row.dataset.removed) {
      setButtonVisible(row, '[data-edit-obra-row]', !editable);
      setButtonVisible(row, '[data-cancel-obra-row]', editable);
    }
  }

  function setRowRemoved(row, removed) {
    if (!row) return;
    const ativoSelect = rowAtivoSelect(row);
    if (ativoSelect) ativoSelect.value = removed ? '0' : (row.dataset.originalAtivo || '1');
    row.dataset.removed = removed ? '1' : '';
    row.classList.toggle('bg-rose-50', removed);
    row.classList.toggle('opacity-70', removed);
    row.querySelector('[data-obra-row-state]')?.classList.toggle('hidden', !removed);
    setButtonVisible(row, '[data-edit-obra-row]', !removed);
    setButtonVisible(row, '[data-cancel-obra-row]', false);
    setButtonVisible(row, '[data-remove-obra-row]', !removed);
    setButtonVisible(row, '[data-undo-remove-obra-row]', removed);
    setRowEditable(row, false);
  }

  function selectedPapelId() {
    const papelSelect = document.getElementById('acesso_papel');
    const selected = papelSelect?.selectedOptions?.[0];
    return selected?.dataset?.papelId || '';
  }

  function isAdminSelected() {
    const papelSelect = document.getElementById('acesso_papel');
    return (papelSelect?.value || '').trim().toUpperCase() === 'ADMIN';
  }

  function rowObraSelect(row) {
    return row?.querySelector('select[name="obra_usuario_obra_id[]"]') || null;
  }

  function rowPapelSelect(row) {
    return row?.querySelector('select[name="obra_usuario_papel_id[]"]') || null;
  }

  function rowAtivoSelect(row) {
    return row?.querySelector('select[name="obra_usuario_ativo[]"]') || null;
  }

  function activeRows() {
    const rowsContainer = document.getElementById('obraUsuarioRows');
    if (!rowsContainer) return [];
    return Array.from(rowsContainer.querySelectorAll('[data-obra-user-row]'))
      .filter((row) => row.dataset.removed !== '1');
  }

  function allRows() {
    const rowsContainer = document.getElementById('obraUsuarioRows');
    if (!rowsContainer) return [];
    return Array.from(rowsContainer.querySelectorAll('[data-obra-user-row]'));
  }

  function rowIsIncomplete(row) {
    if (!row || row.dataset.removed === '1') return false;
    const obraValue = rowObraSelect(row)?.value || '';
    const papelValue = rowPapelSelect(row)?.value || '';
    return !obraValue || !papelValue;
  }

  function findIncompleteObraRow() {
    return activeRows().find(rowIsIncomplete) || null;
  }

  function selectedObraIds(exceptRow) {
    return new Set(
      activeRows()
        .filter((row) => row !== exceptRow)
        .map((row) => rowObraSelect(row)?.value || '')
        .filter(Boolean)
    );
  }

  function hasAvailableObraForNewRow() {
    const usedIds = selectedObraIds(null);
    return obrasDisponiveis.some((obra) => !usedIds.has(String(obra.id)));
  }

  function refreshObraOptions() {
    activeRows().forEach((row) => {
      const obraSelect = rowObraSelect(row);
      if (!obraSelect) return;
      const usedIds = selectedObraIds(row);
      Array.from(obraSelect.options).forEach((option) => {
        if (!option.value) return;
        option.hidden = usedIds.has(option.value);
        option.disabled = usedIds.has(option.value);
      });
    });
  }

  function findRowByObra(obraId) {
    return allRows().find((row) => rowObraSelect(row)?.value === String(obraId)) || null;
  }

  function updateEmptyState() {
    const emptyState = document.getElementById('obraUsuarioEmptyState');
    if (!emptyState) return;
    emptyState.classList.toggle('hidden', activeRows().length > 0);
  }

  function addObraRow(obraId, papelId, lockAfterCreate) {
    const rowTemplate = document.getElementById('obraUsuarioRowTemplate');
    const rowsContainer = document.getElementById('obraUsuarioRows');
    if (!rowTemplate || !rowsContainer) return null;
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector('[data-obra-user-row]');
    const obraSelect = rowObraSelect(row);
    const papelSelect = rowPapelSelect(row);
    const ativoSelect = rowAtivoSelect(row);
    if (obraId && obraSelect) obraSelect.value = String(obraId);
    if (papelId && papelSelect) papelSelect.value = String(papelId);
    if (ativoSelect) ativoSelect.value = '1';
    rowsContainer.appendChild(fragment);
    const appended = rowsContainer.lastElementChild;
    snapshotRow(appended);
    setRowEditable(appended, !lockAfterCreate);
    updateEmptyState();
    refreshObraOptions();
    return appended;
  }

  function syncAdminObras() {
    const admin = isAdminSelected();
    const papelId = selectedPapelId();
    const addRowButton = document.getElementById('addObraUsuarioRow');
    const adminHint = document.getElementById('adminObrasHint');
    if (addRowButton) {
      addRowButton.disabled = admin;
      addRowButton.classList.toggle('opacity-50', admin);
      addRowButton.classList.toggle('cursor-not-allowed', admin);
    }
    adminHint?.classList.toggle('hidden', !admin);

    if (!admin) {
      allRows().forEach((row) => {
        row.querySelectorAll('[data-edit-obra-row], [data-remove-obra-row]').forEach((button) => {
          button.disabled = false;
          button.classList.remove('opacity-50', 'cursor-not-allowed');
        });

        if (row.dataset.removed === '1') {
          setRowRemoved(row, true);
          return;
        }

        setButtonVisible(row, '[data-edit-obra-row]', row.dataset.existingRow === '1');
        setButtonVisible(row, '[data-cancel-obra-row]', row.dataset.existingRow !== '1');
        setButtonVisible(row, '[data-remove-obra-row]', true);
        setButtonVisible(row, '[data-undo-remove-obra-row]', false);
      });
      return;
    }

    obrasDisponiveis.forEach((obra) => {
      let row = findRowByObra(obra.id);
      if (!row) {
        row = addObraRow(obra.id, papelId, true);
      }
      const papelSelectRow = rowPapelSelect(row);
      const ativoSelect = rowAtivoSelect(row);
      if (papelSelectRow && papelId) papelSelectRow.value = String(papelId);
      if (ativoSelect) ativoSelect.value = '1';
      setRowRemoved(row, false);
      setRowEditable(row, false);
      snapshotRow(row);
    });
    allRows().forEach((row) => {
      setButtonVisible(row, '[data-edit-obra-row]', false);
      setButtonVisible(row, '[data-cancel-obra-row]', false);
      setButtonVisible(row, '[data-remove-obra-row]', false);
      setButtonVisible(row, '[data-undo-remove-obra-row]', false);
      row.querySelectorAll('[data-edit-obra-row], [data-remove-obra-row]').forEach((button) => {
        button.disabled = true;
        button.classList.add('opacity-50', 'cursor-not-allowed');
      });
      setRowEditable(row, false);
    });
    refreshObraOptions();
  }

  function initCpfMask() {
    const cpfInput = document.getElementById('cadastro_pessoa_fisica');
    if (!cpfInput || cpfInput.disabled || cpfInput.readOnly) return;
    cpfInput.value = formatCpf(cpfInput.value);
    cpfInput.addEventListener('input', () => {
      cpfInput.value = formatCpf(cpfInput.value);
    });
  }

  function initEmailAutocomplete() {
    const emailInput = document.getElementById('acesso_email');
    const emailSuggestions = document.getElementById('acesso_email_suggestions');
    if (!emailInput || !emailSuggestions || emailInput.disabled || emailInput.readOnly) return;

    let activeSuggestionIndex = -1;
    let currentSuggestions = [];
    let suggestionCleanupBound = false;

    function positionEmailSuggestions() {
      if (!emailSuggestions.classList.contains('is-open')) return;
      const rect = emailInput.getBoundingClientRect();
      const viewportPadding = 12;
      const gap = 6;
      const availableBelow = window.innerHeight - rect.bottom - viewportPadding;
      const availableAbove = rect.top - viewportPadding;
      const desiredHeight = Math.min(emailSuggestions.scrollHeight || 0, 256);
      const shouldOpenAbove = availableBelow < Math.min(desiredHeight, 140) && availableAbove > availableBelow;
      const panelHeight = Math.max(48, Math.min(desiredHeight, shouldOpenAbove ? availableAbove : availableBelow, 256));
      const panelWidth = Math.min(rect.width, window.innerWidth - (viewportPadding * 2));
      const left = Math.min(Math.max(rect.left, viewportPadding), window.innerWidth - panelWidth - viewportPadding);
      const top = shouldOpenAbove ? Math.max(viewportPadding, rect.top - panelHeight - gap) : rect.bottom + gap;
      emailSuggestions.style.width = `${panelWidth}px`;
      emailSuggestions.style.left = `${left}px`;
      emailSuggestions.style.top = `${top}px`;
      emailSuggestions.style.maxHeight = `${panelHeight}px`;
    }

    function bindSuggestionViewportEvents() {
      if (suggestionCleanupBound) return;
      suggestionCleanupBound = true;
      window.addEventListener('resize', positionEmailSuggestions);
      window.addEventListener('scroll', positionEmailSuggestions, true);
    }

    function closeEmailSuggestions() {
      emailSuggestions.classList.remove('is-open');
      emailSuggestions.innerHTML = '';
      emailSuggestions.style.removeProperty('width');
      emailSuggestions.style.removeProperty('left');
      emailSuggestions.style.removeProperty('top');
      emailSuggestions.style.removeProperty('max-height');
      activeSuggestionIndex = -1;
      currentSuggestions = [];
    }

    function selectEmailSuggestion(value) {
      emailInput.value = value;
      closeEmailSuggestions();
      emailInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function renderEmailSuggestions(items) {
      emailSuggestions.innerHTML = '';
      currentSuggestions = items.slice();
      if (!items.length) {
        closeEmailSuggestions();
        return;
      }
      items.forEach((suggestion, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ds-autocomplete-option';
        button.setAttribute('role', 'option');
        button.dataset.index = String(index);
        button.textContent = suggestion;
        button.addEventListener('mousedown', (event) => {
          event.preventDefault();
          selectEmailSuggestion(suggestion);
        });
        emailSuggestions.appendChild(button);
      });
      emailSuggestions.classList.add('is-open');
      activeSuggestionIndex = -1;
      bindSuggestionViewportEvents();
      positionEmailSuggestions();
    }

    function updateActiveEmailSuggestion() {
      Array.from(emailSuggestions.querySelectorAll('.ds-autocomplete-option')).forEach((option, index) => {
        option.classList.toggle('is-active', index === activeSuggestionIndex);
      });
    }

    function updateEmailSuggestions(value) {
      const typedValue = (value || '').trim().toLowerCase();
      const [localPart, partialDomain = ''] = typedValue.split('@');
      if (!localPart) {
        renderEmailSuggestions(['usuario@empresa.com', 'operacional@empresa.com', 'acesso@empresa.com']);
        return;
      }
      renderEmailSuggestions(
        emailDomains
          .filter((domain) => !partialDomain || domain.startsWith(partialDomain))
          .slice(0, 6)
          .map((domain) => `${localPart}@${domain}`)
      );
    }

    emailInput.addEventListener('input', () => updateEmailSuggestions(emailInput.value));
    emailInput.addEventListener('focus', () => updateEmailSuggestions(emailInput.value));
    emailInput.addEventListener('keydown', (event) => {
      if (!currentSuggestions.length) return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, currentSuggestions.length - 1);
        updateActiveEmailSuggestion();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, 0);
        updateActiveEmailSuggestion();
      } else if (event.key === 'Enter' && activeSuggestionIndex >= 0) {
        event.preventDefault();
        selectEmailSuggestion(currentSuggestions[activeSuggestionIndex]);
      } else if (event.key === 'Escape') {
        closeEmailSuggestions();
      }
    });
    emailInput.addEventListener('blur', () => window.setTimeout(closeEmailSuggestions, 120));
  }

  function initSenhaAleatoria() {
    const senhaInput = document.getElementById('senha');
    const gerarSenhaInput = document.getElementById('gerar_senha_aleatoria');
    function updateSenhaAleatoria() {
      if (!senhaInput || !gerarSenhaInput) return;
      const gerar = gerarSenhaInput.checked;
      senhaInput.disabled = gerar;
      senhaInput.required = !gerar;
      senhaInput.classList.toggle('opacity-60', gerar);
      senhaInput.classList.toggle('cursor-not-allowed', gerar);
      if (gerar) senhaInput.value = '';
    }
    gerarSenhaInput?.addEventListener('change', updateSenhaAleatoria);
    updateSenhaAleatoria();
  }

  function initTipoFields() {
    const tipoSelect = document.getElementById('tipo');
    const fornecedorField = document.getElementById('fornecedorField');
    const clienteField = document.getElementById('clienteField');
    const fornecedorSelect = document.getElementById('fornecedor_id');
    const clienteSelect = document.getElementById('cliente_id');
    function updateTipoFields() {
      const tipo = tipoSelect?.value || 'PROPRIO';
      fornecedorField?.classList.toggle('hidden', tipo !== 'TERCEIRO');
      clienteField?.classList.toggle('hidden', tipo !== 'CLIENTE');
      if (fornecedorSelect) fornecedorSelect.required = tipo === 'TERCEIRO';
      if (clienteSelect) clienteSelect.required = tipo === 'CLIENTE';
      if (tipo === 'PROPRIO') {
        if (fornecedorSelect) fornecedorSelect.value = '';
        if (clienteSelect) clienteSelect.value = '';
      } else if (tipo === 'TERCEIRO' && clienteSelect) {
        clienteSelect.value = '';
      } else if (tipo === 'CLIENTE' && fornecedorSelect) {
        fornecedorSelect.value = '';
      }
    }
    tipoSelect?.addEventListener('change', updateTipoFields);
    updateTipoFields();
  }

  function initAcessoToggle() {
    const acessoToggle = document.getElementById('possui_acesso');
    const acessoFields = document.getElementById('acessoFields');
    function updateAcessoFields() {
      acessoFields?.classList.toggle('hidden', !acessoToggle?.checked);
    }
    acessoToggle?.addEventListener('change', updateAcessoFields);
    updateAcessoFields();
  }

  function initTabs() {
    const tabs = Array.from(document.querySelectorAll('[data-access-tab]'));
    const panels = Array.from(document.querySelectorAll('[data-access-panel]'));
    function activateTab(tabName) {
      tabs.forEach((tab) => {
        const active = tab.dataset.accessTab === tabName;
        tab.classList.toggle('border-blue-600', active);
        tab.classList.toggle('text-blue-700', active);
        tab.classList.toggle('border-transparent', !active);
        tab.classList.toggle('text-slate-500', !active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        tab.setAttribute('tabindex', active ? '0' : '-1');
      });
      panels.forEach((panel) => {
        panel.classList.toggle('hidden', panel.dataset.accessPanel !== tabName);
      });
    }
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => activateTab(tab.dataset.accessTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const currentIndex = tabs.indexOf(tab);
        const nextIndex = event.key === 'ArrowRight'
          ? (currentIndex + 1) % tabs.length
          : (currentIndex - 1 + tabs.length) % tabs.length;
        tabs[nextIndex].focus();
        activateTab(tabs[nextIndex].dataset.accessTab);
      });
    });
    activateTab('dados');
  }

  function initObrasRows() {
    const addRowButton = document.getElementById('addObraUsuarioRow');
    const rowsContainer = document.getElementById('obraUsuarioRows');
    allRows().forEach((row) => {
      snapshotRow(row);
      setRowEditable(row, false);
    });

    addRowButton?.addEventListener('click', () => {
      const incompleteRow = findIncompleteObraRow();
      if (incompleteRow) {
        warn('Campo vazio', 'Preencha a obra e o papel da linha anterior antes de adicionar outra.');
        setRowEditable(incompleteRow, true);
        rowObraSelect(incompleteRow)?.focus();
        return;
      }
      if (!hasAvailableObraForNewRow()) {
        warn('Sem obras disponíveis', 'Todas as obras disponíveis já estão vinculadas a este usuário.');
        return;
      }
      addObraRow('', '', false);
    });

    rowsContainer?.addEventListener('click', (event) => {
      const row = event.target.closest('[data-obra-user-row]');
      if (!row) return;
      if (event.target.closest('[data-edit-obra-row]')) {
        snapshotRow(row);
        setRowEditable(row, true);
        refreshObraOptions();
      } else if (event.target.closest('[data-cancel-obra-row]')) {
        if (row.dataset.existingRow === '1') {
          restoreRow(row);
        } else {
          row.remove();
          updateEmptyState();
          refreshObraOptions();
        }
      } else if (event.target.closest('[data-remove-obra-row]')) {
        if (row.dataset.existingRow === '1') {
          setRowRemoved(row, true);
        } else {
          row.remove();
        }
        updateEmptyState();
        refreshObraOptions();
      } else if (event.target.closest('[data-undo-remove-obra-row]')) {
        setRowRemoved(row, false);
        refreshObraOptions();
      }
    });

    rowsContainer?.addEventListener('change', (event) => {
      if (event.target.matches('select[name="obra_usuario_obra_id[]"]')) refreshObraOptions();
    });

    document.getElementById('acesso_papel')?.addEventListener('change', syncAdminObras);
    refreshObraOptions();
    syncAdminObras();
  }

  function initResetConfirm() {
    const resetButton = document.querySelector('[data-reset-password-button]');
    resetButton?.addEventListener('click', async (event) => {
      event.preventDefault();
      const ok = await confirmAction(
        'Resetar senha',
        'Deseja gerar uma nova senha temporária e exigir troca no próximo acesso?'
      );
      if (!ok) return;
      resetButton.formAction = resetButton.getAttribute('formaction');
      resetButton.formMethod = resetButton.getAttribute('formmethod') || 'post';
      form.dataset.resetSubmitting = 'true';
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit(resetButton);
      } else {
        form.submit();
      }
    });
  }

  form.addEventListener('submit', (event) => {
    if (form.dataset.submitting === 'true') {
      event.preventDefault();
      return;
    }
    if (form.dataset.resetSubmitting === 'true') {
      delete form.dataset.resetSubmitting;
      form.dataset.submitting = 'true';
      return;
    }

    const incompleteRow = findIncompleteObraRow();
    if (incompleteRow) {
      event.preventDefault();
      warn('Campo vazio', 'Preencha a obra e o papel da linha aberta antes de salvar.');
      setRowEditable(incompleteRow, true);
      rowObraSelect(incompleteRow)?.focus();
      return;
    }

    form.querySelectorAll('.obra-row-control:disabled').forEach((control) => {
      control.disabled = false;
    });
    form.dataset.submitting = 'true';
    if (submitBtn) {
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1.5"></i> Salvando...';
      submitBtn.classList.add('opacity-70', 'cursor-not-allowed');
      submitBtn.setAttribute('disabled', 'disabled');
    }
  });

  initCpfMask();
  initEmailAutocomplete();
  initSenhaAleatoria();
  initTipoFields();
  initAcessoToggle();
  initTabs();
  initObrasRows();
  initResetConfirm();
})();

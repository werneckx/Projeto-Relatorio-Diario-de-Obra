(function () {
  const LOCK_ATTR = 'data-submit-guard-state';
  const CONTROL_SELECTOR = 'button[type="submit"], input[type="submit"]';
  const OPT_OUT_SELECTOR = '[data-submit-guard="off"], [data-no-submit-lock], [data-allow-repeat-submit="true"]';

  function guardDisabled(form) {
    return !form || form.matches(OPT_OUT_SELECTOR);
  }

  function formLocked(form) {
    return form?.getAttribute(LOCK_ATTR) === 'submitting';
  }

  function lockControls(form) {
    form.querySelectorAll(CONTROL_SELECTOR).forEach((control) => {
      if (control.disabled) return;
      control.dataset.submitGuardDisabled = '1';
      control.disabled = true;
      control.setAttribute('aria-disabled', 'true');
      control.setAttribute('aria-busy', 'true');
    });
  }

  function unlockControls(form) {
    form.querySelectorAll('[data-submit-guard-disabled="1"]').forEach((control) => {
      control.disabled = false;
      control.removeAttribute('aria-disabled');
      control.removeAttribute('aria-busy');
      delete control.dataset.submitGuardDisabled;
    });
  }

  function lockForm(form) {
    form.setAttribute(LOCK_ATTR, 'submitting');
    lockControls(form);
  }

  function unlockForm(form) {
    if (!form) return;
    form.removeAttribute(LOCK_ATTR);
    unlockControls(form);
  }

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || guardDisabled(form)) return;

    if (formLocked(form)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }

    lockForm(form);

    window.setTimeout(() => {
      if (event.defaultPrevented) unlockForm(form);
    }, 0);
  }, true);

  if (window.HTMLFormElement?.prototype?.submit) {
    const nativeSubmit = window.HTMLFormElement.prototype.submit;
    if (!nativeSubmit.__submitGuardPatched) {
      const guardedSubmit = function guardedSubmit() {
        if (!guardDisabled(this)) {
          if (formLocked(this)) return undefined;
          lockForm(this);
        }
        return nativeSubmit.apply(this, arguments);
      };
      guardedSubmit.__submitGuardPatched = true;
      window.HTMLFormElement.prototype.submit = guardedSubmit;
    }
  }

  window.addEventListener('pageshow', () => {
    document.querySelectorAll(`form[${LOCK_ATTR}="submitting"]`).forEach(unlockForm);
  });
})();

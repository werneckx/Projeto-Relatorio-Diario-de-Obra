/*
  Centralized helper for admin DataTables pages.
  Keeps per-page behavior (IDs/dom/columns) configurable without duplicating boilerplate.
*/

(function () {
  function _escapeCsv(value) {
    if (value === null || value === undefined) return "";
    const s = String(value)
      .replace(/\r?\n|\r/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (/[",;]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  function initDataTable(tableSelector, options) {
    if (!window.$ || !$.fn || !$.fn.DataTable) return null;
    return $(tableSelector).DataTable(options);
  }

  function bindSearch(inputSelector, dataTable) {
    if (!dataTable) return;
    const input = document.querySelector(inputSelector);
    if (!input) return;
    input.addEventListener("keyup", function () {
      dataTable.search(this.value).draw();
    });
  }

  window.AdminTables = window.AdminTables || {};
  window.AdminTables.initWithSearch = function (cfg) {
    const dtOptions = cfg.dataTableOptions || cfg.options;
    const table = initDataTable(cfg.tableSelector, dtOptions);
    bindSearch(cfg.searchInputSelector, table);
    return table;
  };

  window.AdminTables.exportCsv = function (cfg) {
    const tableSelector = cfg && cfg.tableSelector ? cfg.tableSelector : null;
    if (!tableSelector) return;

    const tableEl = document.querySelector(tableSelector);
    if (!tableEl) return;

    const filename = (cfg && cfg.filename) || "export.csv";

    const headerCells = Array.from(tableEl.querySelectorAll("thead th"));
    const excludeIndexes = new Set(
      headerCells
        .map((th, idx) => ({ idx, text: (th.innerText || "").trim().toLowerCase() }))
        .filter((h) => h.text === "ações" || h.text === "acoes")
        .map((h) => h.idx)
    );

    const headers = headerCells
      .filter((_, idx) => !excludeIndexes.has(idx))
      .map((th) => _escapeCsv(th.innerText || ""));

    const rows = Array.from(tableEl.querySelectorAll("tbody tr")).filter((tr) => {
      const style = window.getComputedStyle(tr);
      return style && style.display !== "none";
    });

    const csvLines = [];
    csvLines.push(headers.join(";"));

    rows.forEach((tr) => {
      const cells = Array.from(tr.querySelectorAll("td"))
        .filter((_, idx) => !excludeIndexes.has(idx))
        .map((td) => _escapeCsv(td.innerText || ""));
      csvLines.push(cells.join(";"));
    });

    const blob = new Blob(["\uFEFF" + csvLines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };
})();

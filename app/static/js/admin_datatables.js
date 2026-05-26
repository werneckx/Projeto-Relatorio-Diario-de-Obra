/*
  Centralized helper for admin DataTables pages.
  Keeps per-page behavior (IDs/dom/columns) configurable without duplicating boilerplate.
*/

(function () {
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
    const table = initDataTable(cfg.tableSelector, cfg.dataTableOptions);
    bindSearch(cfg.searchInputSelector, table);
    return table;
  };
})();


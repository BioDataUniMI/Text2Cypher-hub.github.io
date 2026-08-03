document$.subscribe(function () {
  if (typeof Tablesort === 'undefined') return;
  document.querySelectorAll('article table:not([class]), article table.registry-summary').forEach(function (table) {
    new Tablesort(table);
  });
});

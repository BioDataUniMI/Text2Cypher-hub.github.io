(function () {
  function setupRegistry() {
    const search = document.querySelector('#registry-search');
    const curation = document.querySelector('#registry-kind');
    const count = document.querySelector('#registry-count');
    const table = document.querySelector('table.registry-summary');
    if (!search || !curation || !count || !table || table.dataset.registryReady) return;
    table.dataset.registryReady = 'true';

    const rows = Array.from(table.querySelectorAll('tbody tr'));

    function filterRegistry() {
      const query = search.value.trim().toLocaleLowerCase();
      const selected = curation.value.toLocaleLowerCase();
      let visible = 0;

      rows.forEach((row) => {
        const searchableText = `${row.textContent} ${row.dataset.registrySearch || ''}`.toLocaleLowerCase();
        const rowCuration = (row.dataset.registryCuration || '').toLocaleLowerCase();
        const matches = (!query || searchableText.includes(query)) && (!selected || rowCuration === selected);
        row.hidden = !matches;
        if (matches) visible += 1;
      });

      count.textContent = `${visible} of ${rows.length} datasets`;
    }

    search.addEventListener('input', filterRegistry);
    curation.addEventListener('change', filterRegistry);
    filterRegistry();
  }

  if (typeof document$ !== 'undefined') document$.subscribe(setupRegistry);
  else document.addEventListener('DOMContentLoaded', setupRegistry);
})();

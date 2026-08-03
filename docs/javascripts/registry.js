(function () {
  function setupRegistry() {
    const search = document.querySelector('#registry-search');
    const curation = document.querySelector('#registry-kind');
    const count = document.querySelector('#registry-count');
    const table = document.querySelector('table.registry-summary');
    if (!search || !curation || !count || !table || table.dataset.registryReady) return;
    table.dataset.registryReady = 'true';

    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const entries = new Map(
      Array.from(document.querySelectorAll('.registry-entry'))
        .map((entry) => [entry.dataset.registryId, entry])
    );

    function openDataset(id, scroll) {
      const entry = entries.get(id);
      if (!entry) return;
      entry.open = true;
      if (scroll) entry.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    table.addEventListener('click', function (event) {
      const link = event.target.closest('.registry-name-link');
      if (!link) return;
      event.preventDefault();
      const id = link.dataset.registryTarget;
      history.replaceState(null, '', link.getAttribute('href'));
      openDataset(id, true);
    });

    function filterRegistry() {
      const query = search.value.trim().toLocaleLowerCase();
      const selected = curation.value.toLocaleLowerCase();
      let visible = 0;

      rows.forEach((row) => {
        const entry = entries.get(row.dataset.registryId);
        const searchableText = `${row.textContent} ${entry ? entry.textContent : ''}`.toLocaleLowerCase();
        const rowCuration = (row.dataset.registryCuration || '').toLocaleLowerCase();
        const matches = (!query || searchableText.includes(query)) && (!selected || rowCuration === selected);
        row.hidden = !matches;
        if (entry) entry.hidden = !matches;
        if (matches) visible += 1;
      });

      count.textContent = `${visible} of ${rows.length} datasets`;
    }

    search.addEventListener('input', filterRegistry);
    curation.addEventListener('change', filterRegistry);
    filterRegistry();

    const hashMatch = location.hash.match(/^#(.+)-details$/);
    if (hashMatch) openDataset(hashMatch[1], false);
  }

  if (typeof document$ !== 'undefined') document$.subscribe(setupRegistry);
  else document.addEventListener('DOMContentLoaded', setupRegistry);
})();

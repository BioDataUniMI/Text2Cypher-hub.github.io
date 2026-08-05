(() => {
  const PAGE_SIZE = 10;
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  const init = (root) => {
    if (root.dataset.initialized) return;
    root.dataset.initialized = "true";
    const benchmarkId = root.dataset.benchmarkResource;
    const input = root.querySelector("[data-benchmark-search]");
    const status = root.querySelector("[data-benchmark-status]");
    const results = root.querySelector("[data-benchmark-results]");
    const previous = root.querySelector("[data-benchmark-previous]");
    const next = root.querySelector("[data-benchmark-next]");
    const page = root.querySelector("[data-benchmark-page]");
    let offset = 0;
    let timer;

    const load = async () => {
      status.textContent = "Loading examples…";
      const parameters = new URLSearchParams({
        offset: String(offset), limit: String(PAGE_SIZE), search: input.value.trim(),
      });
      try {
        const response = await fetch(`/api/benchmarks/${encodeURIComponent(benchmarkId)}/examples?${parameters}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to load benchmark examples.");
        results.innerHTML = data.examples.map((example) => `
          <article class="benchmark-example">
            <div class="benchmark-example-heading"><strong>#${example.document_id}</strong>${example.notes ? `<span>${escapeHtml(example.notes)}</span>` : ""}</div>
            <p>${escapeHtml(example.question)}</p>
            <pre><code>${escapeHtml(example.cypher)}</code></pre>
          </article>`).join("");
        if (!data.examples.length) results.innerHTML = "<p>No matching examples.</p>";
        const first = data.filtered_total ? data.offset + 1 : 0;
        const last = Math.min(data.offset + data.examples.length, data.filtered_total);
        status.textContent = `Showing ${first}–${last} of ${data.filtered_total} matching examples (${data.total} total).`;
        page.textContent = data.filtered_total ? `Page ${Math.floor(data.offset / PAGE_SIZE) + 1} of ${Math.ceil(data.filtered_total / PAGE_SIZE)}` : "";
        previous.disabled = data.offset === 0;
        next.disabled = data.offset + data.examples.length >= data.filtered_total;
      } catch (error) {
        status.textContent = error.message;
        results.innerHTML = "";
        previous.disabled = true;
        next.disabled = true;
      }
    };

    previous.addEventListener("click", () => { offset = Math.max(0, offset - PAGE_SIZE); load(); });
    next.addEventListener("click", () => { offset += PAGE_SIZE; load(); });
    input.addEventListener("input", () => {
      clearTimeout(timer);
      offset = 0;
      timer = setTimeout(load, 250);
    });
    load();
  };

  const start = () => document.querySelectorAll("[data-benchmark-resource]").forEach(init);
  document.addEventListener("DOMContentLoaded", start);
  if (typeof document$ !== "undefined") document$.subscribe(start);
})();

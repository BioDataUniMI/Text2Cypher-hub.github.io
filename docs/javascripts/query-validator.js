(() => {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const formatScore = (value) => value == null ? "N/A" : Number(value).toFixed(2);

  const renderMessages = (report) => {
    const messages = [
      ...(report.errors || []).map((item) => ({ kind: "error", text: item.message || item })),
      ...(report.warnings || []).map((item) => ({ kind: "warning", text: item.message || item })),
      ...((report.execution && report.execution.warnings) || []).map((item) => ({
        kind: "warning", text: item.description || item.title || item.message || item,
      })),
    ];
    if (!messages.length) return "";
    return `<div class="query-messages">${messages.map((item) => {
      const text = typeof item.text === "string" ? item.text : JSON.stringify(item.text);
      return `<div class="query-message query-message--${item.kind}"><strong>${item.kind === "error" ? "Error" : "Warning"}:</strong> ${escapeHtml(text)}</div>`;
    }).join("")}</div>`;
  };

  const renderOutput = (execution) => {
    if (!execution.attempted) return "<h3>Execution</h3><p>Not attempted because syntax validation failed.</p>";
    if (!execution.succeeded) return "<h3>Execution</h3><p>The query did not execute successfully.</p>";
    if (!execution.rows.length) return "<h3>Output</h3><p>Query executed successfully and returned no rows.</p>";
    const columns = execution.columns || Object.keys(execution.rows[0]);
    const head = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
    const body = execution.rows.map((row) => `<tr>${columns.map((column) => {
      const value = typeof row[column] === "string" ? row[column] : JSON.stringify(row[column]);
      return `<td><code>${escapeHtml(value)}</code></td>`;
    }).join("")}</tr>`).join("");
    return `<h3>Output</h3><p>${execution.returned_rows} row(s) returned${execution.truncated ? " (truncated)" : ""}.</p><div class="query-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  };

  const renderSimilar = (similar) => {
    if (!similar) return "";
    const warnings = (similar.warnings || []).map((warning) => `<div class="query-message query-message--warning"><strong>Warning:</strong> ${escapeHtml(warning)}</div>`).join("");
    const matches = similar.matches || [];
    const items = matches.length ? `<div class="query-similar-list">${matches.map((match, index) => `
      <article class="query-similar-item">
        <div class="query-similar-heading"><strong>#${match.rank} · ${escapeHtml(match.benchmark_name || match.benchmark_id || "Benchmark")} · document ${escapeHtml(match.document_id)}</strong><span>${(Number(match.similarity) * 100).toFixed(1)}%</span></div>
        <p><strong>Matched question:</strong> ${escapeHtml(match.question)}</p>
        <pre><code>${escapeHtml(match.cypher)}</code></pre>
        <div class="query-similar-actions">${match.notes ? `<small>${escapeHtml(match.notes)}</small>` : ""}<button class="md-button" type="button" data-use-similar="${index}">Use this Cypher</button></div>
      </article>`).join("")}</div>` : "<p>No indexed benchmark examples are available.</p>";
    return `<h2>Most similar benchmark questions</h2>
      <p class="query-similar-note">Top ${matches.length} across all associated benchmarks, encoded with <code>${escapeHtml(similar.model || similar.provider)}</code>.</p>
      ${warnings}${items}`;
  };

  const init = async (root) => {
    if (root.dataset.initialized) return;
    root.dataset.initialized = "true";
    const database = root.querySelector("[data-query-database]");
    const mode = root.querySelector("[data-query-mode]");
    const inputLabel = root.querySelector("[data-query-input-label]");
    const textarea = root.querySelector("[data-query-text]");
    const submit = root.querySelector("[data-query-submit]");
    const status = root.querySelector("[data-query-status]");
    const reportBox = document.querySelector("[data-query-report]");
    const validationBox = reportBox.querySelector("[data-query-validation]");
    const similarBox = reportBox.querySelector("[data-query-similar]");

    const updateMode = () => {
      const natural = mode.value === "natural";
      inputLabel.textContent = natural ? "Natural-language question" : "Cypher query";
      textarea.placeholder = natural
        ? "Which genes have a label that starts with MIR43?"
        : "MATCH (n) RETURN n LIMIT 10";
      submit.textContent = natural ? "Find similar queries" : "Validate and run";
      status.textContent = "";
    };
    mode.addEventListener("change", updateMode);
    updateMode();

    try {
      const response = await fetch("/api/databases");
      if (!response.ok) throw new Error("The database list is unavailable.");
      const data = await response.json();
      database.innerHTML = data.databases.map((item) => {
        const benchmarks = (item.benchmarks || []).map((entry) => `${entry.name} ${entry.version}`).join(", ");
        return `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}${benchmarks ? ` — ${escapeHtml(benchmarks)}` : ""}</option>`;
      }).join("");
      if (!data.databases.length) throw new Error("No database associated with a benchmark is available.");
      database.disabled = false;
      submit.disabled = false;
    } catch (error) {
      status.textContent = error.message;
      status.className = "query-validator-status query-validator-status--error";
    }

    submit.addEventListener("click", async () => {
      const value = textarea.value.trim();
      const natural = mode.value === "natural";
      if (!value) { status.textContent = natural ? "Enter a question." : "Enter a Cypher query."; return; }
      submit.disabled = true;
      status.textContent = natural ? "Searching associated benchmarks…" : "Validating and running…";
      status.className = "query-validator-status";
      reportBox.hidden = true;
      try {
        const response = await fetch(natural ? "/api/similar" : "/api/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(natural
            ? { database_id: database.value, question: value }
            : { database_id: database.value, query: value }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Request failed.");
        if (natural) {
          validationBox.hidden = true;
          similarBox.innerHTML = renderSimilar(data.similar_queries);
          similarBox.querySelectorAll("[data-use-similar]").forEach((button) => {
            button.addEventListener("click", () => {
              const match = data.similar_queries.matches[Number(button.dataset.useSimilar)];
              mode.value = "cypher";
              textarea.value = match.cypher;
              updateMode();
              root.scrollIntoView({ behavior: "smooth", block: "start" });
            });
          });
          status.textContent = `${data.similar_queries.matches.length} similar queries found.`;
        } else {
          validationBox.hidden = false;
          similarBox.innerHTML = "";
          const cyver = data.cyver;
          reportBox.querySelector("[data-query-scores]").innerHTML = [
            ["Syntax", formatScore(cyver.syntax.score), cyver.syntax.valid],
            ["Schema", formatScore(cyver.schema.score), cyver.schema.score === 1],
            ["Properties", formatScore(cyver.properties.score), cyver.properties.score === 1 || cyver.properties.score === null],
            ["KG valid", cyver.kg_valid ? "Yes" : "No", cyver.kg_valid],
          ].map(([label, score, valid]) => `<div class="query-score query-score--${valid ? "ok" : "bad"}"><span>${label}</span><strong>${score}</strong></div>`).join("");
          const metadata = escapeHtml(JSON.stringify({ syntax: cyver.syntax.metadata, schema: cyver.schema.metadata, properties: cyver.properties.metadata }, null, 2));
          reportBox.querySelector("[data-query-messages]").innerHTML = `${renderMessages(data)}<details><summary>CyVer details</summary><pre><code>${metadata}</code></pre></details>`;
          reportBox.querySelector("[data-query-output]").innerHTML = renderOutput(data.execution);
          status.textContent = data.execution.succeeded ? "Query executed." : "Validation completed with errors.";
        }
        reportBox.hidden = false;
      } catch (error) {
        status.textContent = error.message;
        status.className = "query-validator-status query-validator-status--error";
      } finally { submit.disabled = false; }
    });
  };

  const start = () => document.querySelectorAll("[data-query-validator]").forEach(init);
  document.addEventListener("DOMContentLoaded", start);
  if (typeof document$ !== "undefined") document$.subscribe(start);
})();

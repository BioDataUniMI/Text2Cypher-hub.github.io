(() => {
  const DISPLAY_ROW_LIMIT = 100;
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const formatScore = (value) => value == null ? "N/A" : Number(value).toFixed(2);
  const downloadJson = (value, filename) => {
    const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

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
    const displayRows = execution.rows.slice(0, DISPLAY_ROW_LIMIT);
    const head = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
    const body = displayRows.map((row) => `<tr>${columns.map((column) => {
      const value = typeof row[column] === "string" ? row[column] : JSON.stringify(row[column]);
      return `<td><code>${escapeHtml(value)}</code></td>`;
    }).join("")}</tr>`).join("");
    const displayNote = execution.rows.length > DISPLAY_ROW_LIMIT
      ? ` Showing the first ${DISPLAY_ROW_LIMIT}.`
      : "";
    return `<h3>Output</h3><p>${execution.returned_rows} row(s) returned.${displayNote} <button class="md-button" type="button" data-download-json>Download full result (JSON)</button></p><div class="query-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  };

  const PROMPT_MIN = 1;
  const PROMPT_MAX = 5;
  const PROMPT_DEFAULT = 3;
  const SAMPLE_ROW_LIMIT = 3;

  const formatSampleRows = (rows) => rows.length
    ? rows.slice(0, SAMPLE_ROW_LIMIT).map((row) => JSON.stringify(row)).join("\n")
    : "(no rows returned)";

  const buildPrompt = (matches, count, question, outputs) => {
    const examples = matches
      .slice(0, count)
      .map((match, index) => {
        const base = `Question: ${match.question}\nCypher: ${match.cypher}`;
        if (!outputs) return base;
        const sample = outputs[index];
        if (!sample) return base;
        const outputText = sample.error ? `(execution error: ${sample.error})` : formatSampleRows(sample.rows);
        return `${base}\nOutput:\n${outputText}`;
      })
      .join("\n\n");
    const intro = outputs
      ? `Based on the examples below that provide useful
patterns for querying the graph database (Neo4j outputs are also reported),
write a Cypher query that would answer the user's question.
Return only Cypher statement, no backticks, nothing else.`
      : `Based on the examples below that provide useful
patterns for querying the graph database,
write a Cypher query that would answer the user's question.
Return only Cypher statement, no backticks, nothing else.`;
    return `${intro}

Examples:
${examples}

Question: ${question}
Cypher query:`;
  };

  const renderPromptExport = (matches, question) => {
    if (!matches.length) return "";
    const max = Math.min(PROMPT_MAX, matches.length);
    const initial = Math.min(PROMPT_DEFAULT, max);
    const preview = escapeHtml(buildPrompt(matches, initial, question, null));
    return `<div class="query-prompt-export" data-query-prompt>
      <label for="query-prompt-count">Examples to include in prompt: <span data-query-prompt-count-label>${initial}</span></label>
      <input type="range" id="query-prompt-count" data-query-prompt-count min="${PROMPT_MIN}" max="${max}" step="1" value="${initial}">
      <label class="query-prompt-checkbox" for="query-prompt-outputs">
        <input type="checkbox" id="query-prompt-outputs" data-query-prompt-outputs>
        Include Neo4j query output (first ${SAMPLE_ROW_LIMIT} rows per example)
      </label>
      <textarea data-query-prompt-preview rows="8" spellcheck="false" readonly>${preview}</textarea>
      <div class="query-prompt-actions">
        <button class="md-button md-button--primary" type="button" data-query-prompt-copy>Copy LLM prompt</button>
        <span class="query-prompt-status" data-query-prompt-status role="status" aria-live="polite"></span>
      </div>
    </div>`;
  };

  const renderSimilar = (similar, question) => {
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
      ${warnings}${items}
      ${renderPromptExport(matches, question)}`;
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
        ? "How many entities are present in the database?"
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
      database.innerHTML = data.databases.map((item) =>
        `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`
      ).join("");
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
          similarBox.innerHTML = renderSimilar(data.similar_queries, data.question);
          similarBox.querySelectorAll("[data-use-similar]").forEach((button) => {
            button.addEventListener("click", () => {
              const match = data.similar_queries.matches[Number(button.dataset.useSimilar)];
              mode.value = "cypher";
              textarea.value = match.cypher;
              updateMode();
              root.scrollIntoView({ behavior: "smooth", block: "start" });
            });
          });
          const promptRoot = similarBox.querySelector("[data-query-prompt]");
          if (promptRoot) {
            const range = promptRoot.querySelector("[data-query-prompt-count]");
            const rangeLabel = promptRoot.querySelector("[data-query-prompt-count-label]");
            const preview = promptRoot.querySelector("[data-query-prompt-preview]");
            const copyButton = promptRoot.querySelector("[data-query-prompt-copy]");
            const promptStatus = promptRoot.querySelector("[data-query-prompt-status]");
            const outputToggle = promptRoot.querySelector("[data-query-prompt-outputs]");
            const matches = data.similar_queries.matches;
            let sampleOutputs = null;

            const refreshPreview = () => {
              preview.value = buildPrompt(matches, Number(range.value), data.question, outputToggle.checked ? sampleOutputs : null);
            };

            const loadOutputs = async () => {
              outputToggle.disabled = true;
              promptStatus.textContent = "Running examples on the database…";
              try {
                const response = await fetch("/api/run-samples", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ database_id: database.value, queries: matches.map((match) => match.cypher) }),
                });
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.detail || "Could not run the examples on the database.");
                sampleOutputs = payload.results;
                promptStatus.textContent = "";
              } catch (error) {
                sampleOutputs = null;
                outputToggle.checked = false;
                promptStatus.textContent = error.message;
              } finally {
                outputToggle.disabled = false;
                refreshPreview();
              }
            };

            range.addEventListener("input", () => {
              rangeLabel.textContent = range.value;
              refreshPreview();
            });
            outputToggle.addEventListener("change", () => {
              if (outputToggle.checked && !sampleOutputs) { loadOutputs(); } else { refreshPreview(); }
            });
            copyButton.addEventListener("click", async () => {
              try {
                await navigator.clipboard.writeText(preview.value);
                promptStatus.textContent = "Prompt copied to clipboard.";
              } catch (error) {
                preview.select();
                promptStatus.textContent = "Clipboard unavailable — text selected, press Ctrl/Cmd+C to copy.";
              }
            });
          }
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
          const downloadButton = reportBox.querySelector("[data-download-json]");
          if (downloadButton) {
            downloadButton.addEventListener("click", () => {
              downloadJson(
                { columns: data.execution.columns, rows: data.execution.rows },
                `query-result-${Date.now()}.json`
              );
            });
          }
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

# Query assistant

Choose a registered Neo4j database, then provide either a read-only Cypher query or a question in natural language.

- **Cypher query** validates the statement with CyVer and executes it against the selected database.
- **Natural-language question** searches all benchmark datasets associated with that database and returns the five semantically closest questions with their reference Cypher translations.

!!! warning "Read-only service"
    Only read Cypher queries are accepted. Execution results are limited to 100 rows and have a server-side timeout. Natural-language questions are never executed.

<div class="query-validator" data-query-validator>
  <label for="query-database">Database</label>
  <select id="query-database" data-query-database disabled>
    <option>Loading databases…</option>
  </select>

  <label for="query-mode">Input type</label>
  <select id="query-mode" data-query-mode>
    <option value="cypher">Cypher query</option>
    <option value="natural">Natural-language question</option>
  </select>

  <label for="query-text" data-query-input-label>Cypher query</label>
  <textarea id="query-text" data-query-text rows="10" spellcheck="false" placeholder="MATCH (n) RETURN n LIMIT 10"></textarea>

  <button class="md-button md-button--primary" type="button" data-query-submit disabled>Validate and run</button>
  <span class="query-validator-status" data-query-status role="status" aria-live="polite"></span>
</div>

<section class="query-report" data-query-report hidden aria-live="polite">
  <div data-query-validation>
    <h2>Validation report</h2>
    <div class="query-scores" data-query-scores></div>
    <div data-query-messages></div>
    <div data-query-output></div>
  </div>
  <div data-query-similar></div>
</section>

The **KG valid** result follows CyVer's definition: valid syntax, schema score equal to 1, and property score equal to 1 (or not applicable). Similarity percentages are cosine similarities computed with `sentence-transformers/all-mpnet-base-v2` over the natural-language `question` field.

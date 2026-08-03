# T2C-Registry

T2C-Registry describes each Text2Cypher dataset along with the materials needed to use and reproduce it: data files, graph instances, graph dumps, source code, papers and documentation.

Search the catalogue or filter by curation method.

<div class="registry-controls">
  <label for="registry-search">Search</label>
  <input id="registry-search" type="search" placeholder="Dataset, domain, material…" autocomplete="off">
  <label for="registry-kind">Curation</label>
  <select id="registry-kind">
    <option value="">All methods</option>
    <option value="Manually curated">Manually curated</option>
    <option value="LLM-assisted">LLM-assisted</option>
    <option value="Mixed">Mixed</option>
  </select>
  <span id="registry-count" aria-live="polite"></span>
</div>

{{ t2c_registry_summary }}
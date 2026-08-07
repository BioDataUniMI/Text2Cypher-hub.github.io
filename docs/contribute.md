# Contribute to T2C-Registry

Contributions are welcome through GitHub issues:

[Propose a resource](https://github.com/BioDataUniMI/Text2Cypher-hub.github.io/issues/new?template=new-resource.yml){ .md-button .md-button--primary }

## Requirements

- benchmark has to be hosted in a public, version-controlled repository;
- include, where possible, the code and configuration files required to reproduce the reported results;
- identify the dataset, data split, graph snapshot, and database version used for evaluation;
- clearly distinguish between LLM-assisted and manually curated data;
- remain open to corrections, extensions, and reuse by the community.

## Fastest way to get included

The quickest path to onboarding is to send a single JSON file: a flat list of entries, each with a `question`, a `cypher` query, and optional `notes` (e.g. the query's complexity level).

```json
[
  {
    "question": "Which genes are associated with breast cancer?",
    "cypher": "MATCH (g:Gene)-[:ASSOCIATED_WITH]->(d:Disease {name: 'breast cancer'}) RETURN g.name",
    "notes": "complexity: simple, single hop"
  },
  {
    "question": "How many pathways involve genes on chromosome 17?",
    "cypher": "MATCH (g:Gene {chromosome: '17'})-[:PART_OF]->(p:Pathway) RETURN count(DISTINCT p)",
    "notes": "complexity: medium, aggregation"
  }
]
```

Together with the JSON file, share the Neo4j connection details for the graph the queries run against:

- the **bolt endpoint** (e.g. `neo4j+s://host:7687`);
- the **database** name;
- **username** and **password** (a read-only account is preferred).

These map directly onto the `endpoint` block of a `databases` entry in [`docs/registry.yaml`](https://github.com/BioDataUniMI/Text2Cypher-hub.github.io/blob/main/docs/registry.yaml), so once received, adding the resource is a matter of registering the connection and dropping in the JSON file.
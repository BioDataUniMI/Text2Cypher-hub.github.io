# Evaluation guide

Text2Cypher evaluation is most useful when it separates *query similarity* from *correct execution behavior*. A generated query can resemble the reference query—or even parse and execute successfully—while still returning an incorrect result.

## Notation

Let:

- $Q_{\mathrm{gen}}$ be the generated Cypher query;
- $Q_{\mathrm{ref}}$ be the reference Cypher query;
- $\mathcal{R}_{\mathrm{gen}}$ be the execution output of $Q_{\mathrm{gen}}$;
- $\mathcal{R}_{\mathrm{ref}}$ be the execution output of $Q_{\mathrm{ref}}$.

## Recommended metric stack

| Name | Level | Description |
|---|---|---|
| Jaro–Winkler | Syntax | Character-level similarity between the generated and reference Cypher queries, with greater emphasis on matching prefixes. |
| Normalized Levenshtein | Syntax | Character-level similarity derived from the minimum number of insertions, deletions, and substitutions required to transform one query into the other. |
| Jaccard | Semantics | Intersection over union of the generated and reference execution outputs. |
| Coverage | Semantics | Fraction of reference results contained in the generated query output. |
| Pass@k | Semantics | Whether at least one of the top $k$ generated queries achieves complete Coverage. |

## Jaro–Winkler

Jaro–Winkler measures the character-level similarity between the generated and reference queries:

$$
S_{\mathrm{JW}}
=
\mathrm{JW}
\left(
Q_{\mathrm{gen}},
Q_{\mathrm{ref}}
\right)
$$

with:

$$
0 \leq S_{\mathrm{JW}} \leq 1.
$$

A score of $1$ indicates identical query strings, while lower values indicate increasing textual differences.

Jaro–Winkler is useful for determining whether the generated query follows a structure similar to the reference query, such as the expected `MATCH`, `WHERE`, and `RETURN` skeleton. Because it gives additional weight to common prefixes, it can particularly reward queries that begin with the same Cypher structure.

However, syntactic similarity does not imply semantic correctness. Two similar queries may use different relationships, filters, directions, or returned properties.

## Normalized Levenshtein

The Levenshtein distance measures the minimum number of single-character insertions, deletions, and substitutions required to transform the generated query into the reference query.

Let:

$$
d_{\mathrm{lev}}
\left(
Q_{\mathrm{gen}},
Q_{\mathrm{ref}}
\right)
$$

be the Levenshtein distance between the two query strings. The normalized Levenshtein similarity is defined as:

$$
S_{\mathrm{NL}}
=
1
-
\frac{
    d_{\mathrm{lev}}
    \left(
        Q_{\mathrm{gen}},
        Q_{\mathrm{ref}}
    \right)
}{
    \max
    \left(
        \left|Q_{\mathrm{gen}}\right|,
        \left|Q_{\mathrm{ref}}\right|
    \right)
}.
$$

with:

$$
0 \leq S_{\mathrm{NL}} \leq 1.
$$

A score of $1$ indicates identical query strings, while a score approaching $0$ indicates that a large number of edits is required to transform one query into the other.

If both query strings are empty, the similarity is conventionally defined as $1$ to avoid division by zero.

Unlike Jaro–Winkler, normalized Levenshtein does not give additional importance to common prefixes. It instead measures the overall amount of character-level editing required across the complete query.

For reproducibility, the same preprocessing should be applied to both queries before computing the metric. For example, an evaluation may normalize line endings and remove leading or trailing whitespace. Any additional normalization, such as collapsing repeated whitespace or converting keywords to uppercase, should be explicitly documented.

As with Jaro–Winkler, a high normalized Levenshtein similarity does not guarantee semantic correctness.

## Jaccard

Jaccard evaluates semantic similarity by comparing the execution outputs:

$$
J
=
\frac{
    \left|
        \mathcal{R}_{\mathrm{gen}}
        \cap
        \mathcal{R}_{\mathrm{ref}}
    \right|
}{
    \left|
        \mathcal{R}_{\mathrm{gen}}
        \cup
        \mathcal{R}_{\mathrm{ref}}
    \right|
}.
$$

A score of $1$ indicates that the generated and reference queries return the same results.

Before comparing the outputs:

- returned property names and Cypher aliases are ignored;
- result ordering is ignored unless the reference query explicitly contains an `ORDER BY` clause.

Jaccard penalizes both missing and additional results. Consequently, it may assign a score below $1$ when the generated query returns all the required information together with additional data.

For example, the generated query may use:

```cypher
RETURN n
```

while the reference query uses:

```cypher
RETURN n.property
```

The generated output contains the requested property, but it also contains additional node information.

## Coverage

Coverage measures the fraction of reference results contained in the generated output:

$$
C
=
\frac{
    \left|
        \mathcal{R}_{\mathrm{gen}}
        \cap
        \mathcal{R}_{\mathrm{ref}}
    \right|
}{
    \left|
        \mathcal{R}_{\mathrm{ref}}
    \right|
}.
$$

Unlike Jaccard, Coverage does not penalize additional information returned by the generated query.

This makes Coverage useful when $Q_{\mathrm{gen}}$ returns a richer representation of the expected result. For example, returning an entire node or relationship can still achieve complete Coverage when $Q_{\mathrm{ref}}$ requests only one of its properties.

Coverage is also referred to as *execution accuracy* in parts of the Text2Cypher literature.

## Pass@k

Suppose that the system generates $k$ candidate queries:

$$
Q_{\mathrm{gen}}^{(1)},
Q_{\mathrm{gen}}^{(2)},
\ldots,
Q_{\mathrm{gen}}^{(k)}.
$$

Let $C_i$ be the Coverage achieved by the $i$-th candidate. Pass@k is defined as:

$$
P_k
=
\begin{cases}
1, & \text{if } \displaystyle\max_{1 \leq i \leq k} C_i = 1, \\
0, & \text{otherwise}.
\end{cases}
$$

Therefore, Pass@k is equal to $1$ when at least one of the top $k$ generated queries achieves complete semantic coverage.

For a benchmark containing $N$ questions, the final Pass@k score is:

$$
\overline{P}_k
=
\frac{1}{N}
\sum_{j=1}^{N}
P_{k,j}.
$$

For systems producing only one query per question, Pass@1 is defined as:

$$
P_1
=
\begin{cases}
1, & \text{if } C = 1, \\
0, & \text{otherwise}.
\end{cases}
$$

A query therefore passes only when its output completely covers the reference output.
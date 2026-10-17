# Card format

Each card starts with a strict JSON object between `---` lines, then a nonempty Markdown body. UTF-8 and LF newlines are required. Duplicate JSON keys, unknown fields, missing required fields and incorrect types fail validation. This is not a general YAML parser. See the full metadata shapes in [knowledge.schema.json](knowledge.schema.json) and [source.schema.json](source.schema.json); the CLI enforces the small documented JSON Schema vocabulary plus cross-card semantic checks.

Formal research cards must be based on selected and read public sources; their lifecycle and replication status remain separate from that source check. Complete **synthetic, non-scientific** format examples live in [knowledge fixtures](../tests/fixtures/knowledge/K-900001.md) and [source fixture](../tests/fixtures/sources/S-900001.md). Keep these examples outside the formal directories; do not copy them into the formal collection as research content.

## Knowledge metadata

Required: `schema_version=1`, `kind="knowledge"`, `id`, `title`, `version`, `example`, `summary`, `lifecycle`, `evidence`, `tags`, `aliases`, `conditions`, `limitations`, `review_after`, `sources`, `relations`.

- `tags`: nonempty arrays for `domains`, `methods`, `problems`; multi-domain cards share one body.
- `aliases`: nonempty `zh` and `en` arrays. Use honest descriptive translations when a standard alias does not exist, and explain uncertainty in the body.
- `evidence`: `strength` is `unassessed`, `reported` or `corroborated`; `replication` is `not_attempted`, `partial`, `reproduced` or `failed`; `note` explains the basis and limits. These are independent of lifecycle.
- `lifecycle`: `draft`, `active` or `superseded`. `review_after` is the last date eligible for default current retrieval (UTC). A reviewer changes lifecycle; a relationship never changes it automatically.
- `sources`: nonempty list of `{id, version, locator, role}`. The source's current version and named locator must match exactly. An archived Git commit preserves previous versions.
- `relations`: possibly empty list of `{type, target, reason, conditions, evidence, verification}`. Conditions/evidence cannot be empty. Evidence uses the same citation shape. Verification is `unverified`, `checked`, or `rejected`; the graph returns all with labels for human review. Types are `depends_on`, `supports`, `limits`, `conflicts_with`, `supersedes`, `transfer_to`.

The body should provide stable, descriptive headings for explanation, applicability, limitations and source discussion. Agents cite actual headings returned by `read_card`; the system does not fabricate section identifiers. Changing substantive meaning requires a version update and PR explanation; file renames keep the same ID. Deletion must repair all references in the same PR. Deleted IDs must never be reused (Git history is the allocation audit trail).

## Source metadata

Required: `schema_version=1`, `kind="source"`, `id`, `title`, `version`, `example`, `source_type`, `authors`, `original_url`, `version_url`, `version_note`, `accessed`, `locators`.

- `source_type`: `paper`, `documentation`, `dataset`, `synthetic`. Synthetic sources must have `example=true`. Formal content cannot cite or link to example data.
- `original_url`: canonical original HTTPS link. `version_url`: link identifying the exact version, preferably immutable. `version_note`: explain the version selection, identifier and any immutability limitation. A source version string alone is not evidence that its remote content is immutable or checked.
- `authors`: real authors/organization for formal sources. `accessed`: actual access date. The system validates completeness, not scientific accuracy or remote availability; reviewers must verify these.
- `locators`: nonempty mapping from stable local locator key to the actual page/section/theorem/figure/URL fragment. Cite no page number unless verified against the exact version. For unpaginated sources use a true heading or other exact locator.

The body describes bibliographic details, scope, version limitations and why a source was selected. Store only permitted short excerpts or your own summaries; do not copy restricted full papers. A source card is metadata and context, not a claim that the source is scientifically correct or replicated.

## Build inputs

`input_version` covers source Markdown paths+bytes and the build implementation/schemas. `index.json` contains the input manifest and reverse typed relations. Index artifacts contain no authored research content. Files outside `knowledge/` and `sources/` (including this document and all fixtures) are never silently imported as formal knowledge.

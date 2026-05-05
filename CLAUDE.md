# ClassApp Technical Wiki — LLM Schema

This file defines the structure, conventions, and workflows for maintaining the ClassApp technical knowledge base. Read this at the start of every session.

---

## Purpose

This wiki is a persistent, compounding technical knowledge base for the ClassApp project. It captures architecture, components, design decisions, and accumulated understanding — synthesized from source documents, code exploration, and conversation. The LLM maintains it; the human curates and directs.

---

## Directory Structure

```
ClassApp/
├── CLAUDE.md          ← this file
├── index.md           ← catalog of all wiki pages (update on every ingest)
├── log.md             ← append-only chronological record
├── overview.md        ← evolving high-level synthesis of the project
├── components/        ← one page per module, class, feature, or API
├── concepts/          ← design patterns, decisions, algorithms, principles
├── sources/           ← one summary page per ingested document
└── raw/               ← immutable source documents (never modify)
```

### What goes where

| Category | Directory | Examples |
|---|---|---|
| Module, class, feature, endpoint | `components/` | `Auth.md`, `DatabaseLayer.md`, `UserAPI.md` |
| Pattern, decision, principle, algorithm | `concepts/` | `MVCPattern.md`, `SessionStrategy.md` |
| Ingested doc summary | `sources/` | `DesignSpec_v1.md`, `FastAPI_Docs.md` |
| High-level synthesis | root | `overview.md` |

---

## Page Format

Every wiki page (except `index.md` and `log.md`) uses this frontmatter:

```yaml
---
type: component | concept | source | overview
tags: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Cross-references
Use Obsidian wikilinks: `[[PageName]]`. Always link to related pages — this is what makes the graph view useful.

### Page body conventions
- Lead with a one-paragraph summary of what this page is about.
- Use `## Section` headings to organize content.
- End every page with a `## Related` section listing wikilinks to connected pages.

---

## Workflows

### Ingest

When the user provides a new source document:

1. Read the source in full.
2. Discuss key takeaways with the user — ask what to emphasize.
3. Write a summary page in `sources/` (named after the document).
4. Identify components and concepts mentioned — update or create pages in `components/` and `concepts/`.
5. Update `overview.md` if the source changes the big picture.
6. Update `index.md` — add all new/modified pages.
7. Append an entry to `log.md`.

A single source may touch 5–15 wiki pages. That's expected.

### Query

When the user asks a question:

1. Read `index.md` to find relevant pages.
2. Read those pages in full.
3. Synthesize an answer with inline citations (e.g. `([[ComponentName]])`).
4. If the answer is substantive and reusable, offer to file it as a new page in `concepts/`.

### Lint

When the user asks for a health check:

1. Scan all pages for: broken wikilinks, orphan pages (no inbound links), contradictions between pages, stale claims superseded by newer sources, concepts mentioned but lacking their own page.
2. Report findings as a prioritized list.
3. Suggest new questions to investigate or sources to seek out.

---

## Naming Conventions

- File names: `PascalCase.md` for components and concepts, `SourceTitle.md` for sources.
- No spaces in file names (Obsidian wikilinks work best without them).
- Keep names specific and stable — renaming a file breaks wikilinks.

---

## index.md Format

Group entries by category. Each entry: `- [[PageName]] — one-line description`.

Update the index on every ingest. Do not let it fall out of sync.

## log.md Format

Append-only. Each entry starts with `## [YYYY-MM-DD] <type> | <title>` where type is `ingest`, `query`, or `lint`. Follow with 2–4 bullet points summarizing what happened.

---
name: context7
description: Pull version-accurate library, framework and API documentation into context through the Context7 MCP server or the ctx7 CLI, instead of recalling signatures from training data when writing a fix, a payload, or an integration
---

# Context7 — Version-Accurate Library Docs

Use Context7 when the answer depends on an exact API shape for a specific
library version — a signature, a config key, a renamed option, a migration
step. Recalled-from-memory API details are the most common source of a fix
that looks right and does not compile, or a payload that targets an endpoint
that no longer exists in the version under test.

Upstream: [context7.com](https://context7.com) ·
[github.com/upstash/context7](https://github.com/upstash/context7) (MIT).

## Two Ways In

**MCP (preferred when already configured).** Strix connects to Context7 as an
MCP server and exposes two tools:

- `resolve-library-id` — `libraryName` plus a `query`; returns candidate IDs
  ranked by relevance to the query.
- `query-docs` — `libraryId` plus a `query`; returns the matching docs.

Endpoint `https://mcp.context7.com/mcp`. A free API key from
[context7.com/dashboard](https://context7.com/dashboard) raises rate limits
and is passed as a bearer header.

**CLI (no MCP client needed).** `ctx7` requires Node.js 18+:

```bash
npx ctx7@latest library supabase "row level security policy examples"
npx ctx7@latest docs /supabase/supabase "RLS policy for per-tenant reads"
npx ctx7@latest setup --mcp      # wire it into a coding agent
npx ctx7@latest setup --cli      # install the CLI + skill flow instead
npx ctx7@latest whoami           # login state
```

Library IDs are slash paths: `/supabase/supabase`, `/vercel/next.js`,
`/mongodb/docs`. If the ID is already known, skip the resolve step — it saves
a round trip and the ambiguity of a name match against several packages.

## Wiring It Into Strix

Add an entry to `~/.strix/mcp-servers.json` (see the MCP docs page for the
full field list):

```json
[
  {
    "name": "context7",
    "transport": "http",
    "url": "https://mcp.context7.com/mcp",
    "auth": { "kind": "bearer", "token": "<CONTEXT7_API_KEY>" },
    "notes": "Version-accurate library docs. Resolve an ID, then query it for the exact API shape before writing a patch."
  }
]
```

Namespaced tool names become `context7_resolve-library-id` and
`context7_query-docs`. A key is not strictly required — the anonymous tier
just answers less before rate limiting.

## When To Reach For It

- Writing or reviewing a fix that calls a third-party API (`create_agent`
  with `fix_verification` inlined, then this).
- Checking whether a vulnerable option was deprecated, renamed, or defaulted
  differently across two versions of the same package.
- Confirming the current recommended pattern for a control you are about to
  claim is missing — a missing `SameSite`, a non-constant-time compare, a
  framework helper that already exists.
- Establishing the *intended* behaviour before calling a deviation a bug.

Skip it when the question is about the target's own code (read the code), the
framework's live behaviour (drive it with the browser skill), or a general
security concept (the vulnerability skills cover that).

## Pitfalls

- **Community-contributed content.** Indexed docs ship from project owners and
  the community; a page can lag a release. Cross-check anything security
  critical against the version actually installed (`pip show`, `npm ls`,
  lockfile, container image tag) and say which version the guidance came from.
- **Never put secrets in a query.** Prompts and library names leave the
  machine. Keep tokens, internal hostnames, and customer data out of queries.
- **Be specific.** A short, well-scoped question returns usable snippets; a
  vague one returns generic prose and burns context.
- Absence is not evidence. "The docs do not mention rate limiting" does not
  mean rate limiting is absent — confirm against the running system.

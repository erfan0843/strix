---
name: secure_stack_loop
description: End-to-end loop for building and re-verifying a Supabase-backed web application with Strix — pull exact library docs, write RLS-first backend code, keep the UI baseline, prove behaviour in a real browser, then re-run Strix to confirm
---

# Secure Stack Loop

The coordination skill for work that spans all four tools: documentation
(Context7), backend (Supabase CLI + MCP), interface (`ui_skills`), browser
evidence (`playwright_cli`) — closed by a Strix re-scan. Use it when a finding
turns into code changes, when a target is being stood up for testing, or when a
fix has to be shown working rather than asserted.

Strix itself: [strix.ai](https://www.strix.ai) ·
[github.com/usestrix/strix](https://github.com/usestrix/strix).

## The Loop

**0. Scope and authorization first.** Confirm the target, the environment
(staging or local, never an unowned host), what is out of bounds (payments,
deletes, mass mail), and whether credentials exist for two identities. No
credentials means no authorization proof — collect them before writing code.

**1. Get the exact API shape.** `context7` — resolve the library ID, query it
for the specific call you are about to write, and record the version you
verified against. This is the step that stops a "fix" from being written
against a signature that does not exist.

**2. Write the code with secure defaults on.** `supabase_cli` for schema,
migrations, RLS policies, function `search_path`, storage policies, and secret
handling; `ui_skills` for anything user-facing. The database defaults are not
negotiable during a fix: a new table ships with RLS enabled and per-operation
policies in the same migration, or it does not ship.

**3. Verify the backend objectively.**

```bash
supabase db lint --local --level warning --fail-on warning
supabase db advisors --local --type security --level warn --fail-on warn
supabase test db
```

Zero advisories is the floor. Then check the invariants the advisors cannot
see — every policy against the tenant model, every `SECURITY DEFINER` function
against its caller.

**4. Prove it in a browser.** `playwright_cli` — replay the exact flow that
produced the finding, with saved storage states for the identities involved,
and capture the before/after pair. A status code is not evidence; the rendered
result for each identity is. `recording-stop` converts the flow into Playwright
code for the report, `tracing-stop` packages the trace.

**5. Re-run the security checks that apply.** The `supabase` skill for policy
and key exposure, plus the vulnerability skills matching the finding
(`idor`, `broken_function_level_authorization`, `xss`, ...). Re-run the original
proof of concept against the patched system and state precisely which step now
fails.

**6. Re-scan with Strix.** Close the loop with the scanner that found it:

```bash
strix -n -t ./ --scan-mode quick --max-budget 10      # local source review
strix -n -t https://staging.example.com --max-budget 20
```

Exit codes in headless mode: `0` clean, `1` fatal error, `2` vulnerabilities
found. A `0` covers only what was analyzed — check
`strix_runs/<run-name>/run.json` (`status`, `llm_usage.cost` against the
budget) before calling a run clean. Artifacts land in `strix_runs/<run-name>/`:
`penetration_test_report.md`, `vulnerabilities/*.md`, `vulnerabilities.json`,
`findings.sarif`, `run.json`.

No Docker locally, or CI/sandboxed environment? The managed platform takes the
same task: `strix cloud login`, then `strix cloud scans start ...` with a
reviewed source digest.

## Rules That Keep The Loop Honest

- **One change at a time, verified.** Docs → code → browser proof → re-scan.
  Do not batch four fixes and one verification pass.
- **Evidence travels with the claim.** Every "fixed" statement names the
  command, the identity, and the artifact that shows it.
- **Secrets stay out of the loop's outputs.** Storage-state files, tokens,
  `.env` contents, MCP keys, and production data do not reach the report or a
  third-party query.
- **Scope never widens on its own.** A tool that makes a step easy (a CLI
  `push`, an MCP write tool, a browser session) is still bound by the
  authorization established in step 0.
- **Stop and report** when a step needs a human — DNS changes, payments,
  production writes, plan upgrades.

## When Not To Use This

Pure reconnaissance of an unfamiliar target (use `asset_discovery` and the
recon skills), a black-box assessment where no code changes are in scope (use
`web-app-penetration-testing`), or a single isolated finding with no fix
attached. This skill is for the build-and-prove cycle, not for exploration.

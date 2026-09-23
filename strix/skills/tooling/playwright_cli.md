---
name: playwright_cli
description: Drive headless Chrome through the Playwright agent CLI for authorized testing and fix verification — ref-based snapshots, named sessions, saved storage state, request inspection, route mocking, console reading, tracing and codegen from recorded actions
---

# Playwright Agent CLI

A command-line browser driver built for agents: short-lived commands against a
persistent daemon, accessibility snapshots with element refs instead of raw
HTML, and sessions that keep cookies and storage between calls.

Upstream: [playwright.dev/agent-cli](https://playwright.dev/agent-cli/introduction) ·
[github.com/microsoft/playwright-cli](https://github.com/microsoft/playwright-cli).
Requires Node.js 18+.

```bash
npm install -g @playwright/cli@latest
playwright-cli --version
playwright-cli install --skills          # writes the skill for your coding agent
playwright-cli install-browser chromium  # browser binary; add --with-deps for system libs
```

Headless by default; `--headed` on `open` shows the window. Run everything
through `exec_command`.

## The Loop

Every interaction is ref-based, and refs are regenerated on each snapshot:

```bash
playwright-cli open https://target.example/login
playwright-cli snapshot                 # elements carry refs: e12, e21, ...
playwright-cli fill e12 "user@example.com"
playwright-cli fill e15 "hunter2"
playwright-cli click e19
playwright-cli snapshot                 # re-snapshot: the old refs are stale
playwright-cli screenshot --filename=after-login.png
playwright-cli close
```

Cheaper variants when the page is large:
`snapshot --depth=N` to cap the tree, `snapshot <ref>` to snapshot one
subtree, `find "checkout"` / `find --regex "..."` to search the snapshot for a
node without dumping it.

Refs are positional, not selectors. `e21` means "node 21 of the last
snapshot" — after any navigation or re-render, re-snapshot before the next
click instead of reusing a stale ref.

## Sessions And Storage State

State lives in memory per session and dies with the browser:

```bash
playwright-cli open https://app.example --persistent   # keep the profile on disk
playwright-cli -s=victim  open https://app.example     # named session
playwright-cli -s=attacker open https://app.example    # parallel session
playwright-cli list
playwright-cli state-save tenant_b.json                # cookies + storage to a file
playwright-cli state-load tenant_a.json                # restore an authenticated identity
playwright-cli close-all                               # or kill-all, forcefully
```

`PLAYWRIGHT_CLI_SESSION=<name>` sets the session for a whole shell. A headless
session exits on its own after an hour idle; `open --idle-timeout=<ms>`
changes that, `0` disables it.

Saved state files are credentials in plain text. Keep them out of the report,
never commit them, and delete them when the run ends.

## Command Groups You Will Actually Use

**Core:** `open`, `goto`, `type`, `fill` (`--submit` presses Enter), `click`,
`dblclick`, `hover`, `select`, `check`/`uncheck`, `upload`, `drag`, `drop`
(`--path=` or `--data=`), `dialog-accept [prompt]` / `dialog-dismiss`,
`resize <w> <h>`, `eval <func> [ref]`.

**Tabs and navigation:** `go-back`, `go-forward`, `reload`, `tab-list`,
`tab-new`, `tab-select`, `tab-close`.

**Network:** `requests` lists numbered requests since load; `request <n>`,
`request-headers <n>`, `request-body <n>`, `response-headers <n>`,
`response-body <n>` drill into one. `route <pattern>` mocks matching requests,
`route-list`, `unroute`, `network-state-set offline|online`.

**Console and code execution:** `console [min-level]`, `run-code <snippet>`,
`generate-locator <ref>`, `highlight`.

**Evidence and replay:** `tracing-start` / `tracing-stop`,
`recording-start` / `recording-stop` (recorded user actions print as Playwright
code — paste that into a regression test), `video-start` / `video-stop`,
`video-show-actions`, `pause-at` / `resume` / `step-over` for stepping through
a flow.

**Emulation:** `set-color-scheme`, `set-reduced-motion`, `set-forced-colors`,
`set-contrast`, `set-media` (and the matching `clear-*`). Directly useful when
a finding is "this control is indistinguishable at high contrast" or "the
animation ignores reduced motion".

**WebMCP:** `webmcp-list` lists the WebMCP tools a page registers — the fastest
way to enumerate the tool surface an in-browser agent exposes.

`--json` and `--raw` on any command give machine-parseable output.

## Patterns For Security Work

- **Prove an authorization boundary, not just a status code.** Save one
  storage state per identity (`state-save`), reload the same URL with each,
  and diff what actually renders. A 200 with an empty shell is not access.
- **Verify a fix where it was broken.** After patching, replay the exact flow
  that produced the finding and capture the before/after pair; a fix that
  cannot be shown to change browser-observable behaviour is unproven.
- **Catch what the proxy alone cannot.** `dialog-accept` for script-triggered
  dialogs, `console` for client-side errors leaking data, `eval` for DOM
  state, `route` to simulate a hostile upstream.
- **Reproduce deterministically.** `recording-stop` gives the flow as
  Playwright code for the report, and `tracing-stop` packages the full trace
  as evidence.

## Guardrails

- Only drive targets the user is authorized to test. Browser actions are real
  actions: a click can delete a record.
- No destructive or irreversible steps (payments, deletes, mass emails) without
  explicit approval.
- Clean up sessions (`close-all` / `kill-all`) and storage-state files before
  finishing a run.
- This is complementary to the `agent_browser` skill, which is pre-installed in
  the sandbox and wired to the Caido proxy. Use `agent_browser` for fast
  crawl-and-inspect passes that should land in the intercepting proxy; use
  `playwright-cli` when you need saved identities, request/response bodies,
  emulation, tracing, or recorded flows converted to code.

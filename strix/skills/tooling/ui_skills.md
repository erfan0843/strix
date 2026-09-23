---
name: ui_skills
description: Design-engineering skill registry for frontend work — fetch UI skills and DESIGN.md evidence over the ui-skills CLI or MCP, and apply the Baseline UI constraint set when writing or remediating interface code
---

# UI Skills — Design Engineering Registry

Frontend code written during a security fix or a rebuild is still production
code. This skill is the design-quality baseline to follow while writing it, and
the registry to pull a deeper, topic-specific skill from when the task is
bigger than a patch.

Upstream: [ui-skills.com](https://www.ui-skills.com/) ·
[github.com/ibelick/ui-skills](https://github.com/ibelick/ui-skills) (MIT).
Registry content is community-contributed — by Anthropic, shadcn, Emil
Kowalski, Antfu, and others — so read a fetched skill before applying it, and
keep it consistent with the repository you are editing.

## Access

**CLI** (Node.js 18+):

```bash
npx ui-skills start                       # the routing skill: pick by topic/stack/intent
npx ui-skills categories                  # list categories (motion, accessibility, ...)
npx ui-skills list --category motion
npx ui-skills get baseline-ui             # print one skill's full markdown
npx ui-skills get ui-skills-root
```

**MCP:** endpoint `https://www.ui-skills.com/mcp` (server card at
`/.well-known/mcp/server-card.json`), tools `list_skills` (optional query over
path, name, or description) and `get_skill` (by discovery name, slug, or
pathSlug). No auth, so it drops straight into Strix's MCP config:

```json
[
  {
    "name": "ui_skills",
    "transport": "http",
    "url": "https://www.ui-skills.com/mcp",
    "allowed_tools": ["list_skills", "get_skill"],
    "notes": "Design-engineering skill registry. Fetch the topic-specific skill before writing frontend code."
  }
]
```

Alongside the skills, the site publishes **DESIGN.md** files (Vercel, Atlassian,
Mintlify, UNICEF) documenting a product's real type scale, colour tokens,
spacing and component rules. If the project already has a `DESIGN.md`, that file
outranks any generic skill here — read it first and follow it.

## Baseline UI — The Constraints To Hold While Writing Code

These are condensed from the registry's MIT-licensed `baseline-ui` skill
(upstream: `github.com/ibelick/ui-skills`) so the constraints are available
without a network call. Re-fetch the original when exact wording matters.
They exist to stop
AI-generated interface slop: inconsistent spacing, gratuitous motion, and
hand-rolled interactive behaviour that breaks keyboard and screen-reader users.

**Stack**

- Tailwind CSS defaults unless custom values exist or are requested.
- `motion/react` (formerly `framer-motion`) when JavaScript animation is
  required; `tw-animate-css` for entrance and micro animations.
- `cn` (`clsx` + `tailwind-merge`) for class logic.

**Components**

- Accessible component primitives for anything with keyboard or focus
  behaviour (`Base UI`, `React Aria`, `Radix`) — and the project's existing
  primitives first.
- Never mix primitive systems within one interaction surface.
- `aria-label` on icon-only buttons; never rebuild keyboard or focus behaviour
  by hand.

**Interaction**

- `AlertDialog` for destructive or irreversible actions.
- Structural skeletons for loading states.
- `h-dvh`, not `h-screen`; respect `safe-area-inset` for fixed elements.
- Errors render next to the action that caused them; never block paste in
  `input`/`textarea`.

**Animation**

- No animation unless requested; animate only compositor properties
  (`transform`, `opacity`), never layout properties; avoid animating paint
  properties except in small local UI.
- `ease-out` on entrance, interaction feedback under 200ms, looping animations
  paused off-screen, `prefers-reduced-motion` respected, no custom easing
  curves.

**Typography**

- `text-balance` on headings, `text-pretty` on body copy, `tabular-nums` for
  data, `truncate`/`line-clamp` for dense UI, no `tracking-*` changes unless
  requested.

**Layout and design**

- Fixed `z-index` scale, no arbitrary values; `size-*` for square elements.
- No gradients (and never purple or multicolor ones) unless requested; no glow
  as a primary affordance; default Tailwind shadow scale.
- Empty states get one clear next action; one accent colour per view; existing
  theme tokens before new ones.

**Performance**

- Never animate large `blur()` or `backdrop-filter` surfaces; no `will-change`
  outside an active animation; no `useEffect` for something render logic can
  express.

## How This Connects To Security Work

- Interactive controls written without accessible primitives end up with
  hand-rolled focus and keyboard handling — the same code that usually fails to
  gate the action it exposes. Fixing accessibility and fixing the authorization
  check are often the same edit.
- A design system that already defines tokens, dialogs, and error placement
  gives the reviewer a reference to diff against: a UI that ignores it is where
  unreviewed ad-hoc components and unvalidated inputs accumulate.
- `set-reduced-motion`, `set-contrast` and `set-forced-colors` in the
  `playwright_cli` skill let you verify these constraints in a real browser
  rather than by reading the diff.

## Workflow

1. Match the stack first — if the repo is not Tailwind-based, apply the
   principles (states, contrast, motion budget, typography) without importing
   Tailwind-specific class names.
2. Fetch the smallest relevant skill (`npx ui-skills get baseline-ui`, or
   `list_skills` filtered by topic) rather than several at once.
3. When auditing existing UI, quote the exact line, state why it
   matters in one sentence, and give a code-level fix — the same
   evidence discipline the security skills ask for.
4. Re-check anything user-facing you changed in a browser before calling it
   done.

## Pitfalls

- Community skills encode their authors' opinions and stacks. Apply the parts
  that fit the project; do not restructure an existing design system around one.
- Design polish is not a security control. Do not let a UI pass substitute for
  the authorization, input handling, and output-encoding checks.
- Do not paste proprietary design files or internal screenshots into a
  third-party MCP query.

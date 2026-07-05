---
type: folder-index
folder: personas
title: "Personas"
version: "3.0"
purpose: "Optional, cross-domain persona context for personalized AI behavior"
last_updated: "2026-07-05"
---

# Personas

This layer is optional.

Use it to store persona context that should apply across all knowledge topics in this wiki (health, law, finance, and future domains).

It can include:

- Real user profiles (preferences, goals, communication style)
- Shared profiles for teams or organizations
- Fictional personas for role-based reasoning and alternative viewpoints

---

## Folder Structure

```
personas/
│
├── INDEX.md                              <- This file
├── _templates/                           <- Templates (do not edit)
│   ├── persona_template.md
│   └── history_template.md
│
├── me/                                   <- Personal profile
│   ├── persona.md                        <- Preferences, goals, values, context
│   └── history.md                        <- Optional background facts
│
├── person_{name_or_id}/                  <- Real person profile
│   ├── persona.md
│   └── history.md
│
├── team_{name}/                          <- Shared team profile
│   ├── persona.md
│   └── history.md
│
└── fictional_{persona_name}/             <- Fictional role/persona
    ├── persona.md
    └── history.md
```

---

## Naming Convention

Use lowercase snake_case for folder names.

Suggested patterns:

- `me`
- `person_<name_or_id>`
- `team_<name>`
- `fictional_<persona_name>`

---

## What A Persona Should Contain

Minimum recommended fields in `persona.md`:

- Identity: display name, role, language, region/timezone
- Communication style: concise vs detailed, tone, preferred format
- Priorities: top goals, decision criteria, what matters most
- Constraints: hard limits, legal/ethical boundaries, no-go topics
- Preferences: tools, workflows, output style, citation expectations
- Viewpoints and values: optional ideological, political, or strategic positions to simulate
- Relevance filters: what is personally relevant vs noise

---

## Agent Behavior Rules

When a persona is active, agents should:

1. Load `persona.md` first.
2. Apply communication and relevance preferences across all domains.
3. Keep evidence and uncertainty explicit, even when adopting a viewpoint.
4. Separate facts from persona-based interpretation.
5. Avoid mixing data between personas.
6. Default to neutral behavior when persona instructions are missing.

If multiple personas are loaded, define a primary persona and list conflict-resolution rules explicitly.

---

## Fictional Persona Use

Fictional personas are valid and useful for:

- Scenario analysis (different stakeholder views)
- Red-team and challenge perspectives
- Writing or simulation tasks
- Comparing policy or strategy options from multiple positions

Mark fictional personas clearly in `persona.md` so they are never confused with real users.

---

## Privacy And Safety Guidance

- Store only necessary personal data.
- Prefer pseudonyms or IDs when possible.
- Keep sensitive data separated and access-controlled.
- Do not treat persona preferences as objective truth.
- Never present harmful or illegal instructions as acceptable behavior.

---

## Quick Session Protocol

1. Identify active persona folder.
2. Read `persona.md` (and `history.md` if relevant).
3. Confirm output style, depth, and relevance filters.
4. Generate answer with clear evidence references.
5. If new stable preferences emerge, update persona files.

---

## Active Profiles (Optional Table)

| Profile | Type | Persona File | Last Updated |
|--------|------|--------------|--------------|
| me | real | yes | 2026-07-05 |

Maintain this table manually if helpful.


---
name: writing-minxg-skills
description: How to write, test, and publish a MINXG skill — a markdown instruction bundle the agent can load, with no executable code involved.
version: 1.0.0
author: minxg-core
tags: [development, skills, meta]
category: development
---

# Writing MINXG Skills

A skill is a `SKILL.md` file: YAML frontmatter plus markdown body. It's
read by the model as instructions — never executed — which is the main
reason it's safer to install from a third party than an extension is.

## When to use this

Package up a repeatable procedure — a checklist, a house style, a
domain workflow — so any MINXG session can load it instead of you
re-explaining it every time.

## Steps

1. Scaffold one:
   ```
   minxg skill new my-skill --description "what it teaches the agent to do"
   ```
   This creates `~/.minxg/skills/user/my-skill/SKILL.md` from a
   template with the required frontmatter fields already filled in
   (`name`, `description` are mandatory; `version`, `author`, `tags`,
   `category` are optional but recommended).

2. Fill in the body: concrete steps, not vague goals. Write it the way
   you'd brief a competent colleague who has never done this task —
   include the commands, the file paths, the gotchas, in the order
   they actually happen.

3. Try it:
   ```
   minxg skill view my-skill
   minxg skill list --category user
   ```

4. When you're happy with it and ready to share:
   ```
   minxg skill publish my-skill
   ```
   This validates the frontmatter, checks for anything that looks like
   an accidentally-embedded secret (API keys, private key blocks), and
   prints a ready-to-use catalog-entry JSON snippet. There is no
   hosted marketplace to upload to — MINXG's catalog is just a JSON
   file anyone can host (a raw GitHub URL is enough). Open a PR against
   whatever catalog you want your skill listed in, with that snippet
   added, and point its `source` at wherever you're actually hosting
   the skill (a git repo `#subdir` or a raw file URL both work).

## Installing someone else's skill

```
minxg skill search "topic" --catalog https://raw.githubusercontent.com/<org>/<repo>/main/catalog.json
minxg skill install <name-or-git-url-or-raw-url>
```
Installing always shows you the SKILL.md content first and requires
explicit confirmation — nothing gets written to disk silently.

## Notes / gotchas

- Keep a SKILL.md under 512KB. It's instructions, not a knowledge dump
  — if it's bigger than that, it probably wants to be several skills
  or a reference doc the skill points to.
- `category` is just an organizational label (shows up in `minxg skill
  list --category ...`); it doesn't change behavior.
- This very skill is a real, working example — it ships bundled with
  MINXG and installs/searches exactly the way it says above.

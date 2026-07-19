---
name: daily-standup-notes
description: Turn a rough end-of-day brain dump into a clean, three-line standup update (done / doing / blockers).
version: 1.0.0
author: minxg-core
tags: [productivity, writing, standup]
category: productivity
---

# Daily Standup Notes

Take whatever messy notes, commit messages, or stream-of-consciousness
the person gives you about their day and turn it into a standard
three-part standup update.

## When to use this

The person pastes in raw notes (bullet points, half sentences, a list
of things they touched) and wants a standup-ready summary, or asks
something like "turn this into my standup update."

## Steps

1. Read the raw input and sort every item into exactly one of three
   buckets:
   - **Done** — finished and verifiable (shipped, merged, tested, closed).
   - **Doing** — in progress, will continue tomorrow.
   - **Blocked** — can't proceed without something from someone else.

2. Rewrite each item as one short, concrete line — past tense for
   Done, present-continuous for Doing, and name the actual blocker
   (who/what it's waiting on) for Blocked. Drop vague filler like
   "worked on stuff."

3. If an item doesn't clearly belong in any bucket, ask instead of
   guessing — a wrong bucket is worse than a clarifying question here.

4. Output format:
   ```
   **Done:**
   - ...

   **Doing:**
   - ...

   **Blocked:**
   - ... (waiting on: ...)
   ```
   Omit a section entirely if it has nothing in it — don't print
   "Blocked: none."

## Notes / gotchas

- Keep each line to one sentence. If someone's "done" item needs two
  sentences to explain, it's probably actually two items.
- Preserve any ticket/PR numbers or proper nouns exactly as given —
  don't paraphrase identifiers.

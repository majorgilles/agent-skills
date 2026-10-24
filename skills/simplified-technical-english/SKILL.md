---
name: simplified-technical-english
description: Rewrite text in ASD-STE100 Simplified Technical English (STE). Use when the user asks to rewrite, simplify or "STE" something already written - a previous chat answer, a Notion page, block, table cell or comment, a Slack message, a GitHub PR or issue, a doc file - or says "rewrite in STE", "simplified technical english", "ASD-STE100", "make it plainer".
---

# Rewrite in Simplified Technical English (ASD-STE100)

STE is the controlled language the aerospace industry uses so that a reader with no one to ask cannot misread a text. Rewrite the target so it follows the rules below, without changing its meaning.

## 1. Find the target

- **"What you said"**: the previous answer in this conversation, or the part the user quotes.
- **A Notion page, block, database cell or comment**: fetch it first. Rewrite only the text the user names; leave properties, mentions, links, tables structure and unrelated sections as they are.
- **Slack, GitHub (PR body, issue, comment), Airtable, a file**: read the current text with the matching tool first.
- If the target is unclear, ask one short question. Do not guess.

## 2. Rewrite rules

### Words
- Use common, simple words. Prefer "use" to "utilize", "start" to "initiate", "help" to "facilitate", "show" to "indicate".
- **One word, one meaning.** Pick one term for a concept and keep it. Do not rotate synonyms.
- Keep **technical names** exactly as they are: field and column names, code identifiers, product names, status values, VINs, URLs, numbers, dates. Put code-like names in backticks when the platform supports it.
- Explain an unusual term or acronym the first time it appears.
- Do not use more than **three nouns in a row**. Break a cluster with "of", "for" or a relative clause.
- Do not use contractions: "do not", not "don't".

### Verbs
- Use the **active voice**: "The backend sends the event", not "the event is sent".
- Use **simple tenses** only: present, past, simple future.
- Do not use **-ing forms** as verbs. "When you start the sync", not "When starting the sync". An -ing word that is part of a technical name stays (`own sourcing`, "listing").
- Avoid phrasal verbs when a single verb exists: "remove", not "get rid of"; "configure", not "set up".
- Use "must" for a requirement and "can" for a possibility. Avoid "should".

### Sentences
- **One idea per sentence.**
- **Procedures** (steps the reader does): at most **20 words**. Use the imperative: "Tick `Is Sourceable`."
- **Descriptions**: at most **25 words**.
- Put a **condition first**: "If the VIN is missing, the backend refuses the row."
- Keep articles ("the", "a"). Do not write telegraphic text.
- Split a long sentence. Do not compress it by removing a subject, an article or a condition.

### Structure
- Start with the topic sentence: say what it is, then how it works.
- At most **six sentences per paragraph**, one topic per paragraph.
- Use a **vertical list** for steps, conditions or alternatives (three or more items).
- Put warnings and cautions **before** the step they apply to.
- Use numbered lists for a sequence; use bullets when order does not matter.

## 3. Process

1. Read the target in full.
2. Rewrite it with the rules above. Keep every fact, number, link and name. Do not add new content.
3. Check each sentence: word count, active voice, no -ing verb, one idea.
4. **Text on a shared platform** (Notion, Slack, GitHub, Airtable): show the before and after to the user, and write it only after the user approves. For a long text, show a few representative samples and the full list of changes.
5. **The previous chat answer**: give the rewritten text directly.
6. Write it back with the platform's own tool. Change only the target text. For Notion, re-fetch the page after the edit to confirm it.

## 4. Example

Before:
> The legacy sync, which runs every 20 minutes, is currently still being used for relisting returning cars and should be decommissioned once the migration has been completed.

After:
> The legacy sync runs every 20 minutes. It puts cars that come back from a lease on sale again. Remove the sync after the migration is complete.

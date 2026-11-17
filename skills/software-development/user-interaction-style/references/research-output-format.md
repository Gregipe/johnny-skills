# Research & Search Output Formatting

Greg's direct feedback, July 18, 2026:

> "Check this - not formatted and just a dump - it has to be easy on the eye
> with clear formatting and de-duped news items."

## Clean Format Rules

### De-duplicate Aggressively
Multiple sources covering the same story = ONE entry with multiple links.
Greg called out duplicate results as noise — "de-duped news items."

### Compact Source Attribution
Use `[SourceName](url) · [SourceName](url)` with `·` separators, not raw
URLs or new lines per source.

### Scannable, Not a Dump
Greg's direct words: "it has to be easy on the eye with clear formatting."
If it looks like raw tool output, reformat it. Never present:

```
- [HDFC Bank Trims Workforce By Over 3300](https://www.youtube.com/...)
  HDFC Bank has reduced its workforce by over 3,300 employees...

- [HDFC Bank Workforce Drops by Over 3300](https://www.bloomberg.com/...)
  ### Bloomberg. Connecting decision makers...
```

Present as:

```
📰 HDFC Bank — Key Updates

1. **Workforce cut by 3,300+ as AI automation accelerates** — FY26 saw
   significant reduction in non-supervisory roles as the bank pivots to
   digital-first operations. [Mint](url) · [Bloomberg](url) · [Firstpost](url)
```

### No fetch_url on Every Result
web_search already returns snippets. Only fetch_url when the user explicitly
asks for full article text. Calling fetch_url on every result floods the
response with raw page content.

### Silent Filtering
Skip irrelevant results — don't say "I filtered out X." If the search lens
says IGNORE consumer banking products, just don't mention them.

## Template

```
📰 [Company Name] — Key Updates

1. **Headline that captures the story** — 1-2 lines of what happened and
   why it matters for our proposition. [Source](url) · [Source](url)

2. **Next story headline** — 1-2 lines of key facts. [Source](url)

💡 **Entry Point:** [1-line take on why this matters for outreach]
```

## Anti-Patterns

- ❌ Raw markdown bullet dumps with URLs and snippets
- ❌ Same story repeated 3 times from different sources as separate entries
- ❌ fetch_url called on every web_search result
- ❌ Full page content (4000 chars) dumped into response
- ❌ "I also found X, Y, Z but filtered those out" — just skip them silently

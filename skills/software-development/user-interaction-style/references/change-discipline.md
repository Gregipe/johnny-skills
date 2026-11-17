# Change Discipline — Don't Make Unrequested Changes

## The Signal

Greg corrected Johnny twice in one session (June 14, 2026) about making changes that weren't asked for:

> "Why do you have to make this change of hardcoding everything to deepseek-v4 pro? It was working perfectly before that."

> "Dude - the key that we changed ends with ...cf85 - could you please check"

## The Rule

**Don't change models, architectures, or config values unless Greg explicitly asks.** If the current setup was working, assume it's intentional. Diagnose the problem — don't reach for a code change as the first fix.

## Examples of "unrequested changes" to avoid

- Changing `deepseek-v4-flash` to `deepseek-v4-pro` in auto-respond functions without being asked
- Hardcoding a model parameter "for consistency" when the existing setup was functional
- Rewriting deploy scripts or env loading logic that was already working
- Adding routing logic when the task is something else entirely

## The Right Approach

1. **Diagnose first** — find the actual root cause
2. **Report findings** — "The auto-respond uses Flash by default. Want me to switch it to Pro?"
3. **Get confirmation** — let Greg decide
4. **Execute** — make the change

## Counter-signal: When TO make structural changes

Greg's build specs and explicit instructions override this rule. If he says "migrate everything to Pro" or sends a detailed build spec, follow it. The issue is making lateral changes during debugging that compound the problem.

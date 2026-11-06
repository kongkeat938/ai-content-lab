# Advisor panel scorecard

K requires the advisor team itself to be measured -- on timeline, output and
goal -- and any advisor that scores badly to be replaced.

`scripts/panel_scorecard.py` sends each advisor three checkable probes:

- **format** -- must return parseable JSON with the exact keys asked for.
- **grounding** -- the real channel numbers are embedded in the prompt; the
  advisor must return the exact view total. Catches invented data.
- **thai** -- must answer in Thai.

Score 0-100 (format 25, grounding 30, thai 20, reachability 25). Verdict:
>=80 KEEP, >=50 WATCH, else REPLACE. Timeline is the wall-clock seconds the three
probes take.

## Measured 2026-11-06

| advisor | format | grounding | thai | secs | score | verdict |
|---|---|---|---|---|---|---|
| gemini | OK | OK | OK | 2.3 | 100 | KEEP |
| pollinations | OK | OK | OK | 1.1 | 100 | KEEP |
| openhands | n/a | n/a | n/a | >600 | -- | WATCH (reachable, too slow) |
| openhands-claude | n/a | n/a | n/a | >600 | -- | WATCH (reachable, too slow) |
| openhands-gpt | n/a | n/a | n/a | >600 | -- | WATCH (reachable, too slow) |

- The two free HTTP advisors are fast and accurate: **keep both**.
- The three OpenHands advisors answer a bare question only by spinning up a full
  agent conversation, which took **over 10 minutes per probe** -- longer than the
  pod's 20-minute idle budget and far slower than a panel needs. They are
  reachable, so not dropped, but they are a poor fit for a fast panel. Use them
  only for a single, slow, high-value decision, not a routine scorecard.

## What "replace" looks like

An advisor is replaced when it scores REPLACE twice in a row, or when a
candidate vendor beats its score on a re-measure. Candidates to test next:
the Zhipu (GLM) camp via llm7 when its free daily quota is fresh, and any other
keyless OpenAI-compatible endpoint that answers a grounded probe correctly.

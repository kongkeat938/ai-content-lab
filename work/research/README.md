# work/research — competitor analysis and the quality gate

Everything here was built on 2026-10-30 to answer two questions: **who are we
competing with, and how do we keep quality high over many episodes.**

This folder is deliberately outside `scripts/`. `scripts/` is the pipeline owner's
directory (rule 6 in `AGENTS.md`), and a read-only checker any account can run
does not belong there.

## Read these

| File | What it is |
|---|---|
| `COMPETITOR-STRATEGY.md` | the analysis: measured competitor numbers, what wins, and the plan to attract viewers |
| `RUNBOOK.md` | the repeatable per-episode loop and the pre-publish checklist |

## Tools (read-only unless noted)

| File | Does |
|---|---|
| `yt.py` | YouTube Data API helper; mints an access token from the per-channel refresh tokens in the environment |
| `collect.py` | searches the three niches and writes `raw.json` (channels + video stats) |
| `deep.py` | pulls the latest 50 uploads of key competitors into `recent.json` |
| `measure.py` | measures **our** channels against the targets in the strategy, §6 |
| `quality_gate.py` | checks one finished episode against the definition of done; exits 1 on a hard failure |

`raw.json` and `recent.json` are committed on purpose: they are the evidence
behind the numbers in the strategy, and the live figures move. Regenerate with
`collect.py` / `deep.py`.

## Usage

```bash
python3 work/research/collect.py                 # refresh competitor data
python3 work/research/measure.py                 # our channels vs target
python3 work/research/quality_gate.py episodes/ep02_manthana_phatha --channel ch2
```

## Note on scope

The tokens hold the full `youtube` scope, but `commentThreads` still returns 403
(insufficient scopes), so this tooling reads statistics only — never comments.
Everything is read-only: no upload, no edit, no delete.

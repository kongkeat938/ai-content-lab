# Advisor panel scorecard

| advisor | format | grounding | thai | secs | score | verdict |
|---|---|---|---|---|---|---|
| gemini | OK | OK | OK | 2.3 | 100 | KEEP |
| pollinations | OK | OK | OK | 1.1 | 100 | KEEP |

## Raw

```json
[
  {
    "advisor": "gemini",
    "probes": {
      "format": true,
      "grounding": true,
      "thai": true
    },
    "error": "",
    "seconds": 2.269447088241577,
    "answer_sample": "**\"ก้าวแรกอาจจะยังไม่มีใครเห็น แต่เชื่อเถอะว่าความพยายามในวันนี้ จะพาช่องของคุณไ"
  },
  {
    "advisor": "pollinations",
    "probes": {
      "format": true,
      "grounding": true,
      "thai": true
    },
    "error": "",
    "seconds": 1.1312274932861328,
    "answer_sample": "ให้ความตั้งใจในทุกคลิปเป็นแรงบันดาลใจให้ผู้ชม และอย่ายอมแพ้ เพราะทุกความพยายามจะ"
  }
]
```

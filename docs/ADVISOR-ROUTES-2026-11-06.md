# Advisor / tool routes — measured from the pod (2026-11-06)

K: "หาค่ายอื่น อย่ายึดติดกับแค่ชื่อเสียง เน้นลองใช้จริง". So every line below is a
**live call made from this pod**, not a vendor's marketing page.

## Result in one line
The **only keyless text camp that reliably answers today** is **Pollinations
(OpenAI-OSS / gpt-oss-20b)**; **Google** answers via the `GEMINI_API_KEY` secret
(2 models). **Zhipu GLM** is a genuine third camp through llm7 but its free daily
quota runs out fast. **Pollinations image generation now works keyless** — a new,
important capability.

## Text — what actually returned a completion

| Camp | Route | Key? | Measured today |
|---|---|---|---|
| **OpenAI-OSS** | `text.pollinations.ai/openai` (`openai-fast` = gpt-oss-20b) | none | ✅ 200, real Thai answer |
| **Google** | `generativelanguage.googleapis.com` `gemini-3.5-flash-lite` | `GEMINI_API_KEY` | ✅ 200, real answer |
| **Google** | same, `gemma-4-31b-it` | `GEMINI_API_KEY` | ✅ 200 |
| **Zhipu** | `api.llm7.io` `GLM-5.3-Flash` | none | ✅ 200 when quota allows; then 429 "Daily token quota exceeded" |
| **DeepSeek** | `api.llm7.io` `DeepSeek-V4-Flash-0731` | none | ✅ 200 briefly; then 429 (same quota pool as GLM) |

- **llm7 free tier is one shared daily token pool.** Exhaust it and *every* llm7
  model 429s ("Retry after N s" that only ever counts down). Many other llm7
  models return `401 Missing API key` even though the same key-less request works
  for GLM/DeepSeek — so most of the 70-model catalog is paid-gated.

## Image — measured

| Route | Key? | Measured |
|---|---|---|
| **Pollinations image** `image.pollinations.ai/prompt/<text>?width=&height=&nologo=true` | none | ✅ **200 `image/jpeg`, 36,964 B** |

This contradicts the earlier note that Pollinations images were "402 service-wide".
Measured 2026-11-06: it renders. Re-check before relying on it.

## Tested and NOT usable (no keyless route)

`groq`, `cerebras`, `mistral`, `together`, `fireworks`, `novita`, `deepinfra`,
`sambanova`, `nvidia`, `hyperbolic` (endpoint decommissioned), `featherless`,
`friendli`, `kluster`, `avian`, `perplexity`, `cohere`, `aimlapi`, `arliai`,
`a4f`, `electronhub`, `zukijourney`, `naga`, `airforce`, `chatanywhere`,
`chatgptuk`, `gpt.ge`, `free.v36.cm`, `juheai`, `voidai`, `puter` → all need a
key/subscription, or DNS-fail, or 5xx.

## Two traps worth remembering

1. **The pod's egress proxy stubs some hosts.** `models.github.ai/inference`
   returned a literal `OK` for *every* prompt and `/catalog/models` → `OK`; a
   batch of unrelated vendors returned an identical `{"error":{"message":"Missing
   API key","type":"invalid_request_error","param":null,"code":"invalid_api_key"}}`.
   That is a proxy stub, not the real vendor. **Verify with a prompt whose answer
   you can check**, never just a 200.
2. **llm7 throttles *concurrency*, not just total.** Fanning out 12 parallel
   probes made every llm7 model say `429 Too many concurrent requests`. Probe
   llm7 **one request at a time**.

## What this means for the panel rule

"Consult ≥3 distinct camps" is met today by: **Google + OpenAI-OSS + Zhipu**.
When llm7's quota is dry, fall back to **Google + OpenAI-OSS** and say so — do
not claim a third camp that did not actually answer.

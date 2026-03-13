# SovereignGuard Launch Kit

This guide is for launching SovereignGuard to real audiences, not just documenting it.

## 1. 60-Second Demo Script

Goal: show the mask-forward-restore cycle in under one minute.

Shot list:

1. Show input prompt in terminal:

```text
Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678
```

2. Show the forwarded upstream payload in logs (tokenized):

```text
Call {{SG_PERSON_NAME_a3f9b2}} at {{SG_TN_PHONE_c4d5e6}}, {{SG_TN_NATIONAL_ID_f7e3b1}}
```

3. Show final response returned to client (restored):

```text
Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678
```

4. End on one line:

```text
Provider saw tokens, not raw identifiers.
```

Recording tips:

- Keep it one take.
- No narration needed.
- Keep terminal font large enough for mobile.
- Keep total runtime between 35 and 60 seconds.

## 2. Demo Command Sequence

Use one terminal for gateway logs and one for requests.

Gateway:

```bash
python -m uvicorn sovereignguard.main:app --reload --port 8000
```

Request:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sg-client-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678"}
    ]
  }'
```

If you want cleaner visuals, pre-run once, then record the second run.

## 3. LinkedIn Post Templates

### Template A (problem-first)

We just open sourced a tool for EMEA teams blocked on AI compliance.

SovereignGuard sits between your app and OpenAI/Anthropic.

Before provider call:
"Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678"

What the model sees:
"Call {{SG_PERSON_NAME_a3f9b2}} at {{SG_TN_PHONE_c4d5e6}}, {{SG_TN_NATIONAL_ID_f7e3b1}}"

Your app still gets restored, usable output.

Built for GDPR workflows with Tunisia, Morocco, and France locale support.

GitHub: <your-link>

If compliance has blocked your AI roadmap, I would value your feedback.

### Template B (story-first)

Many teams do not fail at AI because of models. They fail at compliance.

We built SovereignGuard to enforce one boundary:
raw identifiers should not leave your infrastructure when calling LLM APIs.

Drop-in OpenAI-compatible gateway.
Tokenize outbound PII, restore inbound responses.

Open source now: <your-link>

If you run legaltech, fintech, healthtech, or customer support in EMEA, I would like your review.

## 4. Launch Day Checklist

1. Publish the demo clip (native video, not external link only).
2. Post LinkedIn announcement with one clear before/after example.
3. Pin the same demo in GitHub README near the top.
4. Share in 3 niche communities (GDPR/privacy, French dev, North Africa startup).
5. Ask 5 relevant people for feedback directly (not generic "please share").
6. Respond to all comments within first 2 hours.

## 5. Social Proof Seeding

Before broad announcement:

1. Get 10-20 seed stars from close network.
2. Ask 2 external engineers to open issues or feedback.
3. Add a public "Who is testing SovereignGuard" section in README once first external users appear.

## 6. Messaging Guardrails

Use:

- "production-ready architecture"
- "validate recognizers against your own data"
- "v0.2"

Avoid:

- "perfect privacy"
- "zero risk"
- any legal guarantee language

## 7. Post-Launch Metrics (First 7 Days)

Track daily:

- GitHub stars
- repo clones
- unique visitors
- issues opened
- external contributors
- demo video views

Minimum healthy signal after 7 days:

- 25+ stars
- 3+ external issues or discussions
- at least 1 real pilot conversation

## 8. Security Hygiene Before Posting

1. Rotate any API key ever pasted in chat, screenshots, or public docs.
2. Verify `.env` is not committed.
3. Verify no secrets in recorded terminal history.
4. Use placeholder keys in all shared media.

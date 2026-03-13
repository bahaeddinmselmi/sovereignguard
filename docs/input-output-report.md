# Input and Output Report

Date: 2026-03-13

This file records the exact inputs and outputs from the latest runtime validation.

## 1. Direct DeepSeek API Test

### Input

Command:

```powershell
$env:DEEPSEEK_KEY='sk-***REDACTED***'; python -c "import os, httpx, json; key=os.environ.get('DEEPSEEK_KEY',''); headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'}; payload={'model':'deepseek-chat','messages':[{'role':'user','content':'Reply with exactly: OK'}],'max_tokens':8}; r=httpx.post('https://api.deepseek.com/chat/completions',headers=headers,json=payload,timeout=40); print('direct_status=',r.status_code); txt=r.text[:600]; print('direct_body=',txt)"
```

Payload content:

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "user", "content": "Reply with exactly: OK"}
  ],
  "max_tokens": 8
}
```

### Output

```text
direct_status= 200
direct_body= {"id":"928ad8db-b4bc-4ea8-9fdf-e58ca5dbf7c3","object":"chat.completion","created":1773408673,"model":"deepseek-chat","choices":[{"index":0,"message":{"role":"assistant","content":"OK"},"logprobs":null,"finish_reason":"stop"}],"usage":{"prompt_tokens":9,"completion_tokens":1,"total_tokens":10,"prompt_tokens_details":{"cached_tokens":0},"prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":9},"system_fingerprint":"fp_eaab8d114b_prod0820_fp8_kvcache"}
```

## 2. SovereignGuard Gateway -> DeepSeek End-to-End Test

### Input

Command:

```powershell
$env:TARGET_API_KEY='sk-***REDACTED***'; $env:TARGET_API_URL='https://api.deepseek.com'; $env:TARGET_PROVIDER='openai'; $env:GATEWAY_API_KEYS='["sg-client-key-1"]'; python -c "from fastapi.testclient import TestClient; from sovereignguard.main import app; c=TestClient(app); body={'model':'deepseek-chat','messages':[{'role':'user','content':'Contact Mohamed Ben Ali at +216 98 765 432. Reply with one short sentence.'}]}; r=c.post('/v1/chat/completions', json=body, headers={'Authorization':'Bearer sg-client-key-1'}); print('gateway_status=',r.status_code); data=r.json(); print('gateway_json_keys=',list(data.keys())); msg=data.get('choices',[{}])[0].get('message',{}).get('content',''); print('gateway_response=',msg[:300]);"
```

Request body:

```json
{
  "model": "deepseek-chat",
  "messages": [
    {
      "role": "user",
      "content": "Contact Mohamed Ben Ali at +216 98 765 432. Reply with one short sentence."
    }
  ]
}
```

### Output

```text
CONFIG WARNING: No ALLOWED_ORIGINS set — CORS will allow all origins.
HTTP Request: POST https://api.deepseek.com/v1/chat/completions "HTTP/1.1 200 OK"
gateway_status= 200
gateway_json_keys= ['id', 'object', 'created', 'model', 'choices', 'usage', 'system_fingerprint']
gateway_response= This is Contact Mohamed Ben Ali from +216 98 765 432.
```

Observed audit/runtime notes:

```text
TEXT_MASKED: entity_count=2, entity_types=["TN_PHONE", "PERSON_NAME"]
TEXT_RESTORED: tokens_restored=2, tokens_not_found=0, restoration_completeness=1.0
```

## Result Summary

- Direct provider call: success (`200`)
- Gateway pass-through call: success (`200`)
- Masking/restoration: success (`2` tokens restored)

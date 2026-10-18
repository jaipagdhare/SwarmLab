"""Provider boundary. Implementations must return usage for every successful call."""
from dataclasses import dataclass
from typing import Protocol
from copy import deepcopy
import json
from time import monotonic

import httpx


@dataclass
class Completion:
    value: dict
    usage: dict
    elapsed_seconds: float


class JsonModel(Protocol):
    name: str

    def complete(self, *, system: str, context: dict, schema: dict,
                 max_output_tokens: int, timeout_seconds: float) -> Completion: ...


class ModelError(RuntimeError):
    def __init__(self, code, *, usage=None, elapsed_seconds=0):
        super().__init__(code)
        self.code = code
        self.usage = usage
        self.elapsed_seconds = elapsed_seconds


def strict_schema(schema):
    """Responses strict mode requires all properties, including nullable fields."""
    result = deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(result)
    return result


class OpenAIModel:
    def __init__(self, settings, transport=None):
        self.name = settings.model_name
        self._key = settings.model_api_key
        self._transport = transport

    def complete(self, *, system, context, schema, max_output_tokens, timeout_seconds):
        started = monotonic()
        payload = {
            "model": self.name, "instructions": system, "store": False,
            "input": [{"role": "user", "content": json.dumps(context, separators=(",", ":"))}],
            "reasoning": {"effort": "low"}, "max_output_tokens": max_output_tokens,
            "text": {"format": {"type": "json_schema", "name": "swarmlab_output",
                                 "schema": strict_schema(schema), "strict": True}},
        }
        try:
            # No automatic retries: failures and unknown billed usage remain visible.
            with httpx.Client(transport=self._transport, timeout=timeout_seconds) as client:
                response = client.post("https://api.openai.com/v1/responses", json=payload,
                                       headers={"Authorization": f"Bearer {self._key}"})
        except httpx.TimeoutException:
            raise ModelError("request_timeout", elapsed_seconds=monotonic()-started) from None
        except httpx.HTTPError:
            raise ModelError("connection_failed", elapsed_seconds=monotonic()-started) from None
        elapsed = monotonic() - started
        if response.status_code != 200:
            codes = {401: "invalid_api_key", 403: "model_access_denied", 404: "model_unavailable",
                     429: "rate_or_billing_limit", 400: "request_rejected"}
            raise ModelError(codes.get(response.status_code, "provider_error"), elapsed_seconds=elapsed)
        try:
            body = response.json()
        except ValueError:
            raise ModelError("invalid_response", elapsed_seconds=elapsed) from None
        usage = body.get("usage")
        if body.get("status") != "completed":
            raise ModelError("incomplete_response", usage=usage, elapsed_seconds=elapsed)
        blocks = [block for item in body.get("output", []) if item.get("type") == "message"
                  for block in item.get("content", [])]
        if any(block.get("type") == "refusal" for block in blocks):
            raise ModelError("model_refusal", usage=usage, elapsed_seconds=elapsed)
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "output_text")
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError("Expected JSON object")
        except ValueError:
            raise ModelError("invalid_json_output", usage=usage, elapsed_seconds=elapsed) from None
        return Completion(value=value, usage=usage, elapsed_seconds=elapsed)


def create_model(settings):
    if not settings.model_provider or not settings.model_name or not settings.model_api_key:
        raise ValueError("Set MODEL_PROVIDER, MODEL_NAME, and MODEL_API_KEY in .env")
    if settings.model_provider == "gemini":
        return GeminiModel(settings)
    if settings.model_provider == "openai":
        return OpenAIModel(settings)
    raise ValueError("Supported providers: gemini, openai")



def gemini_schema(schema):
    """Keep nested array bounds in descriptions to avoid provider schema rejection.

    Pydantic still enforces all bounds before the artifact can be published.
    """
    allowed = {'$defs', '$ref', 'type', 'format', 'title', 'description', 'enum',
               'items', 'minimum', 'maximum', 'anyOf',
               'properties', 'additionalProperties', 'required'}
    def visit(node):
        if isinstance(node, list):
            return [visit(v) for v in node]
        if not isinstance(node, dict):
            return node
        result = {}
        for key, value in node.items():
            if key in {'properties', '$defs'}:
                result[key] = {name: visit(child) for name, child in value.items()}
            elif key in allowed:
                result[key] = visit(value)
            elif key == 'const':
                result['enum'] = [value]
        constraints = [f"{k}={node[k]}" for k in ('pattern', 'minLength', 'maxLength', 'minItems', 'maxItems') if k in node]
        if constraints:
            result['description'] = (result.get('description', '') + ' Constraints: ' + '; '.join(constraints)).strip()
        return result
    return visit(schema)


class GeminiModel:
    def __init__(self, settings, transport=None, pacer=None):
        import re
        if not re.fullmatch(r'gemini-[a-zA-Z0-9.-]+', settings.model_name):
            raise ValueError('Invalid Gemini model identifier')
        self.name = settings.model_name
        self._key = settings.model_api_key
        self._transport = transport
        from .pacing import GEMINI_PACER
        self.pacer = pacer if pacer is not None else GEMINI_PACER
        self.cancelled = lambda: False
        self.on_wait = None
        self.max_attempts = 3

    def complete(self, *, system, context, schema, max_output_tokens, timeout_seconds):
        started = monotonic()
        payload = {
            'systemInstruction': {'parts': [{'text': system}]},
            'contents': [{'role': 'user', 'parts': [{'text': json.dumps(context, separators=(',', ':'))}]}],
            'generationConfig': {'responseMimeType': 'application/json',
                                 'responseJsonSchema': gemini_schema(schema),
                                 'maxOutputTokens': max_output_tokens},
        }
        deadline = started + timeout_seconds
        for attempt in range(self.max_attempts):
            try:
                self.pacer.wait(deadline, self.cancelled, self.on_wait)
                if self.on_wait:
                    self.on_wait(0)
                with httpx.Client(transport=self._transport, timeout=max(0.001, deadline-monotonic())) as client:
                    response = client.post(
                        f'https://generativelanguage.googleapis.com/v1beta/models/{self.name}:generateContent',
                        headers={'x-goog-api-key': self._key}, json=payload)
            except InterruptedError:
                raise ModelError('cancelled', elapsed_seconds=monotonic()-started) from None
            except (TimeoutError, httpx.TimeoutException):
                raise ModelError('request_or_rate_wait_timeout', elapsed_seconds=monotonic()-started) from None
            except httpx.HTTPError:
                raise ModelError('connection_failed', elapsed_seconds=monotonic()-started) from None
            if response.status_code != 429:
                break
            # Retry only temporary rate limits. Never loop on a daily/zero quota.
            try:
                error = response.json().get('error', {})
                details = error.get('details', [])
            except (ValueError, AttributeError):
                details = []
            cooldown, daily, zero = 60.0, False, False
            try:
                cooldown = max(cooldown, float(response.headers.get('Retry-After', '0')))
            except ValueError:
                pass
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                for violation in detail.get('violations', []):
                    metric = str(violation.get('quotaId', '')) + str(violation.get('quotaMetric', ''))
                    daily |= 'perday' in metric.lower() or 'per_day' in metric.lower()
                    zero |= str(violation.get('quotaValue', '')) == '0'
                delay = detail.get('retryDelay', '')
                if isinstance(delay, str) and delay.endswith('s'):
                    try:
                        cooldown = max(cooldown, float(delay[:-1]) + 1)
                    except ValueError:
                        pass
            if daily or zero:
                raise ModelError('gemini_daily_or_unavailable_quota', elapsed_seconds=monotonic()-started)
            self.pacer.defer(cooldown)
            if attempt == self.max_attempts - 1:
                break
        elapsed = monotonic()-started
        if response.status_code != 200:
            code = {400: 'request_rejected', 401: 'invalid_api_key', 403: 'api_access_denied',
                    404: 'model_unavailable', 429: 'gemini_quota_or_rate_limit'}.get(response.status_code, 'provider_error')
            raise ModelError(code, elapsed_seconds=elapsed)
        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError()
        except ValueError:
            raise ModelError('invalid_response', elapsed_seconds=elapsed) from None
        raw_usage = body.get('usageMetadata')
        usage = None if raw_usage is None else {
            'input_tokens': raw_usage.get('promptTokenCount', 0),
            'output_tokens': raw_usage.get('candidatesTokenCount', 0) + raw_usage.get('thoughtsTokenCount', 0),
            'total_tokens': raw_usage.get('totalTokenCount'),
            'provider_usage': raw_usage,
            'http_attempts': attempt + 1,
        }
        candidates = body.get('candidates') or []
        if body.get('promptFeedback', {}).get('blockReason') or not candidates:
            raise ModelError('blocked_or_empty_response', usage=usage, elapsed_seconds=elapsed)
        candidate = candidates[0]
        if candidate.get('finishReason') != 'STOP':
            raise ModelError('incomplete_or_blocked_response', usage=usage, elapsed_seconds=elapsed)
        output = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', []) if not p.get('thought'))
        try:
            value = json.loads(output)
            if not isinstance(value, dict):
                raise ValueError()
        except ValueError:
            raise ModelError('invalid_json_output', usage=usage, elapsed_seconds=elapsed) from None
        return Completion(value, usage, elapsed)

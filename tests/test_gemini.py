import json
import httpx
import pytest
from swarmlab.config import Settings
from swarmlab.model import GeminiModel, ModelError, create_model, gemini_schema
from swarmlab.schemas import Decision, SleepArtifact


class NoWaitPacer:
    def wait(self, *args): pass
    def defer(self, seconds): pass


def call(handler):
    model = GeminiModel(Settings(model_name='gemini-3.5-flash-lite', model_api_key='gemini-test'), httpx.MockTransport(handler), pacer=NoWaitPacer())
    return model.complete(system='rules', context={'observations': []}, schema=Decision.model_json_schema(), max_output_tokens=1200, timeout_seconds=1)


def test_gemini_request_and_usage():
    def handler(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.headers['x-goog-api-key'] == 'gemini-test'
        assert 'gemini-test' not in str(request.url)
        body = json.loads(request.content)
        assert body['generationConfig']['maxOutputTokens'] == 1200
        assert body['generationConfig']['responseMimeType'] == 'application/json'
        assert body['systemInstruction']['parts'][0]['text'] == 'rules'
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
            {'thought': True, 'text': 'internal'}, {'text': '{"ok":true}'}]}}],
            'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 4, 'thoughtsTokenCount': 2, 'totalTokenCount':16}})
    result = call(handler)
    assert result.value == {'ok':True}
    assert result.usage['output_tokens'] == 6


@pytest.mark.parametrize('status,code', [(403,'api_access_denied'), (429,'gemini_quota_or_rate_limit'), (404,'model_unavailable')])
def test_gemini_errors_do_not_expose_body(status, code):
    with pytest.raises(ModelError, match=code):
        call(lambda _: httpx.Response(status, text='private provider response'))


def test_incomplete_preserves_usage():
    with pytest.raises(ModelError) as err:
        call(lambda _: httpx.Response(200,json={'candidates':[{'finishReason':'MAX_TOKENS'}], 'usageMetadata':{'totalTokenCount':1200}}))
    assert err.value.usage['total_tokens'] == 1200


def test_key_isolation(monkeypatch, tmp_path):
    monkeypatch.setenv('MODEL_PROVIDER','gemini')
    monkeypatch.setenv('MODEL_API_KEY','openai-key-must-not-be-sent')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    settings = Settings.load(tmp_path/'missing.env')
    assert not settings.model_api_key
    with pytest.raises(ValueError): create_model(settings)
    monkeypatch.setenv('GEMINI_API_KEY','gemini-test')
    settings = Settings.load(tmp_path/'missing.env')
    assert isinstance(create_model(settings), GeminiModel)
    assert settings.model_api_key == 'gemini-test'


def test_gemini_schema_preserves_property_names_and_candidate_literal():
    schema = gemini_schema(SleepArtifact.model_json_schema())
    assert 'summary' in schema['properties']
    assert schema['$defs']['Procedure']['properties']['status']['enum'] == ['candidate']
    assert 'default' not in str(schema)


def test_rate_limit_retries_then_succeeds():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={'error':{'details':[{'retryDelay':'62s'}]}})
        return httpx.Response(200, json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}], 'usageMetadata':{'totalTokenCount':3}})
    result = call(handler)
    assert len(calls) == 2
    assert result.usage['http_attempts'] == 2


def test_daily_limit_does_not_retry():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,json={'error':{'details':[{'violations':[{'quotaId':'GenerateRequestsPerDayPerProject'}]}]}})
    with pytest.raises(ModelError, match='gemini_daily_or_unavailable_quota'):
        call(handler)
    assert len(calls)==1


def test_nested_sleep_array_limits_are_described_but_validated_locally():
    schema = gemini_schema(SleepArtifact.model_json_schema())
    facts = schema['$defs']['Hypothesis']['properties']['observed_facts']
    assert 'maxItems' not in facts
    assert 'maxItems=20' in facts['description']
    assert SleepArtifact.model_json_schema()['$defs']['Hypothesis']['properties']['observed_facts']['maxItems'] == 20


def test_incident_single_attempt_cap_disables_temporary_rate_retry():
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(429,json={'error':{'details':[{'retryDelay':'60s'}]}})
    model=GeminiModel(Settings(model_name='gemini-3.5-flash-lite',model_api_key='test'),httpx.MockTransport(handler),pacer=NoWaitPacer())
    model.max_attempts=1
    with pytest.raises(ModelError,match='gemini_quota_or_rate_limit'):
        model.complete(system='test',context={},schema=Decision.model_json_schema(),max_output_tokens=100,timeout_seconds=1)
    assert len(requests)==1

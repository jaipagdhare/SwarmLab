import json
import httpx
import pytest
from swarmlab.config import Settings
from swarmlab.model import OpenAIModel, ModelError, strict_schema
from swarmlab.schemas import Decision


def request_model(handler):
    model = OpenAIModel(Settings(model_name='test-model', model_api_key='private-key'), httpx.MockTransport(handler))
    return model.complete(system='instructions', context={'observations': []},
                          schema=Decision.model_json_schema(), max_output_tokens=1200, timeout_seconds=1)


def test_responses_payload_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body['store'] is False
        assert body['text']['format']['strict'] is True
        assert 'private-key' not in request.content.decode()
        assert request.headers['authorization'] == 'Bearer private-key'
        return httpx.Response(200, json={'status': 'completed', 'usage': {'input_tokens': 12, 'output_tokens': 9},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"ok":true}'}]}]})
    result = request_model(handler)
    assert result.value == {'ok': True}
    assert result.usage['input_tokens'] == 12


@pytest.mark.parametrize('status,code', [(401,'invalid_api_key'), (429,'rate_or_billing_limit'), (500,'provider_error')])
def test_errors_sanitize_provider_body(status, code):
    with pytest.raises(ModelError) as error:
        request_model(lambda _: httpx.Response(status, text='private-key'))
    assert str(error.value) == code


def test_incomplete_response_preserves_usage():
    with pytest.raises(ModelError) as error:
        request_model(lambda _: httpx.Response(200, json={'status':'incomplete', 'usage':{'output_tokens':1200}}))
    assert error.value.code == 'incomplete_response'
    assert error.value.usage['output_tokens'] == 1200


def test_strict_schema_nullable_fields_required_without_mutation():
    original = Decision.model_json_schema()
    result = strict_schema(original)
    action = result['$defs']['AgentAction']
    assert set(action['required']) == set(action['properties'])
    assert 'default' not in action['properties']['direction']
    assert original == Decision.model_json_schema()

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

ROOT = Path(__file__).resolve().parents[2]
PRIMARY, FALLBACK = 'openai/gpt-oss-20b', 'openai/gpt-oss-120b'
# the exact error body from the production log
MODEL_NOT_FOUND = ('{"error":{"message":"The model `qwen/qwen3.6-27b` does not exist or you do not have access '
                   'to it.","type":"invalid_request_error","code":"model_not_found"}}')


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code, self.ok, self._payload, self.text = status_code, 200 <= status_code < 300, payload, text

    def json(self):
        return self._payload


def reply(content='See a general practitioner.'):
    return FakeResponse(200, {'choices': [{'message': {'content': content}}]})


def tool_call_message(**extra):
    return FakeResponse(200, {'choices': [{'message': {
        'role': 'assistant', 'content': None, **extra,
        'tool_calls': [{'id': 'c1', 'type': 'function',
                        'function': {'name': 'find_doctors', 'arguments': '{"specialization": "Cardiology"}'}}]}}]})


@pytest.fixture(autouse=True)
def cfg(settings):
    settings.GROQ_API_KEY = 'gsk_test'
    settings.GROQ_MODEL = PRIMARY
    settings.GROQ_MODEL_FALLBACKS = [FALLBACK]
    cache.clear()
    yield
    cache.clear()


def chat(client, message='hello'):
    return client.post(reverse('ai_chat'), json.dumps({'message': message}), content_type='application/json')


def models_sent(mock_post):
    return [c.kwargs['json']['model'] for c in mock_post.call_args_list]


@pytest.mark.django_db
@patch('requests.post')
def test_unavailable_primary_model_falls_back_and_succeeds(mock_post, client):
    mock_post.side_effect = [FakeResponse(404, text=MODEL_NOT_FOUND), reply()]
    r = chat(client)
    assert r.status_code == 200 and r.json()['reply'] == 'See a general practitioner.'
    assert models_sent(mock_post) == [PRIMARY, FALLBACK]


@pytest.mark.django_db
@patch('requests.post')
def test_all_models_unavailable_returns_neutral_error_and_logs(mock_post, client, caplog):
    mock_post.return_value = FakeResponse(404, text=MODEL_NOT_FOUND)
    r = chat(client)
    assert r.status_code == 502 and 'temporarily unavailable' in r.json()['error']
    assert models_sent(mock_post) == [PRIMARY, FALLBACK]
    assert 'model_not_found' in caplog.text and 'trying the next model' in caplog.text


@pytest.mark.django_db
@patch('requests.post')
def test_bad_key_does_not_trigger_fallback(mock_post, client):
    mock_post.return_value = FakeResponse(401, text='{"error":{"message":"Invalid API Key"}}')
    assert chat(client).status_code == 502
    assert models_sent(mock_post) == [PRIMARY]                     # retrying another model can't fix a bad key


@pytest.mark.django_db
@patch('requests.post')
def test_bad_request_unrelated_to_model_does_not_trigger_fallback(mock_post, client):
    mock_post.return_value = FakeResponse(400, text='{"error":{"message":"messages must not be empty"}}')
    chat(client)
    assert models_sent(mock_post) == [PRIMARY]


@pytest.mark.django_db
@patch('requests.post')
def test_tool_flow_reuses_the_model_that_worked(mock_post, client):
    mock_post.side_effect = [FakeResponse(404, text=MODEL_NOT_FOUND), tool_call_message(), reply('Try cardiology.')]
    r = chat(client, 'my heart hurts')
    assert r.status_code == 200 and r.json()['reply'] == 'Try cardiology.'
    assert models_sent(mock_post) == [PRIMARY, FALLBACK, FALLBACK]   # follow-up does not retry the dead model
    assert 'tools' not in mock_post.call_args_list[2].kwargs['json']


@pytest.mark.django_db
@patch('requests.post')
def test_assistant_message_is_sent_back_with_standard_fields_only(mock_post, client):
    mock_post.side_effect = [tool_call_message(reasoning='chain of thought', annotations=[], executed_tools=[]),
                             reply()]
    chat(client, 'my heart hurts')
    assistant = [m for m in mock_post.call_args_list[1].kwargs['json']['messages'] if m['role'] == 'assistant']
    assert len(assistant) == 1 and set(assistant[0]) == {'role', 'content', 'tool_calls'}


def load_settings(**env):
    code = "import healthtech.settings as s; print(s.GROQ_MODEL, s.GROQ_MODEL_FALLBACKS)"
    return subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True,
                          env={'PATH': '', 'DJANGO_DEBUG': 'True', **env})


def test_default_model_is_one_groq_documents_as_supporting_function_calling():
    r = load_settings()
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "openai/gpt-oss-20b ['openai/gpt-oss-120b']"


def test_model_and_fallbacks_can_be_overridden_and_are_trimmed():
    r = load_settings(GROQ_MODEL=' model-a ', GROQ_MODEL_FALLBACKS=' model-b , ,model-c ')
    assert r.stdout.strip() == "model-a ['model-b', 'model-c']"

"""Covers the production incident: the model called find_doctors after only "I am having a head pain from
morning and unable to do work", then Groq rejected the follow-up with:
  status=400 {"error":{"code":"tool_use_failed","message":"Tool choice is none, but model called a tool", ...}}
Two bugs, both fixed here: (1) is_model_unavailable() misclassified this as a model-not-found error because its
body happens to contain the word "model"; (2) the second-call failure discarded the doctors already found by
the tool call and returned a bare error.
"""
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from core.models import DoctorProfile, User
from core.views import is_generation_glitch, is_model_unavailable

PROD_BODY = ('{"error":{"message":"Tool choice is none, but model called a tool","type":"invalid_request_error",'
            '"code":"tool_use_failed","failed_generation":"{\\"name\\": \\"assistant<|channel|>final\\", '
            '\\"arguments\\": I understand you\\u2019ve had a headache...}"}}')


class FakeResponse:
    def __init__(self, status_code, text='', payload=None):
        self.status_code, self.ok, self.text, self._payload = status_code, 200 <= status_code < 300, text, payload

    def json(self):
        return self._payload


def text_reply(content='ok'):
    return FakeResponse(200, payload={'choices': [{'message': {'content': content}}]})


def tool_call(spec='Cardiology'):
    return FakeResponse(200, payload={'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': 'c1', 'type': 'function', 'function': {'name': 'find_doctors',
                                                       'arguments': json.dumps({'specialization': spec})}}]}}]})


def glitch():
    return FakeResponse(400, text=PROD_BODY)


# ---- classifiers ------------------------------------------------------------------------------------------
def test_tool_use_failed_is_not_classified_as_model_unavailable():
    # Regression: the old check matched status in (400,404) + 'model' in body, and this body says
    # "model called a tool" - so it was wrongly treated as "try the next model".
    assert is_model_unavailable(glitch()) is False


def test_tool_use_failed_is_classified_as_a_generation_glitch():
    assert is_generation_glitch(glitch()) is True


def test_real_model_not_found_is_still_classified_correctly():
    real = FakeResponse(404, text='{"error":{"message":"The model `x` does not exist","code":"model_not_found"}}')
    assert is_model_unavailable(real) is True and is_generation_glitch(real) is False


@pytest.mark.parametrize('status,text,expect_unavailable,expect_glitch', [
    (401, '{"error":{"message":"Invalid API Key"}}', False, False),
    (429, 'rate limited', False, False),
    (400, '{"error":{"message":"messages must not be empty"}}', False, False),
])
def test_other_errors_are_neither(status, text, expect_unavailable, expect_glitch):
    r = FakeResponse(status, text=text)
    assert is_model_unavailable(r) is expect_unavailable and is_generation_glitch(r) is expect_glitch


# ---- through the endpoint --------------------------------------------------------------------------------
def make_doctor(spec='Cardiologist', years=10):
    user = User.objects.create_user(username='drheart', password='pw', is_doctor=True)
    return DoctorProfile.objects.create(user=user, specialization=spec, experience_years=years, is_verified=True)


@pytest.fixture(autouse=True)
def cfg(settings):
    settings.GROQ_API_KEY = 'gsk_test'
    settings.GROQ_MODEL = 'openai/gpt-oss-20b'
    settings.GROQ_MODEL_FALLBACKS = ['openai/gpt-oss-120b']
    cache.clear()
    yield
    cache.clear()


def chat(client, message='my head hurts'):
    return client.post(reverse('ai_chat'), json.dumps({'message': message}), content_type='application/json')


def models_sent(mock_post):
    return [c.kwargs['json']['model'] for c in mock_post.call_args_list]


@pytest.mark.django_db
@patch('requests.post')
def test_glitch_does_not_trigger_a_model_fallback(mock_post, client):
    # The exact production sequence: tool call succeeds, follow-up glitches, retry succeeds.
    mock_post.side_effect = [tool_call(), glitch(), text_reply('A cardiologist can help with this.')]
    r = chat(client)
    assert r.status_code == 200 and r.json()['reply'] == 'A cardiologist can help with this.'
    assert models_sent(mock_post) == ['openai/gpt-oss-20b'] * 3   # never tried gpt-oss-120b: this wasn't a model problem


@pytest.mark.django_db
@patch('requests.post')
def test_glitch_is_retried_once_and_recovers(mock_post, client):
    mock_post.side_effect = [tool_call(), glitch(), text_reply('See a cardiologist.')]
    r = chat(client)
    assert r.status_code == 200 and r.json()['reply'] == 'See a cardiologist.'
    assert mock_post.call_count == 3


@pytest.mark.django_db
@patch('requests.post')
def test_doctors_already_found_are_not_discarded_when_the_retry_also_fails(mock_post, client, caplog):
    make_doctor()
    mock_post.side_effect = [tool_call('Cardiology'), glitch(), glitch()]
    r = chat(client)
    data = r.json()
    assert r.status_code == 200                                      # not a bare error
    assert [d['name'] for d in data['doctors']] == ['Dr. drheart']    # the doctors ARE still returned
    assert data['stage'] == 'summary' and data['specialization'] == 'Cardiologist'
    assert 'trouble writing a full summary' in data['reply'] and 'Cardiologist' in data['reply']
    assert 'not a doctor' in data['reply'].lower() or "i'm an ai" in data['reply'].lower()
    assert mock_post.call_count == 3
    assert caplog.text.count('tool_use_failed') >= 1 or 'second (after retry)' in caplog.text


@pytest.mark.django_db
@patch('requests.post')
def test_no_matching_doctor_still_gets_an_honest_fallback_reply(mock_post, client):
    mock_post.side_effect = [tool_call('Neurology'), glitch(), glitch()]
    r = chat(client)
    data = r.json()
    assert r.status_code == 200 and data['doctors'] == []
    assert data['specialization_searched'] == 'Neurology'
    assert 'browse all doctors' in data['reply'] or 'general physician' in data['reply'].lower()


@pytest.mark.django_db
@patch('requests.post')
def test_a_real_second_call_failure_unrelated_to_tool_use_is_not_retried(mock_post, client):
    make_doctor()
    bad_key = FakeResponse(401, text='{"error":{"message":"Invalid API Key"}}')
    mock_post.side_effect = [tool_call('Cardiology'), bad_key]
    r = chat(client)
    assert mock_post.call_count == 2                                 # no retry attempted
    assert r.status_code == 200 and r.json()['doctors'] != []        # still recovers with a fallback reply


@pytest.mark.django_db
@patch('requests.post')
def test_prompt_forbids_calling_the_tool_before_the_final_summary(mock_post, client):
    mock_post.return_value = text_reply()
    chat(client, 'hi')
    prompt = mock_post.call_args_list[0].kwargs['json']['messages'][0]['content']
    assert 'NEVER on a turn where you are still asking a question' in prompt

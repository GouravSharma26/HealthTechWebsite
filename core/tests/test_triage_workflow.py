import json
import re
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from core.models import ChatMessage, DoctorProfile, Notification, User
from core.utils import (MAX_FOLLOW_UPS, clean_chat_history, count_follow_up_questions, parse_urgency,
                        screen_for_emergency)


# ---- deterministic emergency screen -----------------------------------------------------------------
@pytest.mark.parametrize('text, categories', [
    ('my chest hurts when I run', ['cardiac']),
    ("I can't breathe and my lips are blue", ['breathing']),
    ('my dad has slurred speech and his face is drooping', ['stroke']),
    ('I want to kill myself', ['self_harm']),
    ('she passed out and is not responding', ['consciousness']),
    ('I fainted and my chest hurts', ['consciousness', 'cardiac']),
    ('my tongue is swelling after eating peanuts', ['allergy']),
    ('there is heavy bleeding from his leg', ['bleeding']),
    ('I keep coughing up blood', ['bleeding']),
    ('not sure if I have chest pain', ['cardiac']),                     # uncertainty is NOT a negation
    ('chest pain but no shortness of breath', ['cardiac']),
    ('I swallowed poison', ['poisoning']),
])
def test_emergency_screen_flags(text, categories):
    assert [a['category'] for a in screen_for_emergency(text)] == categories


@pytest.mark.parametrize('text', [
    'I have a mild headache', 'no chest pain, just a cough', 'I do not have chest pain', 'I never had trouble breathing',
    'I have a sore throat and swollen glands', 'my knee hurts when I run', '', None,
])
def test_emergency_screen_stays_quiet_for_benign_or_negated_text(text):
    assert screen_for_emergency(text) == []


def test_emergency_screen_caps_alerts_and_returns_actionable_text():
    found = screen_for_emergency('unconscious, cannot breathe, chest pain, face drooping, heavy bleeding')
    assert len(found) == 2
    assert all(a['title'] and '112' in a['message'] for a in found)


# ---- follow-up budget ------------------------------------------------------------------------------------
def turn(stage):
    return {'role': 'assistant', 'content': 'x', 'stage': stage}


def test_follow_up_counter_counts_questions_since_the_last_summary():
    assert count_follow_up_questions([]) == 0
    assert count_follow_up_questions([turn('question'), turn('question')]) == 2
    assert count_follow_up_questions([turn('question'), turn('summary'), turn('question')]) == 1
    assert count_follow_up_questions([turn('question'), turn('summary')]) == 0
    assert count_follow_up_questions([{'role': 'user', 'content': 'hi'}]) == 0


def test_history_stage_is_validated():
    cleaned = clean_chat_history([
        {'role': 'assistant', 'content': 'a', 'stage': 'summary'},
        {'role': 'assistant', 'content': 'b', 'stage': 'hacked'},
        {'role': 'user', 'content': 'c', 'stage': 'summary'}])
    assert cleaned[0]['stage'] == 'summary' and 'stage' not in cleaned[1] and 'stage' not in cleaned[2]


@pytest.mark.parametrize('reply, expected', [
    ('**Emergency status:** URGENT - see a doctor within 24 hours - reason', 'urgent'),
    ('**Emergency status:** \U0001f534 EMERGENCY - call 112 now', 'emergency'),
    ('**Emergency status:** ROUTINE - book soon', 'routine'),
    ('**Emergency status:** SELF-CARE - monitor at home', 'self_care'),
    ('emergency status: self care', 'self_care'),
    ('How long has this been happening?', None), ('', None), (None, None),
])
def test_urgency_is_read_from_the_summary_template(reply, expected):
    assert parse_urgency(reply) == expected


# ---- through the chat endpoint -----------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload):
        self.status_code, self.ok, self._payload, self.text = 200, True, payload, ''

    def json(self):
        return self._payload


def text_reply(content='ok'):
    return FakeResponse({'choices': [{'message': {'content': content}}]})


def tool_call(arguments='{"specialization": "Cardiology"}'):
    return FakeResponse({'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': 'c1', 'type': 'function', 'function': {'name': 'find_doctors', 'arguments': arguments}}]}}]})


@pytest.fixture(autouse=True)
def cfg(settings):
    settings.GROQ_API_KEY = 'gsk_test'
    cache.clear()
    yield
    cache.clear()


def make_doctor(username='drheart', spec='Cardiologist', years=10):
    user = User.objects.create_user(username=username, password='pw', is_doctor=True)
    return DoctorProfile.objects.create(user=user, specialization=spec, experience_years=years, is_verified=True)


def chat(client, message, history=None):
    body = {'message': message}
    if history is not None:
        body['history'] = history
    return client.post(reverse('ai_chat'), json.dumps(body), content_type='application/json')


def system_prompt(mock_post):
    return mock_post.call_args_list[0].kwargs['json']['messages'][0]['content']


@pytest.mark.django_db
@patch('requests.post')
def test_emergency_message_returns_alerts_and_primes_the_model(mock_post, client):
    mock_post.return_value = text_reply('Please call 112 now.')
    r = chat(client, 'my chest hurts and I feel faint').json()
    assert [a['category'] for a in r['alerts']] == ['cardiac']
    assert '112' in r['alerts'][0]['message']
    assert 'SAFETY SCREEN' in system_prompt(mock_post) and 'cardiac' in system_prompt(mock_post)


@pytest.mark.django_db
@patch('requests.post')
def test_benign_message_has_no_alert_and_only_the_latest_message_is_screened(mock_post, client):
    mock_post.return_value = text_reply('How long has it lasted?')
    history = [{'role': 'user', 'content': 'earlier I had chest pain'}, {'role': 'assistant', 'content': 'noted'}]
    r = chat(client, 'now I only have a mild headache', history).json()
    assert 'alerts' not in r and 'SAFETY SCREEN' not in system_prompt(mock_post)


@pytest.mark.django_db
@patch('requests.post')
@pytest.mark.parametrize('asked, must_contain', [
    (0, None), (2, 'asked 2 follow-up question(s)'), (MAX_FOLLOW_UPS, 'Do NOT ask another question'),
])
def test_prompt_tells_the_model_how_many_questions_it_has_used(mock_post, client, asked, must_contain):
    mock_post.return_value = text_reply()
    history = []
    for i in range(asked):
        history += [{'role': 'user', 'content': f'a{i}'}, {'role': 'assistant', 'content': f'q{i}?', 'stage': 'question'}]
    chat(client, 'still the same', history)
    prompt = system_prompt(mock_post)
    if must_contain:
        assert must_contain in prompt
    else:
        assert 'follow-up question(s) so far' not in prompt and 'Do NOT ask another question' not in prompt


@pytest.mark.django_db
@patch('requests.post')
def test_question_turns_leave_the_response_shape_unchanged(mock_post, client):
    mock_post.return_value = text_reply('How long has this been going on?')
    assert chat(client, 'I feel unwell').json() == {'reply': 'How long has this been going on?', 'doctors': []}


@pytest.mark.django_db
@patch('requests.post')
def test_summary_turn_reports_stage_urgency_specialization_and_cards(mock_post, client):
    make_doctor()
    summary = ('**Emergency status:** URGENT - see a doctor within 24 hours - exertional chest pain\n'
               '**Recommended specialist:** Cardiologist')
    mock_post.side_effect = [tool_call(), text_reply(summary)]
    r = chat(client, 'about two weeks, 6 out of 10, no other symptoms').json()
    assert r['stage'] == 'summary' and r['urgency'] == 'urgent' and r['specialization'] == 'Cardiologist'
    assert [d['name'] for d in r['doctors']] == ['Dr. drheart'] and r['doctors'][0]['url'].startswith('/doctor/')


@pytest.mark.django_db
@patch('requests.post')
def test_summary_without_matching_doctors_reports_what_was_searched(mock_post, client):
    mock_post.side_effect = [tool_call('{"specialization": "Neurologist"}'), text_reply('**Emergency status:** ROUTINE')]
    r = chat(client, 'headaches for a month').json()
    assert r['stage'] == 'summary' and r['doctors'] == [] and r['specialization_searched'] == 'Neurologist'
    assert 'specialization' not in r


@pytest.mark.django_db
@patch('requests.post')
def test_malformed_tool_arguments_do_not_crash_the_chat(mock_post, client):
    mock_post.side_effect = [tool_call('{not json'), text_reply('Sorry, could you rephrase?')]
    r = chat(client, 'my knee hurts')
    assert r.status_code == 200 and r.json()['doctors'] == []


@pytest.mark.django_db
@patch('requests.post')
def test_prompt_encodes_the_workflow_and_guardrails(mock_post, client):
    mock_post.return_value = text_reply()
    chat(client, 'hello')
    prompt = system_prompt(mock_post)
    for needle in ('ONE question at a time', 'after at most 4 follow-up questions', 'Red flags that change urgency',
                   'Onset and duration', 'Severity from 0 to 10', 'EMERGENCY (call emergency services now)',
                   'URGENT (see a doctor within 24 hours)', '**Emergency status:**', '**Recommended specialist:**',
                   '**Next steps:**', '**Seek emergency help immediately if:**', 'SESSION MEMORY',
                   'Never mention, assume or ask about earlier chats', 'not a doctor',
                   'Never suggest specific prescription medicines', 'Never dismiss or ignore possible emergency indicators'):
        assert needle in prompt, needle


@pytest.mark.django_db
@patch('requests.post')
def test_server_keeps_no_conversation_state(mock_post, client):
    mock_post.return_value = text_reply()
    before = (User.objects.count(), ChatMessage.objects.count(), Notification.objects.count(), len(client.session.keys()))
    chat(client, 'my chest hurts', [{'role': 'user', 'content': 'hello'}])
    after = (User.objects.count(), ChatMessage.objects.count(), Notification.objects.count(), len(client.session.keys()))
    assert before == after


# ---- widget: session-only memory and safe rendering ------------------------------------------------------
@pytest.mark.django_db
def test_widget_memory_is_session_only_and_rendering_is_safe(client):
    html = client.get(reverse('home')).content.decode()
    script = html[html.index('const BOT_STORAGE_KEY'):html.index('async function sendBotMessage')]
    assert 'sessionStorage' in script and 'localStorage' not in script         # cleared with the tab, never persisted
    for needle in ('function botNewChat', "href = 'tel:112'", 'not a doctor', 'call 112', 'erased when you close it'):
        assert needle in script, needle
    ui = script[script.index('function botSafeUrl'):script.index('function botRenderEvent')]
    assert 'innerHTML' not in ui                                               # alerts/cards/status use textContent only
    assert 'window.DOMPurify' in script                                        # bubble HTML is sanitized (or plain text)


# ---- the framework document must describe what the code actually does ------------------------------------------
@pytest.mark.django_db
def test_framework_doc_matches_the_code(client):
    from pathlib import Path
    from core.utils import EMERGENCY_CATEGORIES
    doc = (Path(__file__).resolve().parents[2] / 'docs' / 'triage-framework.md').read_text(encoding='utf-8')
    html = client.get(reverse('home')).content.decode()
    greeting = re.search(r'const BOT_GREETING = "(.*?)";\n', html, re.S).group(1).replace('\\n', '\n').replace('\\u2022', '\u2022')
    assert greeting in doc                                                     # the exact greeting text
    with patch('requests.post', return_value=text_reply()) as mock_post:
        client.post(reverse('ai_chat'), json.dumps({'message': 'hello'}), content_type='application/json')
    prompt = mock_post.call_args_list[0].kwargs['json']['messages'][0]['content']
    template = prompt[prompt.index('**Emergency status:** <EMERGENCY'):prompt.index('If find_doctors found no doctors')].rstrip()
    assert template in doc                                                     # the exact summary template
    assert f'{MAX_FOLLOW_UPS} follow-up questions' in doc
    for category, _, title, _ in EMERGENCY_CATEGORIES:
        assert f'`{category}`' in doc and title in doc

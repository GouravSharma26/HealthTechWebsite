import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from core.models import DoctorProfile, User
from core.utils import available_specializations, doctors_matching_specialization, specialization_stem


@pytest.mark.parametrize('term, stem', [
    ('Cardiology', 'cardi'), ('Cardiologist', 'cardi'),
    ('Pediatrics', 'pediatr'), ('Pediatrician', 'pediatr'),
    ('Dermatology', 'dermat'), ('Dermatologist', 'dermat'),
    ('Urology', 'urolog'), ('Urologist', 'urolog'),          # 'ur' would be too short to be a useful stem
    ('Oncology', 'onc'), ('Oncologist', 'onc'),
    ('Psychiatry', 'psych'), ('Psychiatrist', 'psych'),
    ('Orthopedics', 'orthoped'), ('Orthopedic Surgeon', 'orthoped'),
    ('General Physician', 'general'), ('  ', ''), (None, ''),
])
def test_specialization_stem(term, stem):
    assert specialization_stem(term) == stem


def make_doctor(username, specialization, verified=True, years=5):
    user = User.objects.create_user(username=username, password='pw', is_doctor=True)
    return DoctorProfile.objects.create(user=user, specialization=specialization,
                                        experience_years=years, is_verified=verified)


@pytest.fixture
def doctors(db):
    return {
        'cardio_senior': make_doctor('drheart', 'Cardiologist', years=20),
        'cardio_junior': make_doctor('drjunior', 'Cardiologist', years=3),
        'cardio_unverified': make_doctor('drpending', 'Cardiologist', verified=False, years=30),
        'derm': make_doctor('drskin', 'Dermatologist'),
        'peds': make_doctor('drkids', 'Pediatrician'),
    }


@pytest.mark.parametrize('asked', ['Cardiology', 'Cardiologist', 'cardiology', 'CARDIOLOGIST', 'Cardiology specialist'])
def test_cardiology_finds_cardiologists_only_verified_and_most_experienced_first(doctors, asked):
    found = list(doctors_matching_specialization(asked))
    assert [d.user.username for d in found] == ['drheart', 'drjunior']      # unverified excluded, sorted by experience


def test_pediatrics_finds_pediatrician(doctors):
    assert [d.user.username for d in doctors_matching_specialization('Pediatrics')] == ['drkids']


def test_unknown_specialty_and_blank_return_nothing(doctors):
    assert list(doctors_matching_specialization('Astrophysics')) == []
    assert list(doctors_matching_specialization('')) == []


def test_limit_is_respected(db):
    for i in range(8):
        make_doctor(f'c{i}', 'Cardiologist')
    assert len(doctors_matching_specialization('Cardiology', limit=5)) == 5


def test_available_specializations_lists_only_verified_distinct_sorted(doctors):
    assert available_specializations() == ['Cardiologist', 'Dermatologist', 'Pediatrician']


# ---- end to end through the chat endpoint (the scenario from the production screenshot) -----------
class FakeResponse:
    def __init__(self, payload):
        self.status_code, self.ok, self._payload, self.text = 200, True, payload, ''

    def json(self):
        return self._payload


def tool_call(spec):
    return FakeResponse({'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': 'c1', 'type': 'function', 'function': {'name': 'find_doctors',
                                                       'arguments': json.dumps({'specialization': spec})}}]}}]})


@pytest.mark.django_db
@patch('requests.post')
def test_chat_recommends_cardiologists_when_the_model_asks_for_cardiology(mock_post, client, doctors, settings):
    settings.GROQ_API_KEY = 'gsk_test'
    cache.clear()
    final = FakeResponse({'choices': [{'message': {'content': 'A cardiologist is a good next step.'}}]})
    mock_post.side_effect = [tool_call('Cardiology'), final]

    r = client.post(reverse('ai_chat'), json.dumps({'message': 'my chest hurts when I run'}),
                    content_type='application/json')

    assert r.status_code == 200
    names = [d['name'] for d in r.json()['doctors']]
    assert names == ['Dr. drheart', 'Dr. drjunior']                         # was [] before the fix
    # the model is told how many were found, so it stops saying "I couldn't find any"
    tool_msg = [m for m in mock_post.call_args_list[1].kwargs['json']['messages'] if m['role'] == 'tool'][0]
    assert json.loads(tool_msg['content'])['doctors_found'] == 2
    # ...and the first request told it which specializations really exist
    tools = mock_post.call_args_list[0].kwargs['json']['tools']
    assert 'Cardiologist, Dermatologist, Pediatrician' in tools[0]['function']['description']


@pytest.mark.django_db
@patch('requests.post')
def test_chat_without_any_verified_doctors_still_works(mock_post, client, settings, db):
    settings.GROQ_API_KEY = 'gsk_test'
    cache.clear()
    make_doctor('drpending', 'Cardiologist', verified=False)
    final = FakeResponse({'choices': [{'message': {'content': 'None available right now.'}}]})
    mock_post.side_effect = [tool_call('Cardiology'), final]
    r = client.post(reverse('ai_chat'), json.dumps({'message': 'chest pain'}), content_type='application/json')
    assert r.status_code == 200 and r.json()['doctors'] == []
    assert 'Specializations currently available' not in mock_post.call_args_list[0].kwargs['json']['tools'][0]['function']['description']


# ---- seed script -------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_sample_data_creates_verified_doctors_and_repairs_old_unverified_ones(monkeypatch):
    monkeypatch.setenv('SAMPLE_DATA_PASSWORD', 'Test-Pw-12345!')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    try:
        import create_sample_data
    finally:
        sys.path.pop(0)
    create_sample_data.create_sample_doctors()
    assert DoctorProfile.objects.count() == 4 and not DoctorProfile.objects.filter(is_verified=False).exists()

    DoctorProfile.objects.update(is_verified=False)                          # doctors seeded before this fix
    create_sample_data.create_sample_doctors()
    assert DoctorProfile.objects.count() == 4                                # no duplicates
    assert not DoctorProfile.objects.filter(is_verified=False).exists()      # repaired

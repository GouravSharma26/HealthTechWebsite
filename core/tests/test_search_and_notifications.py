import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from core.models import User, DoctorProfile, Notification
from core.search import search_doctors, text_search_doctors


@pytest.fixture
def doctors(db):
    made = []
    for name, spec in [('drheart', 'Cardiology'), ('drbrain', 'Neurology')]:
        u = User.objects.create_user(username=name, password='pw', is_doctor=True)
        made.append(DoctorProfile.objects.create(user=u, specialization=spec))
    return made


def test_text_search_matches_specialization_and_username(doctors):
    assert [d.specialization for d in text_search_doctors('cardio')] == ['Cardiology']
    assert [d.user.username for d in text_search_doctors('drbrain')] == ['drbrain']


def test_search_falls_back_to_text_when_model_unavailable(doctors):
    with patch('core.search.get_model', return_value=None):
        results = search_doctors('Cardiology')
    assert [d.specialization for d in results] == ['Cardiology']


def test_search_falls_back_to_text_when_no_embeddings_yet(doctors):
    # model "loads" but no doctor has an embedding (fresh deploy, command not run yet)
    with patch('core.search.get_model', return_value=MagicMock()):
        results = search_doctors('Neurology')
    assert [d.specialization for d in results] == ['Neurology']


def test_doctors_page_search_returns_matches(client, doctors):
    with patch('core.search.get_model', return_value=None):
        r = client.get(reverse('doctors'), {'q': 'Cardiology'})
    assert r.status_code == 200
    assert len(r.context['doctors']) == 1


def test_api_search_returns_matches(client, doctors):
    with patch('core.search.get_model', return_value=None):
        r = client.get(reverse('api_search_doctors'), {'q': 'Neuro'})
    assert r.status_code == 200
    assert [x['specialization'] for x in r.json()['results']] == ['Neurology']


def test_notification_saves_even_if_channel_layer_fails(doctors):
    layer = MagicMock()
    layer.group_send.side_effect = ConnectionError('redis down')
    with patch('core.models.get_channel_layer', return_value=layer):
        n = Notification.objects.create(user=doctors[0].user, message='Patient x requested to cancel')
    assert Notification.objects.filter(id=n.id).exists()

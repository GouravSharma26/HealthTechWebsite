import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from django.core.cache import cache
from django.urls import reverse

from core.models import DoctorProfile, PatientProfile, User
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


# ---- rating + distance ranking, and the geolocation input that feeds it ---------------------------------------
from core.utils import haversine_km, rank_doctors_by_rating_and_distance, fetch_driving_distances_km  # noqa: E402
from core.views import _parse_optional_coords  # noqa: E402
from core.models import Review  # noqa: E402
from django.db.models import Avg, Count  # noqa: E402


def make_review(doctor, patient_user, rating):
    patient = PatientProfile.objects.create(user=patient_user)
    return Review.objects.create(doctor=doctor, patient=patient, rating=rating, text='ok')


def test_haversine_is_zero_for_the_same_point_and_matches_a_known_distance():
    assert haversine_km(12.9716, 77.5946, 12.9716, 77.5946) == pytest.approx(0, abs=1e-6)
    # Delhi <-> Mumbai, ~1150 km great-circle
    assert haversine_km(28.6139, 77.2090, 19.0760, 72.8777) == pytest.approx(1150, rel=0.05)


@pytest.mark.django_db
def test_ranking_sorts_by_rating_first_then_distance_then_experience():
    high = make_doctor('drhigh', 'Cardiologist', years=2)     # far, but 5-star
    near = make_doctor('drnear', 'Cardiologist', years=2)      # close, but unrated
    far_unrated = make_doctor('drfar', 'Cardiologist', years=20)  # far AND unrated - loses on both counts
    high.latitude, high.longitude = 19.0760, 72.8777    # Mumbai
    near.latitude, near.longitude = 28.61, 77.21         # ~ Delhi, essentially at the patient
    far_unrated.latitude, far_unrated.longitude = 19.0760, 72.8777
    for d in (high, near, far_unrated):
        d.save()
    make_review(high, User.objects.create_user('p1', password='pw'), 5)

    ranked = rank_doctors_by_rating_and_distance(
        DoctorProfile.objects.filter(id__in=[high.id, near.id, far_unrated.id])
                             .annotate(avg_rating=Avg('reviews__rating'), rating_count=Count('reviews')),
        patient_lat=28.6139, patient_lng=77.2090,   # Delhi
    )
    assert [d.user.username for d, _ in ranked] == ['drhigh', 'drnear', 'drfar']   # rated beats unrated regardless of distance
    assert ranked[0][1] > 1000 and ranked[1][1] < 5                                # distances are sane (km)


@pytest.mark.django_db
def test_ranking_falls_back_to_experience_when_no_location_or_ratings_given():
    junior = make_doctor('drjr', 'Cardiologist', years=2)
    senior = make_doctor('drsr', 'Cardiologist', years=20)
    ranked = rank_doctors_by_rating_and_distance(
        doctors_matching_specialization('Cardiologist'), patient_lat=None, patient_lng=None)
    assert [d.user.username for d, dist in ranked] == ['drsr', 'drjr']
    assert all(dist is None for _, dist in ranked)   # no patient location given -> no distance computed


@pytest.mark.parametrize('lat, lng, valid', [
    (12.9, 77.5, True), ('12.9', '77.5', True),        # numeric strings from a JSON body are fine
    (91, 77.5, False), (12.9, 181, False),              # out of range
    (None, 77.5, False), (12.9, None, False),           # one missing -> pair discarded
    ('nope', 77.5, False), (None, None, False),
])
def test_optional_coords_are_validated_defensively(lat, lng, valid):
    result = _parse_optional_coords(lat, lng)
    assert result == ((float(lat), float(lng)) if valid else (None, None))


@pytest.mark.django_db
@patch('requests.get')
@patch('requests.post')
def test_chat_endpoint_includes_rating_and_real_driving_distance_in_doctor_cards(mock_post, mock_get, client, settings):
    settings.GROQ_API_KEY = 'gsk_test'
    cache.clear()
    doc = make_doctor('drheart', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0760, 72.8777
    doc.save()
    make_review(doc, User.objects.create_user('p2', password='pw'), 4)
    make_review(doc, User.objects.create_user('p3', password='pw'), 5)

    # OSRM table response: one source (the patient), one destination (this doctor). 1,400,000 m is a
    # plausible real Delhi->Mumbai driving distance (vs. ~1150 km great-circle) - the actual number that
    # should now reach the card, not the haversine estimate, so it matches what the doctor's own profile
    # page computes via the same routing engine (Leaflet Routing Machine / OSRM).
    mock_get.return_value = FakeResponse({'code': 'Ok', 'distances': [[1_400_000]]})
    final = FakeResponse({'choices': [{'message': {'content': 'A cardiologist is a good next step.'}}]})
    mock_post.side_effect = [tool_call('Cardiology'), final]
    body = {'message': 'my chest hurts when I run', 'latitude': 28.6139, 'longitude': 77.2090}
    r = client.post(reverse('ai_chat'), json.dumps(body), content_type='application/json')

    card = r.json()['doctors'][0]
    assert card['rating'] == 4.5 and card['rating_count'] == 2
    assert card['distance_km'] == 1400.0                 # the real driving distance, not the ~1150km haversine estimate
    assert mock_get.call_count == 1                        # one batched call, not one per doctor
    assert 'router.project-osrm.org' in mock_get.call_args.args[0]


@pytest.mark.django_db
@patch('requests.get')
@patch('requests.post')
def test_distance_falls_back_to_straight_line_when_osrm_is_unavailable(mock_post, mock_get, client, settings):
    settings.GROQ_API_KEY = 'gsk_test'
    cache.clear()
    doc = make_doctor('drheart2', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0760, 72.8777
    doc.save()

    mock_get.side_effect = requests.exceptions.ConnectionError('OSRM demo server unreachable')
    final = FakeResponse({'choices': [{'message': {'content': 'A cardiologist is a good next step.'}}]})
    mock_post.side_effect = [tool_call('Cardiology'), final]
    body = {'message': 'my chest hurts when I run', 'latitude': 28.6139, 'longitude': 77.2090}
    r = client.post(reverse('ai_chat'), json.dumps(body), content_type='application/json')

    card = r.json()['doctors'][0]
    assert r.status_code == 200
    assert card['distance_km'] == pytest.approx(1150, rel=0.05)   # falls back to the haversine estimate, not None


# ---- fetch_driving_distances_km: batched OSRM lookup, fail-open on any problem -----------------------------
from unittest.mock import Mock  # noqa: E402


@pytest.mark.django_db
@patch('requests.get')
def test_fetch_driving_distances_batches_all_doctors_into_one_request(mock_get):
    d1 = make_doctor('osrm1', 'Cardiologist')
    d2 = make_doctor('osrm2', 'Cardiologist')
    d1.latitude, d1.longitude = 19.0, 72.0
    d2.latitude, d2.longitude = 20.0, 73.0
    d1.save(); d2.save()
    mock_get.return_value = FakeResponse({'code': 'Ok', 'distances': [[500_000, 900_000]]})

    result = fetch_driving_distances_km(28.6, 77.2, [d1, d2])

    assert result == {d1.id: 500.0, d2.id: 900.0}
    assert mock_get.call_count == 1
    call_url = mock_get.call_args.args[0]
    assert f"{d1.longitude},{d1.latitude}" in call_url and f"{d2.longitude},{d2.latitude}" in call_url


@pytest.mark.django_db
@patch('requests.get')
def test_fetch_driving_distances_fails_open_on_non_ok_status(mock_get):
    doc = make_doctor('osrmfail1', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0, 72.0
    doc.save()
    mock_get.return_value = Mock(ok=False, status_code=500)
    assert fetch_driving_distances_km(28.6, 77.2, [doc]) == {}


@pytest.mark.django_db
@patch('requests.get')
def test_fetch_driving_distances_fails_open_on_non_ok_osrm_code(mock_get):
    doc = make_doctor('osrmfail2', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0, 72.0
    doc.save()
    mock_get.return_value = FakeResponse({'code': 'NoRoute'})
    assert fetch_driving_distances_km(28.6, 77.2, [doc]) == {}


@pytest.mark.django_db
@patch('requests.get')
def test_fetch_driving_distances_fails_open_on_mismatched_response_length(mock_get):
    doc = make_doctor('osrmfail3', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0, 72.0
    doc.save()
    mock_get.return_value = FakeResponse({'code': 'Ok', 'distances': [[]]})   # OSRM returned nothing for the one destination we asked for
    assert fetch_driving_distances_km(28.6, 77.2, [doc]) == {}


@pytest.mark.django_db
@patch('requests.get')
def test_fetch_driving_distances_fails_open_on_network_exception(mock_get):
    doc = make_doctor('osrmfail4', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0, 72.0
    doc.save()
    mock_get.side_effect = ConnectionError('boom')
    assert fetch_driving_distances_km(28.6, 77.2, [doc]) == {}


def test_fetch_driving_distances_skips_the_request_entirely_without_a_patient_location():
    assert fetch_driving_distances_km(None, None, [Mock(latitude=19.0, longitude=72.0)]) == {}


@pytest.mark.django_db
def test_ranking_prefers_driving_distance_over_haversine_when_both_are_available():
    near_by_road, far_by_road = make_doctor('roadnear', 'Cardiologist'), make_doctor('roadfar', 'Cardiologist')
    near_by_road.latitude, near_by_road.longitude = 19.0, 72.0     # same great-circle distance from patient...
    far_by_road.latitude, far_by_road.longitude = 19.01, 72.01     # ...but the driving distances disagree
    near_by_road.save(); far_by_road.save()

    ranked = rank_doctors_by_rating_and_distance(
        doctors_matching_specialization('Cardiologist'), patient_lat=28.6, patient_lng=77.2,
        driving_distances={near_by_road.id: 50.0, far_by_road.id: 2000.0},   # deliberately reversed vs. haversine
    )
    assert [d.user.username for d, _ in ranked] == ['roadnear', 'roadfar']
    assert ranked[0][1] == 50.0 and ranked[1][1] == 2000.0


@pytest.mark.django_db
def test_ranking_falls_back_to_haversine_for_a_doctor_missing_from_driving_distances():
    doc = make_doctor('partialosrm', 'Cardiologist')
    doc.latitude, doc.longitude = 19.0760, 72.8777
    doc.save()
    ranked = rank_doctors_by_rating_and_distance(
        doctors_matching_specialization('Cardiologist'), patient_lat=28.6139, patient_lng=77.2090,
        driving_distances={},   # OSRM didn't resolve this doctor - not None, just absent
    )
    assert ranked[0][1] == pytest.approx(1150, rel=0.05)   # haversine fallback, not None

"""The E2E booking tests book for TOMORROW in the server's timezone (see e2e/helpers/booking-date.ts).

They used to book "today" using the CI runner's (UTC) date, which only worked while the IST clock was between about
05:30 and 23:00. These tests pin the two server rules that make the fix valid, and replay the E2E booking scenarios
at every half hour of a UTC day, so the timezone dependency cannot come back unnoticed.
"""
import datetime
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from core.models import Appointment, DoctorProfile, DoctorTimeSlot, PatientProfile, User

INSTANTS = [f'2026-09-20 {h:02d}:{m:02d}:00' for h in range(24) for m in (0, 30)]   # UTC
SLOT_TIMES = [(0, 0), (6, 0), (12, 0), (23, 0), (23, 30)]


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']   # these tests create many users


@pytest.fixture
def doctor(db):
    user = User.objects.create_user(username='drtz', password='pw', is_doctor=True)
    profile = DoctorProfile.objects.create(user=user, specialization='General Physician', is_verified=True)
    for h, m in SLOT_TIMES:
        DoctorTimeSlot.objects.create(doctor=profile, start_time=datetime.time(h, m),
                                      end_time=datetime.time(h, m + 25 if m == 0 else 59), capacity=1)
    return profile


def make_patient(username):
    user = User.objects.create_user(username=username, password='pw', is_patient=True)
    PatientProfile.objects.get_or_create(user=user)
    return user


def slots(doctor, date, client=None):
    return (client or Client()).get(reverse('api_doctor_slots', args=[doctor.id]), {'date': date}).json()['slots']


def server_tomorrow():
    return (timezone.localdate() + timedelta(days=1)).isoformat()


@pytest.mark.parametrize('instant', INSTANTS)
def test_every_slot_is_open_tomorrow_at_any_time_of_day(doctor, instant):
    with freeze_time(instant):
        data = slots(doctor, server_tomorrow())
    assert len(data) == len(SLOT_TIMES)
    assert not any(s['is_passed'] or s['is_full'] for s in data)


def test_the_runners_utc_date_is_already_past_once_the_server_is_after_midnight_ist(doctor):
    # 20:15 UTC on the 20th is 01:45 IST on the 21st: this is the state in which the old "today" test found no slot.
    with freeze_time('2026-09-20 20:15:00'):
        utc_today = timezone.now().date().isoformat()
        assert utc_today == '2026-09-20' and timezone.localdate().isoformat() == '2026-09-21'
        assert all(s['is_passed'] for s in slots(doctor, utc_today))                 # a past date: nothing bookable
        server_today = slots(doctor, '2026-09-21')
        assert [s['is_passed'] for s in server_today] == [True, False, False, False, False]   # only 00:00 has passed


def test_late_in_the_ist_evening_no_slot_is_left_today(doctor):
    with freeze_time('2026-09-20 18:15:00'):                                           # 23:45 IST
        assert all(s['is_passed'] for s in slots(doctor, timezone.localdate().isoformat()))


@pytest.mark.django_db
@pytest.mark.parametrize('instant', INSTANTS[::2])                                    # hourly
def test_e2e_booking_scenarios_work_for_tomorrow_at_any_time_of_day(doctor, instant):
    with freeze_time(instant):
        tomorrow = server_tomorrow()
        slot = doctor.time_slots.order_by('start_time').last()
        a, b = make_patient(f'a{instant[11:13]}'), make_patient(f'b{instant[11:13]}')
        ca, cb = Client(), Client()
        ca.force_login(a)
        cb.force_login(b)
        url = reverse('doctor_detail', args=[doctor.id])
        form = {'action': 'book', 'date': tomorrow, 'time_slot_id': slot.id}

        # "a patient can book an available slot"
        ca.post(url, form, follow=True)
        assert Appointment.objects.filter(patient=a.patient_profile, date=tomorrow, time_slot=slot).count() == 1

        # "booking the same doctor twice while a request is pending is blocked"
        r = ca.post(url, {**form, 'time_slot_id': doctor.time_slots.first().id}, follow=True)
        assert Appointment.objects.filter(patient=a.patient_profile).count() == 1
        assert any('already have an active appointment' in str(m) for m in r.context['messages'])

        # "two concurrent patients cannot both book the last seat in a slot" (capacity 1)
        r = cb.post(url, form, follow=True)
        assert Appointment.objects.filter(time_slot=slot, date=tomorrow).count() == 1
        assert any('already full' in str(m) for m in r.context['messages'])

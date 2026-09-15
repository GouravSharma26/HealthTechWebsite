import pytest
from core.models import User, PatientProfile, DoctorProfile, Appointment, Notification
from datetime import date, time, timedelta
from django.utils import timezone
from django.core.management import call_command
from freezegun import freeze_time

@pytest.fixture
def setup_data(db):
    patient_user = User.objects.create_user(username='patient1', password='pw', is_patient=True)
    doctor_user = User.objects.create_user(username='doctor1', password='pw', is_doctor=True)
    
    patient = PatientProfile.objects.create(user=patient_user)
    doctor = DoctorProfile.objects.create(user=doctor_user, specialization='Cardiology')
    
    return patient, doctor

@pytest.mark.django_db
def test_auto_approve_requests_within_3_hours(setup_data):
    patient, doctor = setup_data
    now = timezone.make_aware(timezone.datetime(2025, 1, 1, 12, 0))
    
    with freeze_time(now):
        # Appointment at 14:00 (within 3 hours)
        appt = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            date=date(2025, 1, 1),
            time=time(14, 0),
            status='Cancel Requested'
        )
        
        call_command('auto_approve_requests')
        
        appt.refresh_from_db()
        assert appt.status == 'Cancelled'
        assert appt.auto_approved == True

@pytest.mark.django_db
def test_auto_approve_requests_within_4_hours_warning(setup_data):
    patient, doctor = setup_data
    now = timezone.make_aware(timezone.datetime(2025, 1, 1, 12, 0))
    
    with freeze_time(now):
        # Appointment at 15:30 (within 4 hours, but not within 3 hours)
        appt = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            date=date(2025, 1, 1),
            time=time(15, 30),
            status='Reschedule Requested',
            reschedule_date=date(2025, 1, 2),
            reschedule_time=time(10, 0)
        )
        
        call_command('auto_approve_requests')
        
        appt.refresh_from_db()
        assert appt.status == 'Reschedule Requested' # Not auto-approved yet
        assert appt.warning_sent == True
        assert Notification.objects.filter(user=doctor.user).exists()

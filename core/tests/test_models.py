import pytest
from core.models import User, PatientProfile, DoctorProfile, Appointment, DoctorTimeSlot
from datetime import date, time

@pytest.fixture
def setup_data(db):
    patient_user = User.objects.create_user(username='patient1', password='pw', is_patient=True)
    doctor_user = User.objects.create_user(username='doctor1', password='pw', is_doctor=True)
    
    patient = PatientProfile.objects.create(user=patient_user)
    doctor = DoctorProfile.objects.create(user=doctor_user, specialization='Cardiology')
    
    time_slot = DoctorTimeSlot.objects.create(doctor=doctor, start_time=time(10, 0), end_time=time(11, 0), capacity=1)
    
    appt = Appointment.objects.create(
        doctor=doctor,
        patient=patient,
        date=date(2025, 1, 1),
        time=time(10, 0),
        time_slot=time_slot,
        status='Pending'
    )
    
    return appt

@pytest.mark.django_db
def test_appointment_pending_to_confirmed(setup_data):
    appt = setup_data
    assert appt.status == 'Pending'
    
    appt.status = 'Confirmed'
    appt.save()
    
    appt.refresh_from_db()
    assert appt.status == 'Confirmed'

@pytest.mark.django_db
def test_appointment_cancel_requested_to_cancelled(setup_data):
    appt = setup_data
    appt.status = 'Cancel Requested'
    appt.save()
    
    appt.status = 'Cancelled'
    appt.save()
    
    appt.refresh_from_db()
    assert appt.status == 'Cancelled'

@pytest.mark.django_db
def test_appointment_reschedule_requested_to_confirmed(setup_data):
    appt = setup_data
    appt.status = 'Reschedule Requested'
    appt.reschedule_date = date(2025, 1, 2)
    appt.reschedule_time = time(11, 0)
    appt.save()
    
    appt.status = 'Confirmed'
    appt.date = appt.reschedule_date
    appt.time = appt.reschedule_time
    appt.save()
    
    appt.refresh_from_db()
    assert appt.status == 'Confirmed'
    assert appt.date == date(2025, 1, 2)
    assert appt.time == time(11, 0)

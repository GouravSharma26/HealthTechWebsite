import pytest
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
import datetime
import os
from core.models import Appointment, PatientProfile, DoctorProfile, User, DoctorTimeSlot
from core.utils import predict_risk

@pytest.fixture(autouse=True)
def reset_model_cache():
    import core.utils as utils
    utils._MODEL = None
    utils._MODEL_LOADED = False
    yield
    utils._MODEL = None
    utils._MODEL_LOADED = False

@pytest.mark.django_db
def test_noshow_model_training_and_prediction(settings, tmp_path):
    # Mock settings so we write to tmp_path and lower the min samples requirement
    settings.NOSHOW_MODEL_PATH = str(tmp_path / "test_model.joblib")
    settings.NOSHOW_MIN_SAMPLES = 2
    
    # 1. Create test data
    user_p = User.objects.create_user(username='patient1', password='pw')
    patient = PatientProfile.objects.create(user=user_p)
    
    user_d = User.objects.create_user(username='doctor1', password='pw')
    doctor = DoctorProfile.objects.create(user=user_d)
    
    slot = DoctorTimeSlot.objects.create(
        doctor=doctor,
        start_time=datetime.time(10, 0),
        end_time=datetime.time(11, 0)
    )
    
    # Create some past appointments
    now = timezone.now()
    
    # Appointment 1 (Completed)
    appt1 = Appointment.objects.create(
        patient=patient, doctor=doctor,
        date=(now - timedelta(days=10)).date(),
        time=datetime.time(10, 0),
        status='Completed'
    )
    # forcefully set created_at to 15 days ago so lead time is 5 days
    appt1.created_at = now - timedelta(days=15)
    appt1.save()
    
    # Appointment 2 (Cancelled)
    appt2 = Appointment.objects.create(
        patient=patient, doctor=doctor,
        date=(now - timedelta(days=5)).date(),
        time=datetime.time(10, 0),
        status='Cancelled'
    )
    appt2.created_at = now - timedelta(days=10)
    appt2.save()

    # Appointment 3 (Upcoming)
    appt3 = Appointment.objects.create(
        patient=patient, doctor=doctor,
        date=(now + timedelta(days=5)).date(),
        time=datetime.time(10, 0),
        status='Confirmed'
    )
    
    # 2. Train the model using the management command
    call_command('train_noshow_model')
    
    # 3. Predict risk for the upcoming appointment
    # We just need to make sure predict_risk doesn't crash and returns a valid string
    risk = predict_risk(appt3)
    
    assert risk in ['Low', 'Medium', 'High', 'Insufficient Data']
    
@pytest.mark.django_db
def test_noshow_insufficient_data(settings, tmp_path):
    # Test fallback when patient has no past history
    settings.NOSHOW_MODEL_PATH = str(tmp_path / "test_model.joblib")
    settings.NOSHOW_MIN_SAMPLES = 20 # Real world setting
    
    # Run the command with only a few samples, verifying it skips save
    call_command('train_noshow_model')
    
    # Confirm it was not saved
    assert not os.path.exists(settings.NOSHOW_MODEL_PATH)
    
    user_p = User.objects.create_user(username='patient2', password='pw')
    patient = PatientProfile.objects.create(user=user_p)
    
    user_d = User.objects.create_user(username='doctor2', password='pw')
    doctor = DoctorProfile.objects.create(user=user_d)
    
    appt = Appointment.objects.create(
        patient=patient, doctor=doctor,
        date=(timezone.now() + timedelta(days=5)).date(),
        time=datetime.time(10, 0),
        status='Confirmed'
    )
    
    # Patient2 has no past history, and model was not trained
    risk = predict_risk(appt)
    assert risk == 'Insufficient Data'

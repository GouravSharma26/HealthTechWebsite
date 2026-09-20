import os
import django
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'healthtech.settings')
django.setup()

from core.models import User, DoctorProfile, DoctorTimeSlot

def create_fixtures():
    # Clear existing e2e specific data just in case
    User.objects.filter(username='seeded_doctor_username').delete()
    User.objects.filter(username='seeded_patient_username').delete()

    print("Creating seeded doctor...")
    doc_user = User.objects.create_user(
        id=9999,
        username='seeded_doctor_username',
        password='seeded_doctor_password',
        email='e2e_doctor@example.com',
        is_doctor=True,
        phone_number='1234567890'
    )

    doc_profile = DoctorProfile.objects.create(
        id=9999,
        user=doc_user,
        specialization='Cardiology',
        qualifications='MD, PhD',
        experience_years=10,
        consultation_fee=100.00,
        about='A seeded doctor for E2E testing.',
        is_verified=True
    )

    print("Creating open timeslots for today...")
    now = timezone.now()
    DoctorTimeSlot.objects.create(
        id=9999,
        doctor=doc_profile,
        start_time=django.utils.timezone.datetime.strptime('23:00', '%H:%M').time(),
        end_time=django.utils.timezone.datetime.strptime('23:29', '%H:%M').time(),
        capacity=100
    )
    # Create multiple capacity=1 slots for concurrent tests (each browser needs one)
    for i in range(5):
        start = (now + timedelta(minutes=30 + i * 30)).time()
        end = (now + timedelta(minutes=59 + i * 30)).time()
        DoctorTimeSlot.objects.create(
            id=9998 - i,
            doctor=doc_profile,
            start_time=start,
            end_time=end,
            capacity=1
        )

    print("Creating patient and appointment for scan test...")
    from core.models import PatientProfile, Appointment
    pat_user = User.objects.create_user(
        id=9998,
        username='seeded_patient_username',
        password='seeded_patient_password',
        email='e2e_patient@example.com',
        is_patient=True
    )
    pat_profile = PatientProfile.objects.create(id=9998, user=pat_user)
    Appointment.objects.create(
        id=9999,
        doctor=doc_profile,
        patient=pat_profile,
        date=now.date(),
        status='Confirmed'
    )

    print("Dumping data to e2e_fixtures.json...")
    with open('e2e_fixtures.json', 'w') as f:
        call_command('dumpdata', 'core', stdout=f, indent=2)
    
    print("Done!")

if __name__ == '__main__':
    create_fixtures()

import os
import sys
import django
from django.core import serializers
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'healthtech.settings')
django.setup()

from core.models import User, DoctorProfile, DoctorTimeSlot

def create_fixtures():
    # This script deletes/creates users with hard-coded passwords (including a verified
    # doctor). Never let it touch a real database by accident: settings.py switches to
    # DATABASE_URL (e.g. production Postgres) whenever that variable is set.
    if os.environ.get('DATABASE_URL') and os.environ.get('E2E_ALLOW_DATABASE_URL') != '1':
        sys.exit("Refusing to run: DATABASE_URL is set, so this would seed that database. "
                 "Unset it to use local SQLite, or set E2E_ALLOW_DATABASE_URL=1 if you really mean it.")

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

    print("Dumping seeded data to e2e_fixtures.json...")
    # Dump ONLY the objects created above. `dumpdata core` would also export every other
    # row in the local database (leftover test accounts and their password hashes).
    from core.models import PatientProfile, Appointment
    seeded = [
        *User.objects.filter(pk__in=[9998, 9999]).order_by('pk'),
        *DoctorProfile.objects.filter(pk=9999),
        *PatientProfile.objects.filter(pk=9998),
        *DoctorTimeSlot.objects.filter(doctor=doc_profile).order_by('pk'),
        *Appointment.objects.filter(pk=9999),
    ]
    with open('e2e_fixtures.json', 'w') as f:
        serializers.serialize('json', seeded, indent=2, stream=f)
    
    print("Done!")

if __name__ == '__main__':
    create_fixtures()

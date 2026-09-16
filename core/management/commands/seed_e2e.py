import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import DoctorProfile, DoctorTimeSlot
from datetime import datetime, time
import django

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with required fixtures for E2E tests.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding E2E test data...")

        # 1. Create a verified doctor
        username = "seeded_doctor_username"
        password = "seeded_doctor_password"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': 'seeded_doctor@example.com',
                'is_doctor': True,
                'phone_number': '5551234567'
            }
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"Created doctor user: {username}")
        else:
            self.stdout.write(f"Doctor user {username} already exists")

        # 2. Create the DoctorProfile
        profile, p_created = DoctorProfile.objects.get_or_create(
            user=user,
            defaults={
                'specialization': 'General Physician',
                'experience_years': 10,
                'is_verified': True,
                'consultation_fee': 50,
                'about': 'A test doctor for E2E testing.'
            }
        )
        if p_created:
            self.stdout.write(f"Created verified profile for {username}")
        else:
            profile.is_verified = True
            profile.save()

        # Slots for booking tests (Future)
        from datetime import timedelta
        now = datetime.now()
        
        start_time_future1 = now + timedelta(hours=2)
        start_time_future1 = start_time_future1.replace(minute=0, second=0, microsecond=0)
        end_time_future1 = start_time_future1 + timedelta(hours=1)
        
        start_time_future2 = start_time_future1 + timedelta(hours=1)
        end_time_future2 = start_time_future2 + timedelta(hours=1)

        DoctorTimeSlot.objects.get_or_create(
            doctor=profile,
            start_time=start_time_future1,
            defaults={'end_time': end_time_future1, 'capacity': 100}
        )
        DoctorTimeSlot.objects.get_or_create(
            doctor=profile,
            start_time=start_time_future2,
            defaults={'end_time': end_time_future2, 'capacity': 1}
        )

        # Slot for prescription test (Past)
        start_time_past = now - timedelta(days=1)
        start_time_past = start_time_past.replace(minute=0, second=0, microsecond=0)
        end_time_past = start_time_past + timedelta(hours=1)

        slot_past, _ = DoctorTimeSlot.objects.get_or_create(
            doctor=profile,
            start_time=start_time_past,
            defaults={'end_time': end_time_past, 'capacity': 1}
        )

        from core.models import Appointment, PatientProfile
        # Create a patient for the appointment
        patient_user, _ = User.objects.get_or_create(
            username="seeded_patient_for_scan",
            defaults={'email': 'scan_patient@example.com', 'is_doctor': False}
        )
        patient_user.set_password('password123')
        patient_user.save()

        patient_profile, _ = PatientProfile.objects.get_or_create(
            user=patient_user,
            defaults={'contact': '555-1234'}
        )

        Appointment.objects.get_or_create(
            doctor=profile,
            patient=patient_profile,
            date=start_time_past.date(),
            time_slot=slot_past,
            defaults={'status': 'Confirmed'}
        )

        self.stdout.write(self.style.SUCCESS("E2E data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS(f'E2E_DOCTOR_PROFILE_ID={profile.id}'))
        self.stdout.write(self.style.SUCCESS(f'E2E_DOCTOR_USER_ID={user.id}'))

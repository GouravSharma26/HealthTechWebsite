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

        from datetime import timedelta
        now = datetime.now()
        start_time = now + timedelta(hours=2)
        start_time = start_time.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)

        slot, s_created = DoctorTimeSlot.objects.get_or_create(
            doctor=profile,
            start_time=start_time,
            defaults={'end_time': end_time, 'capacity': 1}
        )
        if s_created:
            self.stdout.write(f"Created open time slot for {username} today at {start_time}")
        else:
            slot.capacity = 1
            slot.save()

        self.stdout.write(self.style.SUCCESS("E2E data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS(f'E2E_DOCTOR_PROFILE_ID={profile.id}'))
        self.stdout.write(self.style.SUCCESS(f'E2E_DOCTOR_USER_ID={user.id}'))

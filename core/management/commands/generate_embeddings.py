from django.core.management.base import BaseCommand
from core.models import DoctorProfile
from core.search import update_doctor_embedding
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates search embeddings for all existing DoctorProfiles'

    def handle(self, *args, **kwargs):
        doctors = DoctorProfile.objects.all()
        count = 0
        total = doctors.count()
        self.stdout.write(f"Starting to generate embeddings for {total} doctors...")
        
        for doctor in doctors:
            self.stdout.write(f"Processing Dr. {doctor.user.username}...")
            update_doctor_embedding(doctor)
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully generated embeddings for {count} doctors.'))

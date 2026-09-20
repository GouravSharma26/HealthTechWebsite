import os
import secrets
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'healthtech.settings')
django.setup()

from core.models import User, DoctorProfile

# These accounts are created on whatever database DATABASE_URL points at, and this repo is
# public, so never use a fixed password. Set SAMPLE_DATA_PASSWORD, or one is generated
# and printed once at the end.
SAMPLE_PASSWORD = os.environ.get('SAMPLE_DATA_PASSWORD') or secrets.token_urlsafe(12)

def create_sample_doctors():
    doctors_data = [
        {
            'username': 'dr_rajesh',
            'email': 'rajesh@example.com',
            'password': SAMPLE_PASSWORD,
            'specialization': 'Cardiologist',
            'experience_years': 12,
            'contact': '9876543210',
            'address': 'Heart Care Clinic, Apollo Hospital Rd, Delhi',
            'latitude': 28.6139,
            'longitude': 77.2090
        },
        {
            'username': 'dr_priya',
            'email': 'priya@example.com',
            'password': SAMPLE_PASSWORD,
            'specialization': 'Dermatologist',
            'experience_years': 8,
            'contact': '9876543211',
            'address': 'Skin Glow Center, Bandra West, Mumbai',
            'latitude': 19.0596,
            'longitude': 72.8295
        },
        {
            'username': 'dr_amit',
            'email': 'amit@example.com',
            'password': SAMPLE_PASSWORD,
            'specialization': 'Neurologist',
            'experience_years': 15,
            'contact': '9876543212',
            'address': 'Brain & Spine Institute, Salt Lake, Kolkata',
            'latitude': 22.5726,
            'longitude': 88.3639
        },
        {
            'username': 'dr_sneha',
            'email': 'sneha@example.com',
            'password': SAMPLE_PASSWORD,
            'specialization': 'Pediatrician',
            'experience_years': 5,
            'contact': '9876543213',
            'address': 'Little Angels Clinic, Indiranagar, Bangalore',
            'latitude': 12.9716,
            'longitude': 77.5946
        }
    ]

    for data in doctors_data:
        if not User.objects.filter(username=data['username']).exists():
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )
            user.is_doctor = True
            user.save()
            
            DoctorProfile.objects.create(
                user=user,
                specialization=data['specialization'],
                experience_years=data['experience_years'],
                contact=data['contact'],
                address=data['address'],
                latitude=data['latitude'],
                longitude=data['longitude'],
                is_verified=True,   # the chatbot only recommends verified doctors
            )
            print(f"Created Doctor: {data['username']} ({data['specialization']})")
        else:
            # Re-running also repairs sample doctors that were seeded before they were marked verified
            fixed = DoctorProfile.objects.filter(user__username=data['username'], is_verified=False).update(is_verified=True)
            print(f"Doctor {data['username']} already exists." + (" Marked as verified." if fixed else ""))

if __name__ == '__main__':
    create_sample_doctors()
    if not os.environ.get('SAMPLE_DATA_PASSWORD'):
        print(f"\nGenerated password (only for accounts created in this run): {SAMPLE_PASSWORD}")

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'healthtech.settings')
django.setup()

from core.models import User, DoctorProfile

def create_sample_doctors():
    doctors_data = [
        {
            'username': 'dr_rajesh',
            'email': 'rajesh@example.com',
            'password': 'password123',
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
            'password': 'password123',
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
            'password': 'password123',
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
            'password': 'password123',
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
                longitude=data['longitude']
            )
            print(f"Created Doctor: {data['username']} ({data['specialization']})")
        else:
            print(f"Doctor {data['username']} already exists.")

if __name__ == '__main__':
    create_sample_doctors()

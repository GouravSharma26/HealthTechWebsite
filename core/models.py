from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    is_patient = models.BooleanField(default=False)
    is_doctor = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    verification_otp = models.CharField(max_length=6, null=True, blank=True)

class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    contact = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username}'s Patient Profile"

class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    profile_picture = models.ImageField(upload_to='doctor_pics/', null=True, blank=True)
    about = models.TextField(blank=True, null=True)
    specialization = models.CharField(max_length=100)
    qualifications = models.CharField(max_length=200, blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.PositiveIntegerField(blank=True, null=True)
    languages_spoken = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField()
    contact = models.CharField(max_length=20)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    license_document = models.FileField(upload_to='doctor_docs/', null=True, blank=True)
    degree_document = models.FileField(upload_to='doctor_docs/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username} - {self.specialization}"

class Review(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='reviews')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(default=5) # 1 to 5
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.patient.user.username} for Dr. {self.doctor.user.username}"

class DoctorTimeSlot(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='time_slots')
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.doctor.user.username} - {self.start_time.strftime('%H:%M')} to {self.end_time.strftime('%H:%M')}"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Cancel Requested', 'Cancel Requested'),
        ('Reschedule Requested', 'Reschedule Requested'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    )
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    time_slot = models.ForeignKey(DoctorTimeSlot, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='Pending')
    
    # Request Flow Fields
    patient_reason = models.TextField(blank=True, null=True)
    doctor_reason = models.TextField(blank=True, null=True)
    reschedule_date = models.DateField(blank=True, null=True)
    reschedule_time = models.TimeField(blank=True, null=True)
    auto_approved = models.BooleanField(default=False)
    warning_sent = models.BooleanField(default=False)
    
    # Prescription & Follow-up Fields
    prescription_medicines = models.TextField(blank=True, null=True)
    prescription_instructions = models.TextField(blank=True, null=True)
    prescription_document = models.FileField(upload_to='prescriptions/', null=True, blank=True)
    follow_up_date = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Appointment: {self.patient.user.username} with Dr. {self.doctor.user.username} on {self.date}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:20]}"

class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.timestamp}"

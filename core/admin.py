from django.contrib import admin
from .models import User, DoctorProfile, PatientProfile, Appointment, Review, Notification

# Register your models here.
admin.site.register(User)
admin.site.register(DoctorProfile)
admin.site.register(PatientProfile)
admin.site.register(Appointment)
admin.site.register(Review)
admin.site.register(Notification)

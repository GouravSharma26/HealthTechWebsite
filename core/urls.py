from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('verify/', views.verify_account, name='verify_account'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('account/delete/', views.delete_account, name='delete_account'),
    
    # Profiles
    path('doctor/setup/', views.doctor_setup, name='doctor_setup'),
    path('patient/setup/', views.patient_setup, name='patient_setup'),
    path('doctor/profile/', views.doctor_profile, name='doctor_profile'),
    path('patient/profile/', views.patient_profile, name='patient_profile'),
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    
    # Directory
    path('doctors/', views.doctors, name='doctors'),
    path('doctor/<int:id>/', views.doctor_detail, name='doctor_detail'),
    path('api/doctor/<int:id>/slots/', views.api_doctor_slots, name='api_doctor_slots'),
    path('doctor/slots/manage/', views.manage_time_slots, name='manage_time_slots'),
    path('doctor/slots/update-capacity/', views.update_slot_capacity, name='update_slot_capacity'),
    
    # Chat
    path('chat/', views.chat_list, name='chat_list'),
    path('chat/<int:user_id>/', views.chat_detail, name='chat_detail'),
    
    # Static pages
    path('about/', views.about_view, name='about'),
    path('help/', views.help_view, name='help'),
    path('contact/', views.contact_view, name='contact'),
]

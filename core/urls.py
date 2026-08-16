from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('doctor/setup/', views.doctor_setup, name='doctor_setup'),
]

from django.shortcuts import render

def home(request):
    return render(request, 'core/index.html')

def doctor_setup(request):
    return render(request, 'core/doctor_setup.html')

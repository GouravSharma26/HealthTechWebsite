import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import User, DoctorProfile, PatientProfile, Appointment, Review, Notification, DoctorTimeSlot, ChatMessage
import datetime
from django.conf import settings

def home(request):
    return render(request, 'core/index.html')

def signup_view(request):
    if request.method == 'POST':
        role = request.POST.get('role')
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('signup')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use")
            return redirect('signup')

        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Phone number already in use")
            return redirect('signup')
            
        user = User.objects.create_user(username=username, email=email, password=password)
        user.phone_number = phone_number
        if role == 'doctor':
            user.is_doctor = True
        else:
            user.is_patient = True
        user.save()

        # Log them in
        login(request, user)
        
        if user.is_doctor:
            return redirect('doctor_setup')
        else:
            return redirect('patient_setup')
        
    return render(request, 'core/signup.html')



def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_doctor:
                # If they haven't setup profile, go to setup
                if not hasattr(user, 'doctor_profile'):
                    return redirect('doctor_setup')
                return redirect('doctor_profile')
            else:
                if not hasattr(user, 'patient_profile'):
                    return redirect('patient_setup')
                return redirect('patient_profile')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def delete_account(request):
    if request.method == 'POST':
        user_id = request.user.id
        logout(request)
        User.objects.filter(id=user_id).delete()
        messages.success(request, "Your account has been successfully deleted.")
        return redirect('home')
    return redirect('home')

@login_required
def doctor_setup(request):
    if not request.user.is_doctor:
        return redirect('home')
        
    if request.method == 'POST':
        specialization = request.POST.get('specialization')
        qualifications = request.POST.get('qualifications')
        consultation_fee = request.POST.get('consultation_fee')
        languages_spoken = request.POST.get('languages_spoken')
        experience_years = request.POST.get('experience_years')
        contact = request.POST.get('contact') or request.user.phone_number
        about = request.POST.get('about')
        profile_picture = request.FILES.get('profile_picture')
        
        license_document = request.FILES.get('license_document')
        degree_document = request.FILES.get('degree_document')
        
        address = request.POST.get('address')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        # Profile creation/update
        profile, created = DoctorProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'specialization': specialization,
                'qualifications': qualifications,
                'consultation_fee': consultation_fee if consultation_fee else None,
                'languages_spoken': languages_spoken,
                'experience_years': experience_years,
                'contact': contact,
                'about': about,
                'address': address,
                'latitude': float(latitude) if latitude else None,
                'longitude': float(longitude) if longitude else None,
            }
        )
        if profile_picture:
            profile.profile_picture = profile_picture
        if license_document:
            profile.license_document = license_document
        if degree_document:
            profile.degree_document = degree_document
            
        profile.save()
            
        # Handle initial time slots selection
        selected_slots = request.POST.get('selected_slots')
        capacity = request.POST.get('capacity', 3)
        if selected_slots:
            from datetime import datetime
            slot_list = selected_slots.split(',')
            # Clear existing slots if any (in case of re-setup)
            DoctorTimeSlot.objects.filter(doctor=profile).delete()
            for s in slot_list:
                start_str, end_str = s.split('-')
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()
                DoctorTimeSlot.objects.create(
                    doctor=profile,
                    start_time=start_time,
                    end_time=end_time,
                    capacity=int(capacity)
                )

        messages.success(request, "Profile updated successfully!")
        return redirect('doctor_profile')
        
    return render(request, 'core/doctor_setup.html')

@login_required
def patient_setup(request):
    if not request.user.is_patient:
        return redirect('home')
        
    if request.method == 'POST':
        contact = request.POST.get('contact') or request.user.phone_number
        
        PatientProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'contact': contact,
            }
        )
        messages.success(request, "Profile updated successfully!")
        return redirect('patient_profile')
        
    return render(request, 'core/patient_setup.html')

@login_required
def doctor_profile(request):
    profile = get_object_or_404(DoctorProfile, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        appt_id = request.POST.get('appointment_id')
        appt = get_object_or_404(Appointment, id=appt_id, doctor=profile)
        
        if action == 'approve':
            if appt.status == 'Cancel Requested':
                appt.status = 'Cancelled'
            elif appt.status == 'Reschedule Requested':
                appt.status = 'Confirmed'
                appt.date = appt.reschedule_date
                appt.time = appt.reschedule_time
            appt.save()
            messages.success(request, "Request approved successfully.")
            
        elif action == 'reject':
            # Doctor rejects the request and cancels the appointment entirely
            appt.status = 'Cancelled'
            appt.doctor_reason = request.POST.get('reason')
            appt.save()
            messages.success(request, "Request rejected and appointment cancelled.")
            
        elif action == 'confirm_appointment':
            appt.status = 'Confirmed'
            appt.save()
            Notification.objects.create(
                user=appt.patient.user,
                message=f"Dr. {profile.user.get_full_name() or profile.user.username} has confirmed your appointment on {appt.date}."
            )
            messages.success(request, "Appointment confirmed.")
            
        elif action == 'cancel_appointment':
            appt.status = 'Cancelled'
            appt.doctor_reason = request.POST.get('reason')
            appt.save()
            Notification.objects.create(
                user=appt.patient.user,
                message=f"Dr. {profile.user.get_full_name() or profile.user.username} has cancelled your appointment on {appt.date}. Reason: {appt.doctor_reason}"
            )
            messages.success(request, "Appointment cancelled.")
            
        elif action == 'complete_with_prescription':
            appt.status = 'Completed'
            appt.prescription_medicines = request.POST.get('medicines')
            appt.prescription_instructions = request.POST.get('instructions')
            appt.follow_up_date = request.POST.get('follow_up_date') or None
            
            if 'prescription_document' in request.FILES:
                appt.prescription_document = request.FILES['prescription_document']
                
            appt.save()
            
            Notification.objects.create(
                user=appt.patient.user,
                message=f"Dr. {profile.user.get_full_name() or profile.user.username} has completed your appointment and provided a prescription."
            )
            messages.success(request, "Appointment marked as completed with prescription.")
            
        return redirect('doctor_profile')

    appointments = profile.appointments.all().order_by('date', 'time')
    slots = profile.time_slots.all().order_by('start_time')
    return render(request, 'core/doctorProfile.html', {'profile': profile, 'appointments': appointments, 'slots': slots})

@login_required
def manage_time_slots(request):
    if not hasattr(request.user, 'doctor_profile'):
        return redirect('home')
    profile = request.user.doctor_profile
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_slots':
            selected = request.POST.get('selected_slots', '')
            # Optional: clear existing slots before adding new ones, or just add new ones.
            # The prompt implies we replace or add to them. We will just delete all and recreate for simplicity since capacity defaults to 1 or we can just keep existing and add new.
            # Let's keep existing and just add new, but then how to remove unchecked?
            # It's safer to just clear and recreate, or diff them.
            # Let's diff them to preserve capacities:
            existing_slots = profile.time_slots.all()
            existing_map = {f"{s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')}": s for s in existing_slots}
            
            selected_list = [s for s in selected.split(',') if s]
            
            # Delete those not in selected
            for key, slot in existing_map.items():
                if key not in selected_list:
                    slot.delete()
                    
            # Add new ones
            for s in selected_list:
                if s not in existing_map:
                    start, end = s.split('-')
                    DoctorTimeSlot.objects.create(
                        doctor=profile,
                        start_time=start,
                        end_time=end,
                        capacity=1
                    )
            messages.success(request, "Time slots saved successfully.")
            
        elif action == 'delete_slot':
            slot_id = request.POST.get('slot_id')
            DoctorTimeSlot.objects.filter(id=slot_id, doctor=profile).delete()
            messages.success(request, "Time slot deleted.")
    return redirect('doctor_profile')

@login_required
def update_slot_capacity(request):
    if not hasattr(request.user, 'doctor_profile'):
        return redirect('home')
    profile = request.user.doctor_profile
    if request.method == 'POST':
        apply_to_all = request.POST.get('apply_to_all') == 'on'
        if apply_to_all:
            master_cap = request.POST.get('master_capacity', 1)
            DoctorTimeSlot.objects.filter(doctor=profile).update(capacity=master_cap)
            messages.success(request, "All slots updated with new capacity.")
        else:
            slots = profile.time_slots.all()
            for slot in slots:
                cap = request.POST.get(f'capacity_{slot.id}')
                if cap:
                    slot.capacity = cap
                    slot.save()
            messages.success(request, "Slot capacities updated.")
    return redirect('doctor_profile')

def api_doctor_slots(request, id):
    doctor = get_object_or_404(DoctorProfile, id=id)
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'Date is required'}, status=400)
    
    slots = doctor.time_slots.all().order_by('start_time')
    slots_data = []
    
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
        
    today = timezone.localtime(timezone.now()).date()
    current_time = timezone.localtime(timezone.now()).time()
    
    for slot in slots:
        # Count non-cancelled appointments for this slot on this date
        booked_count = Appointment.objects.filter(
            time_slot=slot, 
            date=date_str
        ).exclude(status__in=['Cancelled', 'Cancel Requested']).count()
        
        is_full = booked_count >= slot.capacity
        
        is_passed = False
        if date_obj == today and slot.start_time <= current_time:
            is_passed = True
        elif date_obj < today:
            is_passed = True
        
        slots_data.append({
            'id': slot.id,
            'start_time': slot.start_time.strftime('%I:%M %p'),
            'start_time_raw': slot.start_time.strftime('%H:%M:%S'),
            'end_time': slot.end_time.strftime('%I:%M %p'),
            'capacity': slot.capacity,
            'booked': booked_count,
            'is_full': is_full,
            'is_passed': is_passed
        })
        
    return JsonResponse({'slots': slots_data})

@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def patient_profile(request):
    profile = get_object_or_404(PatientProfile, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        appt_id = request.POST.get('appointment_id')
        appt = get_object_or_404(Appointment, id=appt_id, patient=profile)
        
        if action == 'cancel_request':
            appt.status = 'Cancel Requested'
            appt.patient_reason = request.POST.get('reason')
            appt.save()
            Notification.objects.create(
                user=appt.doctor.user,
                message=f"Patient {profile.user.username} requested to cancel appointment on {appt.date}."
            )
            messages.success(request, "Cancellation request submitted to the doctor.")
        
        elif action == 'reschedule_request':
            appt.status = 'Reschedule Requested'
            appt.patient_reason = request.POST.get('reason')
            appt.reschedule_date = request.POST.get('reschedule_date')
            appt.reschedule_time = request.POST.get('reschedule_time')
            appt.save()
            Notification.objects.create(
                user=appt.doctor.user,
                message=f"Patient {profile.user.username} requested to reschedule to {appt.reschedule_date}."
            )
            messages.success(request, "Reschedule request submitted to the doctor.")
            
        return redirect('patient_profile')

    appointments = profile.appointments.all().order_by('date', 'time')
    return render(request, 'core/patientProfile.html', {'profile': profile, 'appointments': appointments})

def doctors(request):
    query = request.GET.get('q', '')
    if query:
        doctors_list = DoctorProfile.objects.filter(
            user__username__icontains=query
        ) | DoctorProfile.objects.filter(
            specialization__icontains=query
        )
    else:
        doctors_list = DoctorProfile.objects.all()
        
    return render(request, 'core/doctors.html', {'doctors': doctors_list, 'query': query})

def doctor_detail(request, id):
    doctor = get_object_or_404(DoctorProfile, id=id)
    reviews = doctor.reviews.all().order_by('-created_at')
    
    has_active_appointment = False
    if request.user.is_authenticated and getattr(request.user, 'is_patient', False):
        patient = request.user.patient_profile
        has_active_appointment = Appointment.objects.filter(
            doctor=doctor,
            patient=patient,
            status__in=['Pending', 'Confirmed', 'Reschedule Requested']
        ).exists()
    
    if request.method == 'POST' and request.user.is_authenticated and getattr(request.user, 'is_patient', False):
        # Check if booking appointment or review
        action = request.POST.get('action')
        patient = request.user.patient_profile
        
        if action == 'book':
            if has_active_appointment:
                messages.error(request, "You already have an active appointment with this doctor. Please wait for it to be completed or cancelled before booking another.")
                return redirect('doctor_detail', id=id)
                
            date = request.POST.get('date')
            time_slot_id = request.POST.get('time_slot_id')
            
            if not time_slot_id:
                messages.error(request, "Please select a time slot.")
                return redirect('doctor_detail', id=id)
                
            slot = get_object_or_404(DoctorTimeSlot, id=time_slot_id, doctor=doctor)
            
            # Check capacity again
            booked_count = Appointment.objects.filter(
                time_slot=slot, 
                date=date
            ).exclude(status__in=['Cancelled', 'Cancel Requested']).count()
            
            if booked_count >= slot.capacity:
                messages.error(request, "This time slot is already full. Please select another.")
                return redirect('doctor_detail', id=id)
                
            Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                date=date,
                time=slot.start_time,
                time_slot=slot,
                status='Pending'
            )
            messages.success(request, "Appointment booked successfully!")
            return redirect('patient_profile')
            
        elif action == 'review':
            rating = request.POST.get('rating')
            text = request.POST.get('text')
            
            # Security Check: Verify patient has completed an appointment
            if not Appointment.objects.filter(doctor=doctor, patient=patient, status='Completed').exists():
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("You must have a completed appointment with this doctor to leave a review.")
                
            Review.objects.create(
                doctor=doctor,
                patient=patient,
                rating=rating,
                text=text
            )
            messages.success(request, "Review submitted successfully!")
            return redirect('doctor_detail', id=id)
            
    can_review = False
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        can_review = Appointment.objects.filter(doctor=doctor, patient=request.user.patient_profile, status='Completed').exists()
            
    return render(request, 'core/doctorDetails.html', {'doctor': doctor, 'reviews': reviews, 'can_review': can_review})

def about_view(request):
    return render(request, 'core/about.html')

def help_view(request):
    return render(request, 'core/help.html')

def contact_view(request):
    return render(request, 'core/contact.html')

@login_required
def chat_list(request):
    # For a patient, list doctors they have messaged or have appointments with
    # For a doctor, list patients they have messaged or have appointments with
    users = set()
    
    # Get all users we've exchanged messages with
    messages_sent = ChatMessage.objects.filter(sender=request.user).select_related('receiver')
    messages_received = ChatMessage.objects.filter(receiver=request.user).select_related('sender')
    
    for msg in messages_sent:
        users.add(msg.receiver)
    for msg in messages_received:
        users.add(msg.sender)
        
    # Also add users from past appointments
    if hasattr(request.user, 'patient_profile'):
        appts = Appointment.objects.filter(patient=request.user.patient_profile).select_related('doctor__user')
        for appt in appts:
            users.add(appt.doctor.user)
    elif hasattr(request.user, 'doctor_profile'):
        appts = Appointment.objects.filter(doctor=request.user.doctor_profile).select_related('patient__user')
        for appt in appts:
            users.add(appt.patient.user)
            
    users = list(users)
    return render(request, 'core/chat_list.html', {'users': users})

@login_required
def chat_detail(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_message':
            # Security check: restrict messaging between same roles
            if request.user.is_patient and not getattr(other_user, 'is_doctor', False):
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Patients can only message doctors.")
            if request.user.is_doctor and not getattr(other_user, 'is_patient', False):
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Doctors can only message patients.")
                
            message_text = request.POST.get('message')
            if message_text:
                ChatMessage.objects.create(
                    sender=request.user,
                    receiver=other_user,
                    message=message_text
                )
            return redirect('chat_detail', user_id=other_user.id)
            
    # Mark messages as read
    ChatMessage.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    
    # Get chat history
    messages_history = ChatMessage.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).order_by('timestamp')
    
    # Get shared appointment history
    shared_appointments = []
    if hasattr(request.user, 'patient_profile') and hasattr(other_user, 'doctor_profile'):
        shared_appointments = Appointment.objects.filter(patient=request.user.patient_profile, doctor=other_user.doctor_profile).order_by('-date', '-time')
    elif hasattr(request.user, 'doctor_profile') and hasattr(other_user, 'patient_profile'):
        shared_appointments = Appointment.objects.filter(doctor=request.user.doctor_profile, patient=other_user.patient_profile).order_by('-date', '-time')
        
    # Determine context for booking widget
    doctor_obj = None
    if hasattr(other_user, 'doctor_profile'):
        doctor_obj = other_user.doctor_profile
    elif hasattr(request.user, 'doctor_profile'):
        doctor_obj = request.user.doctor_profile
        
    slots = []
    if doctor_obj:
        slots = doctor_obj.time_slots.all().order_by('start_time')
        
    has_active_appointment = False
    if hasattr(request.user, 'patient_profile') and doctor_obj:
        has_active_appointment = Appointment.objects.filter(
            doctor=doctor_obj,
            patient=request.user.patient_profile,
            status__in=['Pending', 'Confirmed', 'Reschedule Requested']
        ).exists()
        
    return render(request, 'core/chat_detail.html', {
        'other_user': other_user,
        'messages_history': messages_history,
        'shared_appointments': shared_appointments,
        'doctor_obj': doctor_obj,
        'slots': slots,
        'has_active_appointment': has_active_appointment
    })

import json
from django.http import JsonResponse
from groq import Groq

def ai_chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            history = data.get('history', [])
            
            if not settings.GROQ_API_KEY:
                return JsonResponse({'error': 'GROQ_API_KEY is not configured in environment variables.'}, status=500)
                
            client = Groq(api_key=settings.GROQ_API_KEY)
            
            system_prompt = """You are HealthBot, an AI triage assistant for the HealthTech platform.
Your job is to listen to the user's symptoms and recommend the best type of doctor specialization they should see on our platform.
Do NOT provide definitive medical diagnoses. Emphasize that you are an AI and they must consult a real doctor.
At the end of your advice, suggest they search our directory for a specific specialist (e.g. **Cardiologist**, **Dermatologist**, **General Physician**).
Keep your responses concise, friendly, and formatted nicely."""

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history:
                if msg.get('role') in ['user', 'assistant']:
                    messages.append({"role": msg['role'], "content": msg['content']})
            
            if not messages or messages[-1]['content'] != user_message:
                messages.append({"role": "user", "content": user_message})

            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama3-8b-8192",
            )
            
            reply = chat_completion.choices[0].message.content
            return JsonResponse({'reply': reply})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'core/ai_chat.html')

import requests

def scan_prescription(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
        
    if not request.user.is_authenticated or not request.user.is_doctor:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        data = json.loads(request.body)
        image_base64 = data.get('image', '')
        
        if not image_base64:
            return JsonResponse({'error': 'No image provided'}, status=400)
            
        if not getattr(settings, 'OPENROUTER_API_KEY', None):
            return JsonResponse({'error': 'OPENROUTER_API_KEY is not configured.'}, status=500)
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemini-flash-1.5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the handwritten prescription from this image. Return ONLY a valid JSON object with exactly two keys: 'medicines' (a comma-separated string of the medicines with their dosages) and 'instructions' (a string of the usage instructions). Do not include any markdown formatting, backticks, or other text."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        }
                    ]
                }
            ]
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        
        if not response.ok:
            return JsonResponse({'error': f"Vision API Error: {response.text}"}, status=response.status_code)
            
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Attempt to clean potential markdown formatting
        content = content.replace('```json', '').replace('```', '').strip()
        
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = {
                "medicines": content,
                "instructions": "Could not separate instructions. Review extracted text."
            }
            
        return JsonResponse(parsed_content)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


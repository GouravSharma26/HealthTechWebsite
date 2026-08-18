from django.core.management.base import BaseCommand
from core.models import Appointment
from django.utils import timezone
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Auto-approves pending patient requests if within 3 hours of the appointment'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        auto_approve_threshold = now + timedelta(hours=3)
        warning_threshold = now + timedelta(hours=4)
        
        pending_requests = Appointment.objects.filter(status__in=['Cancel Requested', 'Reschedule Requested'])
        
        count_approved = 0
        count_warned = 0
        
        for appt in pending_requests:
            appt_datetime = timezone.make_aware(datetime.combine(appt.date, appt.time))
            
            # If within 3 hours, auto-approve
            if appt_datetime <= auto_approve_threshold:
                if appt.status == 'Cancel Requested':
                    appt.status = 'Cancelled'
                elif appt.status == 'Reschedule Requested':
                    appt.status = 'Confirmed'
                    appt.date = appt.reschedule_date
                    appt.time = appt.reschedule_time
                
                appt.auto_approved = True
                appt.save()
                count_approved += 1
                self.stdout.write(self.style.SUCCESS(f'Auto-approved appt {appt.id}'))
                
            # If within 4 hours, and warning not sent, send warning
            elif appt_datetime <= warning_threshold and not appt.warning_sent:
                from core.models import Notification
                Notification.objects.create(
                    user=appt.doctor.user,
                    message=f"WARNING: A patient request for appt on {appt.date} will be auto-approved in less than 1 hour!"
                )
                appt.warning_sent = True
                appt.save()
                count_warned += 1
                self.stdout.write(self.style.WARNING(f'Sent 1hr warning for appt {appt.id}'))
                    
        self.stdout.write(f'Auto-approved {count_approved}, Warned {count_warned}')

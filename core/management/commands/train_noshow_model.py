import os
import joblib
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Appointment
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

class Command(BaseCommand):
    help = 'Trains the No-Show Risk Predictive Model'

    def handle(self, *args, **options):
        self.stdout.write('Querying historical appointments...')
        # We only train on finished appointments
        finished_appts = Appointment.objects.filter(status__in=['Completed', 'Cancelled']).order_by('created_at')
        
        if not finished_appts.exists():
            self.stdout.write(self.style.WARNING('No finished appointments available for training. Model will not be trained.'))
            return

        X = []
        y = []
        
        # Precompute patient cancellation stats up to each appointment
        patient_history = {}

        for appt in finished_appts:
            pid = appt.patient_id
            
            # calculate past cancellation rate at the time this appointment was created
            history = patient_history.get(pid, [])
            total_past = len(history)
            canceled_past = sum(1 for h in history if h[1])
            past_cancel_rate = canceled_past / total_past if total_past > 0 else 0.0
            
            # lead time in days
            lead_time = (appt.date - appt.created_at.date()).days
            if lead_time < 0:
                lead_time = 0
            
            day_of_week = appt.date.weekday()
            
            # time of day (hour)
            time_of_day = appt.time.hour if appt.time else 12
            
            is_cancelled = 1 if appt.status == 'Cancelled' else 0
            
            X.append([lead_time, past_cancel_rate, day_of_week, time_of_day])
            y.append(is_cancelled)
            
            # update history
            if pid not in patient_history:
                patient_history[pid] = []
            patient_history[pid].append((appt.created_at, is_cancelled == 1))
            
        # Handle sparse data scenario
        unique_classes = set(y)
        if len(unique_classes) < 2:
            self.stdout.write(self.style.WARNING('Not enough variance in target (need both Completed and Cancelled). Using dummy data to bootstrap.'))
            # Bootstrap with dummy data to ensure the pipeline can be trained and saved
            X.extend([[0, 0.0, 0, 12], [14, 1.0, 5, 15]])
            if 0 not in unique_classes: y.append(0)
            if 1 not in unique_classes: y.append(1)
            
        self.stdout.write('Training model...')
        # Train a Logistic Regression model
        model = make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced'))
        model.fit(X, y)
        
        # Ensure directory exists
        model_dir = os.path.join(settings.BASE_DIR, 'core', 'ml_models')
        os.makedirs(model_dir, exist_ok=True)
        
        # Make __init__.py if it doesn't exist to make it a package (optional but good practice)
        init_file = os.path.join(model_dir, '__init__.py')
        if not os.path.exists(init_file):
            open(init_file, 'a').close()
        
        model_path = os.path.join(model_dir, 'noshow_model.joblib')
        joblib.dump(model, model_path)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully trained and saved model to {model_path}'))

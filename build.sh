#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# ONE-TIME: Delete all accounts (REMOVE THIS AFTER DEPLOY)
python manage.py shell -c "from core.models import User; count = User.objects.count(); User.objects.all().delete(); print(f'Deleted {count} accounts')"

import datetime
import glob
import re
from pathlib import Path

import pytest
from django.urls import reverse

from core.models import Appointment, DoctorProfile, PatientProfile, User

# Root cause (confirmed by reading Django's own tokenizer in this installed version):
#   tag_re = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})")
# has no re.DOTALL flag, so `.` cannot match a newline. A {{ ... }} tag with a line break
# inside it (e.g. from an editor auto-wrapping a long line) therefore never matches this
# regex as a tag at all - Django silently treats it as literal HTML text instead of raising
# any error, and the raw "{{ some.expression }}" source appears on the live page verbatim.
# This is a real, reproduced bug (not a stale-deployment artifact): a patient viewing their
# own appointments saw the doctor's name, status, and prescription text all render as literal
# unprocessed template source instead of the actual values.

TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / 'core' / 'templates'
_BROKEN_TAG_RE = re.compile(r'\{\{[^{}]*\n[^{}]*\}\}')


def _find_newline_broken_tags():
    """Every {{ ... }} tag across all templates that has a literal newline inside it - each one
    is a tag Django's tokenizer will silently fail to recognize, printing raw source instead."""
    found = []
    for path in sorted(glob.glob(str(TEMPLATES_ROOT / '**' / '*.html'), recursive=True)):
        content = Path(path).read_text(encoding='utf-8')
        for m in _BROKEN_TAG_RE.finditer(content):
            line_no = content.count('\n', 0, m.start()) + 1
            found.append((path, line_no, ' '.join(m.group(0).split())))
    return found


def test_no_template_variable_tag_has_a_newline_inside_it():
    """Project-wide guard: fails with the exact file/line/tag if this bug class reappears
    anywhere (this file, or a future one), instead of only being caught by someone noticing
    broken text on a live page."""
    broken = _find_newline_broken_tags()
    assert broken == [], (
        "Found {{ ... }} tag(s) with a newline inside them - Django's tag_re has no re.DOTALL, "
        "so these silently render as literal text instead of being processed:\n" +
        "\n".join(f"  {path}:{line}: {tag}" for path, line, tag in broken)
    )


@pytest.mark.django_db
def test_patient_profile_appointment_card_renders_doctor_name_status_and_prescription(client):
    """Reproduces the exact reported bug: doctor name, status, and prescription text must render
    as real values, not literal Django template source, on the patient's own appointments page."""
    doc_user = User.objects.create_user('reprodoc', password='pw', is_doctor=True, first_name='Rajesh')
    doc = DoctorProfile.objects.create(user=doc_user, specialization='Cardiologist',
                                        experience_years=10, is_verified=True)
    pat_user = User.objects.create_user('reprupat', password='pw', is_patient=True)
    pat = PatientProfile.objects.create(user=pat_user)
    Appointment.objects.create(patient=pat, doctor=doc, date=datetime.date(2026, 9, 28),
                                time=datetime.time(11, 0), status='Confirmed')
    Appointment.objects.create(patient=pat, doctor=doc, date=datetime.date(2026, 9, 20),
                                time=datetime.time(9, 0), status='Completed',
                                prescription_medicines='Tablet Augmentin 625mg',
                                prescription_instructions='Take twice daily after meals')

    client.login(username='reprupat', password='pw')
    html = client.get(reverse('patient_profile')).content.decode()

    assert 'Dr. Rajesh' in html
    assert 'Confirmed' in html
    assert 'Completed' in html
    assert 'Tablet Augmentin 625mg' in html
    assert 'Take twice daily after meals' in html
    # The specific literal source strings from the bug report must never appear again.
    for literal in ('appt.doctor.user.get_full_name|default', 'appt.prescription_medicines }}',
                    'appt.prescription_instructions }}'):
        assert literal not in html

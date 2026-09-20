import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from core.models import User, DoctorProfile
from core.views import is_valid_file

MB = 1024 * 1024


def pdf(size):
    """A file whose first bytes are a real PDF header, padded to `size` bytes."""
    head = b'%PDF-1.4\n'
    return SimpleUploadedFile('doc.pdf', head + b'0' * (size - len(head)), content_type='application/pdf')


def test_small_valid_pdf_is_accepted():
    assert is_valid_file(pdf(1024)) is True


def test_pdf_exactly_at_limit_is_accepted():
    assert is_valid_file(pdf(5 * MB)) is True


def test_pdf_one_byte_over_limit_is_rejected():
    assert is_valid_file(pdf(5 * MB + 1)) is False


def test_oversize_check_does_not_consume_the_file():
    f = pdf(1024)
    assert is_valid_file(f) is True
    assert f.read(4) == b'%PDF'   # pointer rewound so Django can still save it


@pytest.mark.django_db
def test_doctors_list_query_count_does_not_grow_with_doctors(client):
    def make(n):
        for i in range(n):
            u = User.objects.create_user(username=f'dq{n}_{i}', is_doctor=True)
            DoctorProfile.objects.create(user=u, specialization='Cardiology')

    make(2)
    with CaptureQueriesContext(connection) as few:
        assert client.get(reverse('doctors')).status_code == 200
    make(10)
    with CaptureQueriesContext(connection) as many:
        assert client.get(reverse('doctors')).status_code == 200

    assert len(many) == len(few), f'N+1: {len(few)} queries for 2 doctors vs {len(many)} for 12'

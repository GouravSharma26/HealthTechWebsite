"""Map tiles: CARTO began requiring an API key for basemaps.cartocdn.com raster tiles on 2026-09-23
(unauthenticated requests still return HTTP 200 but every tile is watermarked "API KEY REQUIRED").
Both map pages now use OpenStreetMap's own tile server, which needs no key."""
from pathlib import Path

import pytest
from django.urls import reverse

from core.models import DoctorProfile, User

OLD_HOST = 'cartocdn'          # the keyed CARTO tile host; this file lives under tests/, outside the scanned dirs
NEW_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
CORE = Path(__file__).resolve().parents[1]


def test_no_template_or_static_file_references_the_keyed_carto_tiles():
    offenders = []
    for base in (CORE / 'templates', CORE / 'static'):
        for path in base.rglob('*'):
            if path.suffix in {'.html', '.js', '.css'} and OLD_HOST in path.read_text(encoding='utf-8', errors='ignore'):
                offenders.append(str(path.relative_to(CORE)))
    assert offenders == []


@pytest.mark.parametrize('template', ['doctorDetails.html', 'doctor_setup.html'])
def test_map_templates_use_openstreetmap_tiles_with_attribution(template):
    html = (CORE / 'templates' / 'core' / template).read_text(encoding='utf-8')
    assert NEW_TILE_URL in html
    assert 'openstreetmap.org/copyright' in html     # OSM's tile policy requires visible attribution


@pytest.mark.django_db
def test_doctor_detail_page_serves_the_osm_tile_layer(client):
    user = User.objects.create_user('drmap', password='pw', is_doctor=True)
    profile = DoctorProfile.objects.create(user=user, specialization='Cardiologist', is_verified=True,
                                           latitude=19.076, longitude=72.8777)
    html = client.get(reverse('doctor_detail', args=[profile.id])).content.decode()
    assert NEW_TILE_URL in html and OLD_HOST not in html


@pytest.mark.django_db
def test_doctor_setup_page_serves_the_osm_tile_layer(client):
    user = User.objects.create_user('drsetup', password='pw', is_doctor=True)
    client.force_login(user)
    html = client.get(reverse('doctor_setup')).content.decode()
    assert NEW_TILE_URL in html and OLD_HOST not in html

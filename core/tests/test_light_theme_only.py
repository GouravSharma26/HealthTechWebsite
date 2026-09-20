from pathlib import Path

import pytest
from django.urls import reverse

CSS = Path(__file__).resolve().parents[1] / 'static' / 'core' / 'css' / 'style.css'
JS = Path(__file__).resolve().parents[1] / 'static' / 'core' / 'js' / 'script.js'


@pytest.mark.django_db
def test_home_page_has_no_theme_toggle_or_dark_mode_script(client):
    html = client.get(reverse('home')).content.decode()
    for needle in ('theme-toggle', 'toggleTheme', 'data-theme', 'prefers-color-scheme',
                   "localStorage.getItem('theme')", 'core/js/script.js'):
        assert needle not in html, needle


@pytest.mark.django_db
def test_page_declares_light_color_scheme_so_native_controls_stay_light(client):
    assert '<meta name="color-scheme" content="light">' in client.get(reverse('home')).content.decode()


def test_stylesheet_has_no_dark_rules_and_is_balanced():
    css = CSS.read_text(encoding='utf-8')
    assert 'data-theme' not in css and '.theme-toggle' not in css
    assert css.count('{') == css.count('}')
    assert ':root' in css                                   # light variables are still defined


def test_dead_toggle_script_is_gone():
    assert not JS.exists()

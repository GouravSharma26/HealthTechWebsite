from pathlib import Path

REQ = Path(__file__).resolve().parents[2] / 'requirements.txt'


def test_requirements_is_plain_utf8_without_bom():
    # `pip freeze > requirements.txt` in Windows PowerShell writes UTF-16, and some
    # editors add a BOM; keep this file plain ASCII/UTF-8.
    raw = REQ.read_bytes()
    assert not raw.startswith((b'\xef\xbb\xbf', b'\xff\xfe', b'\xfe\xff'))
    assert b'\x00' not in raw
    raw.decode('utf-8')


def test_requirements_has_no_windows_only_packages():
    # Render builds on Linux: these make `pip install -r requirements.txt` fail.
    names = {
        line.split('==')[0].strip().lower()
        for line in REQ.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    }
    assert not names & {'pywin32', 'pypiwin32', 'pywinpty', 'comtypes'}

import pytest
import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.core.cache import cache
from core.models import User, PatientProfile, DoctorProfile

@pytest.fixture
def users_data(db):
    patient1 = User.objects.create_user(username='patient1', password='pw', is_patient=True)
    patient2 = User.objects.create_user(username='patient2', password='pw', is_patient=True)
    doctor1 = User.objects.create_user(username='doctor1', password='pw', is_doctor=True)
    doctor2 = User.objects.create_user(username='doctor2', password='pw', is_doctor=True)
    
    PatientProfile.objects.create(user=patient1)
    PatientProfile.objects.create(user=patient2)
    DoctorProfile.objects.create(user=doctor1, specialization='Cardiology')
    DoctorProfile.objects.create(user=doctor2, specialization='Neurology')
    
    return patient1, patient2, doctor1, doctor2

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield

@pytest.mark.django_db
def test_chat_detail_patient_to_patient_forbidden(client, users_data):
    patient1, patient2, doctor1, doctor2 = users_data
    client.login(username='patient1', password='pw')
    
    url = reverse('chat_detail', args=[patient2.id])
    response = client.post(url, {'action': 'send_message', 'message': 'Hello'})
    
    assert response.status_code == 403
    assert b"Patients can only message doctors" in response.content

@pytest.mark.django_db
def test_chat_detail_doctor_to_doctor_forbidden(client, users_data):
    patient1, patient2, doctor1, doctor2 = users_data
    client.login(username='doctor1', password='pw')
    
    url = reverse('chat_detail', args=[doctor2.id])
    response = client.post(url, {'action': 'send_message', 'message': 'Hello'})
    
    assert response.status_code == 403
    assert b"Doctors can only message patients" in response.content

@pytest.mark.django_db
def test_chat_detail_patient_to_doctor_allowed(client, users_data):
    patient1, patient2, doctor1, doctor2 = users_data
    client.login(username='patient1', password='pw')
    
    url = reverse('chat_detail', args=[doctor1.id])
    response = client.post(url, {'action': 'send_message', 'message': 'Hello'})
    
    assert response.status_code == 302 # Redirect after successful post
    
@pytest.mark.django_db
@patch('requests.post')
def test_ai_chat_success_and_injection_defense(mock_post, client, settings):
    settings.GROQ_API_KEY = 'test-key'
    
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'Medical advice placeholder'}}]
    }
    mock_post.return_value = mock_response
    
    url = reverse('ai_chat')
    response = client.post(url, json.dumps({'message': 'I have a headache'}), content_type='application/json')
    
    assert response.status_code == 200
    assert response.json() == {'reply': 'Medical advice placeholder', 'doctors': []}
    
    # Check that wrapping happened
    called_json = mock_post.call_args.kwargs['json']
    assert '<user_input>' in called_json['messages'][-1]['content']
    assert 'I have a headache' in called_json['messages'][-1]['content']
    
@pytest.mark.django_db
@patch('requests.post')
def test_ai_chat_tool_call_finds_doctors(mock_post, client, users_data, settings):
    settings.GROQ_API_KEY = 'test-key'
    patient1, patient2, doctor1, doctor2 = users_data
    
    doctor1.doctor_profile.is_verified = True
    doctor1.doctor_profile.save()
    
    mock_response_1 = MagicMock()
    mock_response_1.ok = True
    mock_response_1.json.return_value = {
        'choices': [{'message': {
            'content': None,
            'tool_calls': [{
                'id': 'call_123',
                'function': {
                    'name': 'find_doctors',
                    'arguments': '{"specialization": "Cardiology"}'
                }
            }]
        }}]
    }
    
    mock_response_2 = MagicMock()
    mock_response_2.ok = True
    mock_response_2.json.return_value = {
        'choices': [{'message': {'content': 'You should see a Cardiologist.'}}]
    }
    
    mock_post.side_effect = [mock_response_1, mock_response_2]
    
    url = reverse('ai_chat')
    response = client.post(url, json.dumps({'message': 'My heart hurts'}), content_type='application/json')
    
    assert response.status_code == 200
    data = response.json()
    assert data['reply'] == 'You should see a Cardiologist.'
    assert len(data['doctors']) == 1
    assert data['doctors'][0]['specialization'] == 'Cardiology'
    assert data['doctors'][0]['id'] == doctor1.doctor_profile.id

@pytest.mark.django_db
@patch('requests.post')
def test_ai_chat_tool_call_no_doctors(mock_post, client, settings):
    settings.GROQ_API_KEY = 'test-key'
    
    mock_response_1 = MagicMock()
    mock_response_1.ok = True
    mock_response_1.json.return_value = {
        'choices': [{'message': {
            'content': None,
            'tool_calls': [{
                'id': 'call_456',
                'function': {
                    'name': 'find_doctors',
                    'arguments': '{"specialization": "Orthopedics"}'
                }
            }]
        }}]
    }
    
    mock_response_2 = MagicMock()
    mock_response_2.ok = True
    mock_response_2.json.return_value = {
        'choices': [{'message': {'content': 'We have no Orthopedics right now.'}}]
    }
    
    mock_post.side_effect = [mock_response_1, mock_response_2]
    
    url = reverse('ai_chat')
    response = client.post(url, json.dumps({'message': 'My bones hurt'}), content_type='application/json')
    
    assert response.status_code == 200
    data = response.json()
    assert data['reply'] == 'We have no Orthopedics right now.'
    assert len(data['doctors']) == 0

@pytest.mark.django_db
@patch('requests.post')
def test_ai_chat_tool_call_second_request_fails(mock_post, client, users_data, settings):
    settings.GROQ_API_KEY = 'test-key'
    patient1, patient2, doctor1, doctor2 = users_data
    
    mock_response_1 = MagicMock()
    mock_response_1.ok = True
    mock_response_1.json.return_value = {
        'choices': [{'message': {
            'content': None,
            'tool_calls': [{
                'id': 'call_123',
                'function': {
                    'name': 'find_doctors',
                    'arguments': '{"specialization": "Cardiology"}'
                }
            }]
        }}]
    }
    
    mock_response_2 = MagicMock()
    mock_response_2.ok = False
    
    mock_post.side_effect = [mock_response_1, mock_response_2]
    
    url = reverse('ai_chat')
    response = client.post(url, json.dumps({'message': 'My heart hurts'}), content_type='application/json')
    
    assert response.status_code == 500
    assert 'high traffic' in response.json()['error']

@pytest.mark.django_db
def test_ai_chat_missing_api_key(client, settings):
    settings.GROQ_API_KEY = None
    
    url = reverse('ai_chat')
    response = client.post(url, json.dumps({'message': 'Hello'}), content_type='application/json')
    
    assert response.status_code == 500
    assert 'GROQ_API_KEY is not configured' in response.json()['error']

@pytest.mark.django_db
@patch('requests.post')
def test_scan_prescription_success(mock_post, client, users_data, settings):
    settings.OPENROUTER_API_KEY = 'test-key'
    patient1, patient2, doctor1, doctor2 = users_data
    client.login(username='doctor1', password='pw')
    
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        'choices': [{'message': {'content': '{"medicines": [], "instructions": []}'}}]
    }
    mock_post.return_value = mock_response
    
    url = reverse('scan_prescription')
    response = client.post(url, json.dumps({'image': 'base64str'}), content_type='application/json')
    
    assert response.status_code == 200
    # Also verify prompt contains defense string
    called_json = mock_post.call_args.kwargs['json']
    defense_str_found = any('CRITICAL SECURITY WARNING' in item['text'] for item in called_json['messages'][0]['content'] if item['type'] == 'text')
    assert defense_str_found == True
    
@pytest.mark.django_db
def test_scan_prescription_missing_api_key(client, users_data, settings):
    settings.OPENROUTER_API_KEY = None
    patient1, patient2, doctor1, doctor2 = users_data
    client.login(username='doctor1', password='pw')
    
    url = reverse('scan_prescription')
    response = client.post(url, json.dumps({'image': 'base64str'}), content_type='application/json')
    
    assert response.status_code == 500
    assert 'OPENROUTER_API_KEY is not configured' in response.json()['error']

@pytest.mark.django_db
@patch('requests.post')
def test_ai_chat_rate_limit(mock_post, client, settings):
    settings.GROQ_API_KEY = 'test-key'
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {'choices': [{'message': {'content': 'Reply'}}]}
    mock_post.return_value = mock_response
    
    url = reverse('ai_chat')
    # Limit is 15. Make 15 successful requests.
    for i in range(15):
        resp = client.post(url, json.dumps({'message': 'hello'}), content_type='application/json')
        assert resp.status_code == 200
        
    # The 16th request should fail with 429
    response = client.post(url, json.dumps({'message': 'hello'}), content_type='application/json')
    assert response.status_code == 429
    assert 'Rate limit exceeded' in response.json().get('error', '')

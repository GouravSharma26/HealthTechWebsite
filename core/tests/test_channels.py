import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from healthtech.asgi import application
from core.models import ChatMessage

User = get_user_model()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_chat_consumer_roles():
    # Setup users
    patient = await User.objects.acreate(username="p_test1", is_patient=True)
    doctor = await User.objects.acreate(username="d_test1", is_doctor=True)
    
    # Authenticate patient trying to talk to doctor
    communicator = WebsocketCommunicator(application, f"ws/chat/{doctor.id}/")
    communicator.scope['user'] = patient
    
    connected, subprotocol = await communicator.connect()
    assert connected
    
    # Send message
    await communicator.send_json_to({"message": "Hello Doctor!"})
    
    # Receive message
    response = await communicator.receive_json_from()
    assert response['message'] == "Hello Doctor!"
    assert response['sender_id'] == patient.id
    
    # Verify DB
    msg_exists = await ChatMessage.objects.filter(sender=patient, receiver=doctor).aexists()
    assert msg_exists
    
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_chat_consumer_role_rejection():
    patient1 = await User.objects.acreate(username="p_test2", is_patient=True)
    patient2 = await User.objects.acreate(username="p_test3", is_patient=True)
    
    # Patient talking to Patient should be rejected
    communicator = WebsocketCommunicator(application, f"ws/chat/{patient2.id}/")
    communicator.scope['user'] = patient1
    
    connected, subprotocol = await communicator.connect()
    assert not connected

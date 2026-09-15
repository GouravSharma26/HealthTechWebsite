import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatMessage

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
            
        self.other_user_id = self.scope['url_route']['kwargs']['user_id']
        
        # Verify role restriction
        is_allowed = await self.verify_roles(self.user.id, self.other_user_id)
        if not is_allowed:
            await self.close()
            return
            
        # Create a unique room name based on sorted IDs
        ids = sorted([self.user.id, int(self.other_user_id)])
        self.room_name = f"chat_{ids[0]}_{ids[1]}"
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Save to database
        chat_msg = await self.save_message(self.user.id, self.other_user_id, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': self.user.id,
                'timestamp': chat_msg.timestamp.strftime('%b. %d, %Y, %I:%M %p')
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        sender_id = event['sender_id']
        timestamp = event.get('timestamp', '')

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'sender_id': sender_id,
            'timestamp': timestamp
        }))

    @database_sync_to_async
    def verify_roles(self, user_id, other_user_id):
        try:
            other_user = User.objects.get(id=other_user_id)
            user = User.objects.get(id=user_id)
            if user.is_patient and getattr(other_user, 'is_doctor', False):
                return True
            if user.is_doctor and getattr(other_user, 'is_patient', False):
                return True
            return False
        except User.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message_text):
        return ChatMessage.objects.create(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text
        )

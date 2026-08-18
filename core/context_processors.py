from .models import Notification, ChatMessage

def notifications(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        unread_msgs = ChatMessage.objects.filter(receiver=request.user, is_read=False).count()
        return {
            'unread_notifications': unread,
            'unread_messages_count': unread_msgs
        }
    return {}

from .models import Notification

def unread_notifications(request):
    if request.session.get("user_id"):
        count = Notification.objects.filter(user_id=request.session.get("user_id"), is_read=False).count()
        return {'unread_notif_count': count}
    return {'unread_notif_count': 0}

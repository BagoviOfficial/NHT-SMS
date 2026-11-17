from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import LoginHistory

def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
    LoginHistory.objects.create(
        user=user,
        username_attempted=user.username,
        ip_address=ip,
        user_agent=ua[:500],
        status=LoginHistory.Status.SUCCESS
    )
    user.last_login_ip = ip
    user.save(update_fields=['last_login_ip'])

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
    username = credentials.get('username', 'unknown')
    LoginHistory.objects.create(
        user=None,
        username_attempted=username[:150],
        ip_address=ip,
        user_agent=ua[:500],
        status=LoginHistory.Status.FAILED
    )

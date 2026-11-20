import uuid
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.mail import send_mail
from .models import NotificationChannel, NotificationStatus
from nht_sacco.apps.integrations.services import ConfigurationService

logger = logging.getLogger(__name__)


class BaseNotificationAdapter(ABC):
    @abstractmethod
    def send(self, recipient: str, title: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends notification to the provider.
        Must return dict:
        {
            'success': bool,
            'status': NotificationStatus,
            'external_id': str,
            'error_message': str,
            'raw_response': str
        }
        """
        pass


class AfricasTalkingSMSAdapter(BaseNotificationAdapter):
    """
    Adapter for Africa's Talking SMS API.
    Supports live dispatch via REST API or sandbox/simulated dispatch.
    """
    def send(self, recipient: str, title: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        username = ConfigurationService.get_str('sms.username', default=getattr(settings, 'AFRICASTALKING_USERNAME', 'sandbox'))
        api_key = ConfigurationService.get_secret('sms.api_key', fallback=getattr(settings, 'AFRICASTALKING_API_KEY', ''))
        sender_id = ConfigurationService.get_str('sms.sender_id', default=getattr(settings, 'AFRICASTALKING_SENDER_ID', 'NHT_SACCO'))
        sms_env = ConfigurationService.get_str('sms.environment', default=getattr(settings, 'AT_ENVIRONMENT', 'sandbox'))
        is_simulation = getattr(settings, 'NOTIFICATION_SIMULATION_MODE', True) or not api_key or (sms_env == 'sandbox')

        # Standardize phone number format (e.g. +254...)
        phone = recipient.strip()
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone

        if is_simulation:
            msg_id = f"AT_MSG_{uuid.uuid4().hex[:12].upper()}"
            logger.info(f"[AfricasTalking MOCK] Sent SMS to {phone}: '{message[:40]}...' (ID: {msg_id})")
            return {
                'success': True,
                'status': NotificationStatus.SENT,
                'external_id': msg_id,
                'error_message': '',
                'raw_response': json.dumps({'status': 'Success', 'message_id': msg_id, 'mode': 'sandbox'})
            }

        # Live dispatch
        try:
            import urllib.request
            import urllib.parse

            url = "https://api.africastalking.com/version1/messaging"
            headers = {
                'ApiKey': api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            data = urllib.parse.urlencode({
                'username': username,
                'to': phone,
                'message': message,
                'from': sender_id
            }).encode('utf-8')

            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_text = response.read().decode('utf-8')
                resp_json = json.loads(resp_text)
                recipients = resp_json.get('SMSMessageData', {}).get('Recipients', [])
                if recipients and recipients[0].get('status') in ['Success', 'Pending']:
                    return {
                        'success': True,
                        'status': NotificationStatus.SENT,
                        'external_id': recipients[0].get('messageId', ''),
                        'error_message': '',
                        'raw_response': resp_text
                    }
                else:
                    return {
                        'success': False,
                        'status': NotificationStatus.FAILED,
                        'external_id': '',
                        'error_message': resp_text,
                        'raw_response': resp_text
                    }
        except Exception as e:
            logger.error(f"Failed to send SMS via Africa's Talking: {str(e)}")
            return {
                'success': False,
                'status': NotificationStatus.FAILED,
                'external_id': '',
                'error_message': str(e),
                'raw_response': ''
            }


class MetaWhatsAppAdapter(BaseNotificationAdapter):
    """
    Adapter for Official Meta WhatsApp Business Cloud API.
    Supports official template messages with placeholders and sandbox simulation.
    """
    def send(self, recipient: str, title: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_token = ConfigurationService.get_secret('whatsapp.api_token', fallback=getattr(settings, 'WHATSAPP_API_TOKEN', ''))
        phone_number_id = ConfigurationService.get_str('whatsapp.phone_number_id', default=getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', ''))
        is_simulation = getattr(settings, 'NOTIFICATION_SIMULATION_MODE', True) or not api_token or not phone_number_id

        # Clean recipient phone number
        phone = recipient.strip().replace('+', '').replace(' ', '')
        if phone.startswith('0'):
            phone = '254' + phone[1:]

        if is_simulation:
            wamid = f"wamid.{uuid.uuid4().hex}"
            logger.info(f"[Meta WhatsApp MOCK] Sent WhatsApp to {phone}: '{message[:40]}...' (ID: {wamid})")
            return {
                'success': True,
                'status': NotificationStatus.SENT,
                'external_id': wamid,
                'error_message': '',
                'raw_response': json.dumps({'messaging_product': 'whatsapp', 'messages': [{'id': wamid}]})
            }

        # Live dispatch via Graph API
        try:
            import urllib.request
            url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            headers = {
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json'
            }
            payload = {
                'messaging_product': 'whatsapp',
                'to': phone,
                'type': 'text',
                'text': {'body': message}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_text = response.read().decode('utf-8')
                resp_json = json.loads(resp_text)
                msg_id = resp_json.get('messages', [{}])[0].get('id', '')
                return {
                    'success': True,
                    'status': NotificationStatus.SENT,
                    'external_id': msg_id,
                    'error_message': '',
                    'raw_response': resp_text
                }
        except Exception as e:
            logger.error(f"Failed to send Meta WhatsApp message: {str(e)}")
            return {
                'success': False,
                'status': NotificationStatus.FAILED,
                'external_id': '',
                'error_message': str(e),
                'raw_response': ''
            }


class EmailNotificationAdapter(BaseNotificationAdapter):
    """
    Adapter for transactional Email delivery using Django standard mail framework.
    """
    def send(self, recipient: str, title: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        email = recipient.strip()
        from_email = ConfigurationService.get_str('email.sender_email', default=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@northernhighways.co.ke'))
        mail_id = f"EMAIL_{uuid.uuid4().hex[:8].upper()}"

        try:
            sent_count = send_mail(
                subject=f"[NHT SACCO] {title}",
                message=message,
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False
            )
            return {
                'success': sent_count > 0,
                'status': NotificationStatus.SENT if sent_count > 0 else NotificationStatus.FAILED,
                'external_id': mail_id,
                'error_message': '' if sent_count > 0 else 'Zero recipients accepted email',
                'raw_response': f"send_mail returned count {sent_count}"
            }
        except Exception as e:
            logger.error(f"Failed to dispatch email: {str(e)}")
            return {
                'success': False,
                'status': NotificationStatus.FAILED,
                'external_id': '',
                'error_message': str(e),
                'raw_response': ''
            }


class InAppNotificationAdapter(BaseNotificationAdapter):
    """
    Adapter for in-app internal notification centre.
    """
    def send(self, recipient: str, title: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        inapp_id = f"INAPP_{uuid.uuid4().hex[:8].upper()}"
        return {
            'success': True,
            'status': NotificationStatus.DELIVERED,
            'external_id': inapp_id,
            'error_message': '',
            'raw_response': 'Delivered to member portal in-app inbox'
        }

"""
Twilio Service for Outbound Message Delivery
Handles the actual API calls to Twilio with proper error handling and logging
"""
import os
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

# Configure logging
logger = logging.getLogger(__name__)


class TwilioService:
    """
    Dedicated service for Twilio API operations
    Encapsulates all Twilio-specific logic with comprehensive error handling
    """
    
    def __init__(self):
        """Initialize Twilio client with credentials from environment"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN') 
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            raise ValueError("Missing Twilio credentials in environment variables")
        
        self.client = Client(self.account_sid, self.auth_token)
        
        logger.info(f"TwilioService initialized with phone number: {self.phone_number}")
    
    def send_message(self, to_phone: str, message_content: str, channel: str = 'whatsapp') -> Dict[str, Any]:
        """
        Send a message via Twilio with comprehensive error handling
        
        Args:
            to_phone: E.164 formatted recipient phone number
            message_content: Rendered message content
            channel: Message channel ('whatsapp', 'sms')
            
        Returns:
            Dict containing:
            - success: bool
            - message_sid: str (if successful)
            - error_code: str (if failed)
            - error_message: str (if failed)
            - status: str
        """
        try:
            # Format phone numbers based on channel
            if channel == 'whatsapp':
                from_phone = f"whatsapp:{self.phone_number}"
                to_phone_formatted = f"whatsapp:{to_phone}"
            else:
                from_phone = self.phone_number
                to_phone_formatted = to_phone
            
            # Send message via Twilio API
            message = self.client.messages.create(
                body=message_content,
                from_=from_phone,
                to=to_phone_formatted
            )
            
            logger.info(f"Message sent successfully: SID={message.sid}, To={to_phone}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'to_phone': to_phone,
                'channel': channel,
                'error_code': None,
                'error_message': None
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.code} - {e.msg}")
            
            return {
                'success': False,
                'message_sid': None,
                'status': 'failed',
                'to_phone': to_phone,
                'channel': channel,
                'error_code': str(e.code),
                'error_message': e.msg
            }
            
        except Exception as e:
            logger.error(f"Unexpected error sending message to {to_phone}: {str(e)}")
            
            return {
                'success': False,
                'message_sid': None,
                'status': 'failed',
                'to_phone': to_phone,
                'channel': channel,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e)
            }
    
    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """
        Retrieve message status from Twilio
        
        Args:
            message_sid: Twilio message SID
            
        Returns:
            Dict with message status information
        """
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'date_created': message.date_created,
                'date_updated': message.date_updated,
                'date_sent': message.date_sent,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'price': message.price,
                'price_unit': message.price_unit
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to fetch message status for {message_sid}: {e.code} - {e.msg}")
            
            return {
                'success': False,
                'error_code': str(e.code),
                'error_message': e.msg
            }
        
        except Exception as e:
            logger.error(f"Unexpected error fetching status for {message_sid}: {str(e)}")
            
            return {
                'success': False,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e)
            }
    
    def validate_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Validate phone number using Twilio Lookup API
        
        Args:
            phone_number: E.164 formatted phone number
            
        Returns:
            Dict with validation results
        """
        try:
            # Use Twilio Lookup API for validation
            lookup = self.client.lookups.phone_numbers(phone_number).fetch()
            
            return {
                'success': True,
                'phone_number': lookup.phone_number,
                'country_code': lookup.country_code,
                'national_format': lookup.national_format,
                'valid': True
            }
            
        except TwilioRestException as e:
            if e.code == 20404:  # Invalid phone number
                return {
                    'success': False,
                    'phone_number': phone_number,
                    'valid': False,
                    'error_code': str(e.code),
                    'error_message': 'Invalid phone number format'
                }
            else:
                logger.error(f"Lookup API error for {phone_number}: {e.code} - {e.msg}")
                return {
                    'success': False,
                    'phone_number': phone_number,
                    'valid': False,
                    'error_code': str(e.code),
                    'error_message': e.msg
                }
        
        except Exception as e:
            logger.error(f"Unexpected error validating {phone_number}: {str(e)}")
            return {
                'success': False,
                'phone_number': phone_number,
                'valid': False,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e)
            }


# Global instance for use across the application
twilio_service = TwilioService()
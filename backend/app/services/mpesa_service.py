import requests
import base64
import json
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

class MpesaService:
    def __init__(self, consumer_key: str, consumer_secret: str, passkey: str, shortcode: str):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.passkey = passkey
        self.shortcode = shortcode
        self.environment = os.getenv("MPESA_ENVIRONMENT", "sandbox")
        self.base_url = "https://sandbox.safaricom.co.ke" if self.environment == "sandbox" else "https://api.safaricom.co.ke"
        self._access_token = None
        self._token_expiry = None
        self.connected = False
        
        # Initialize connection
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with M-PESA API"""
        try:
            auth = base64.b64encode(
                f"{self.consumer_key}:{self.consumer_secret}".encode()
            ).decode()
            
            response = requests.post(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {auth}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get('access_token')
                self._token_expiry = datetime.now().timestamp() + data.get('expires_in', 3600) - 60
                self.connected = True
                return True
            else:
                logger.error(f"M-PESA authentication failed: {response.text}")
                self.connected = False
                return False
                
        except Exception as e:
            logger.error(f"M-PESA authentication error: {str(e)}")
            self.connected = False
            return False
    
    def _get_access_token(self) -> Optional[str]:
        """Get valid access token"""
        if not self._access_token or datetime.now().timestamp() >= self._token_expiry:
            if not self._authenticate():
                return None
        return self._access_token
    
    def stk_push(self, phone: str, amount: float, account_reference: str, 
                 transaction_desc: str) -> Dict[str, Any]:
        """Initiate STK Push payment"""
        try:
            token = self._get_access_token()
            if not token:
                return {"error": "Authentication failed", "ResponseCode": "-1"}
            
            phone = self._format_phone(phone)
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{self.shortcode}{self.passkey}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone,
                "PartyB": self.shortcode,
                "PhoneNumber": phone,
                "CallBackURL": "https://your-domain.com/api/v1/payment/callback",
                "AccountReference": account_reference[:12],
                "TransactionDesc": transaction_desc[:20]
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=10
            )
            
            result = response.json()
            return result
            
        except Exception as e:
            logger.error(f"STK Push error: {str(e)}")
            return {"error": str(e), "ResponseCode": "-1"}
    
    def query_status(self, checkout_request_id: str) -> Dict[str, Any]:
        """Query STK Push status"""
        try:
            token = self._get_access_token()
            if not token:
                return {"error": "Authentication failed", "ResultCode": "-1"}
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{self.shortcode}{self.passkey}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            response = requests.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=10
            )
            
            result = response.json()
            return result
            
        except Exception as e:
            logger.error(f"Query status error: {str(e)}")
            return {"error": str(e), "ResultCode": "-1"}
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number for M-PESA"""
        # Remove any non-numeric characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Ensure it starts with 254
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif not phone.startswith('254') and not phone.startswith('07'):
            phone = '254' + phone
        elif phone.startswith('07'):
            phone = '254' + phone[1:]
        
        return phone

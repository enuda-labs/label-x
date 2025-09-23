
import decimal
import json
from django.conf import settings
import requests

from common.responses import ApiResponse
from paystackapi.misc import Misc
from django.conf import settings
import hmac
import hashlib


def verify_paystack_origin(request)->bool:
    secret = settings.PAYSTACK_SECRET_KEY
    
    raw_body = request.body
    computed_signature = hmac.new(
        key=bytes(secret, 'utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha512,
    ).hexdigest()
    
    received_signature = request.headers.get('x-paystack-signature')
    
    if computed_signature != received_signature:
        return False
    return True


def convert_usd_to_ngn(amount) -> decimal.Decimal:
    """
    Convert USD to NGN
    """
    url = f"https://v6.exchangerate-api.com/v6/{settings.EXCHANGE_RATE_API_KEY}/latest/USD"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        value = decimal.Decimal(data['conversion_rates']['NGN']) * decimal.Decimal(amount)
        return value.quantize(decimal.Decimal('0.01')) #round to 2 decimal places
    return decimal.Decimal('1500') * decimal.Decimal(amount)

def find_bank_by_code(target_code):
    """
    Find a bank by its code from the list of Nigerian banks.
        
    Returns:
        {
            "id": 1,
            "name": "Access Bank",
            "slug": "access-bank",
            "code": "044",
            "longcode": "044150149",
            "gateway": "emandate",
            "pay_with_bank": False,
            "active": True,
            "country": "Nigeria",
            "currency": "NGN",
            "type": "nuban",
            "is_deleted": False,
            "createdAt": "2016-07-14T10:04:29.000Z",
            "updatedAt": "2020-02-18T08:06:44.000Z"
        }
    """
    response = Misc.list_banks(currency="NGN")
    if response.get('status'):
        bank = next((bank for bank in response['data'] if bank['code'] == target_code), None)
        return bank
    return None


def request_paystack(path, method='get', data=None, params=None):
    base_url = "https://api.paystack.co"
    url = f"{base_url}{path}"
    headers = {'Authorization': f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    
   

    if method.lower() == 'get':
        response = requests.get(url, headers=headers, params=params)
    else:
        response = requests.post(url, headers=headers, json=data)
        
    
    try:
        json_data = response.json()
    except Exception as e:
        json_data = None
        
    if response.status_code == 200 or response.status_code == 201:
        return ApiResponse(error=False, body=json_data, message="Success", status_code=response.status_code)
    
    if json_data and json_data.get('message'):
        return ApiResponse(error=True, body=response.json(), message=json_data.get('message'), status_code=response.status_code)

    
    return ApiResponse(error=True, body=json_data, message=response.text, status_code=response.status_code)


        

def resolve_bank_details(bank_code, account_number):    
    if settings.PAYSTACK_PUBLIC_KEY.startswith('pk_test'): 
        #paystack implements a rate limit for the test mode, so we use a default bank code
        bank_code = '001'
    # bank_code remains unchanged in production
        
    response = request_paystack(f"/bank/resolve?account_number={account_number}&bank_code={bank_code}")
    if response.error:
        return None
    
    return response.body
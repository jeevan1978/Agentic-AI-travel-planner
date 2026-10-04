"""Live StayingAPI adapter; never uses a local accommodation inventory."""
import os
import requests
from datetime import date
from utils.budget import valid_amount


def search_stay_hotels(location, check_in='', check_out='', guests=1, hotel_type='Budget', max_price=None):
    base = {'source': 'StayingAPI', 'location': location, 'check_in': check_in, 'check_out': check_out}
    def unavailable(reason):
        return {**base, 'success': False, 'status': 'UNAVAILABLE', 'source_type': 'UNAVAILABLE', 'hotels': [], 'reason': reason}
    if os.getenv('STAYING_API_KEY', '').startswith(('stay_test_', 'stay_sandbox_')):
        return unavailable('STAYING_API_KEY is a sandbox key; configure a stay_live_ key for real accommodation results')
    if not os.getenv('STAYING_API_KEY'):
        return unavailable('STAYING_API_KEY is not configured')
    try:
        response = requests.get(os.getenv('STAY_SEARCH_URL', 'https://api.stayingapi.com/v1/search'),
            params={'location': location, 'checkIn': check_in, 'checkOut': check_out, 'adults': guests, 'rooms': 1, 'currency': 'INR', 'limit': 10},
            headers={'Authorization': 'Bearer ' + os.environ['STAYING_API_KEY']}, timeout=20)
        if response.status_code != 200:
            return unavailable(f'StayingAPI HTTP {response.status_code}')
        data = response.json()
        provider_warnings = data.get('meta', {}).get('warnings', [])
        if any(isinstance(w, dict) and w.get('code') == 'sandbox_data' for w in provider_warnings):
            return unavailable('StayingAPI returned sandbox fixtures rather than live accommodation; configure a live key')
        hotels = []
        for row in data.get('data', []):
            if not row.get('name'):
                continue
            price = row.get('price') or {}
            expected_nights = (date.fromisoformat(check_out)-date.fromisoformat(check_in)).days
            total = price.get('totalPrice') if price.get('nights') in (None, expected_nights) else None
            hotels.append({'id': row.get('id'), 'name': row['name'], 'url': row.get('url'),
                'location': row.get('location'), 'rating': row.get('guestRating'), 'rating_scale': row.get('ratingScale'),
                'price_per_night': price.get('nightlyPrice'), 'total_price': total,
                'currency': price.get('currency'), 'source': 'StayingAPI', 'source_type': 'LIVE_PROVIDER'})
        if not hotels:
            return unavailable('No accommodation returned for requested period')
        selected = min(hotels, key=lambda h: valid_amount(h['total_price']) if h['currency']=='INR' and valid_amount(h['total_price']) is not None else float('inf'))
        return {**base, **selected, 'success': True, 'status': 'SUCCESS', 'hotels': hotels, 'warnings': data.get('meta', {}).get('warnings', [])}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return unavailable('StayingAPI request or response failed')

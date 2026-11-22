"""Rate-limited address lookup for explicit map interactions."""

import json
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

BASE_URL = 'https://nominatim.openstreetmap.org'
USER_AGENT = 'Marshrut.Doc/0.1 (https://github.com/skillshifting/Marshrut.Doc)'
_lock = Lock()
_cache = {}
_last_request = 0.0


def _lookup(path, params):
    global _last_request
    key = (path, tuple(sorted(params.items())))
    with _lock:
        if key in _cache:
            return _cache[key]
        time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        url = f'{BASE_URL}/{path}?{urlencode({**params, "format": "jsonv2", "accept-language": "ru"})}'
        request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
        try:
            with urlopen(request, timeout=8) as response:
                result = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise HTTPException(503, 'Сервис адресов сейчас недоступен. Укажите место вручную.') from exc
        _cache[key] = result
        return result


def _short_address(result):
    parts = result.get('address') or {}
    street = next((parts[k] for k in ('road', 'pedestrian', 'residential', 'footway', 'street', 'square') if parts.get(k)), '')
    house = parts.get('house_number', '')
    locality = next((parts[k] for k in ('city', 'town', 'village', 'municipality', 'hamlet', 'suburb', 'county') if parts.get(k)), '')
    street_line = ' '.join(filter(None, (street, house)))
    return ', '.join(filter(None, (street_line, locality))) or result.get('display_name', '')


def reverse(lat: float, lon: float):
    result = _lookup('reverse', {'lat': f'{lat:.6f}', 'lon': f'{lon:.6f}', 'zoom': 18, 'addressdetails': 1})
    return {'address': _short_address(result), 'lat': lat, 'lon': lon}


def search(query: str):
    result = _lookup('search', {'q': query, 'limit': 1})
    if not result:
        raise HTTPException(404, 'Место не найдено. Попробуйте указать город и регион.')
    return {'lat': float(result[0]['lat']), 'lon': float(result[0]['lon']), 'label': result[0].get('display_name', query)}

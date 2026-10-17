import json
import logging
import time
import uuid
from datetime import datetime, timezone


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        if request.path == '/api/health/':
            return response
        # No credentials, card numbers, query strings or request bodies in logs.
        logging.getLogger('bank.requests').info(json.dumps({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': 'error' if response.status_code >= 500 else 'warning' if response.status_code >= 400 else 'info',
            'service': 'bank-api', 'request_id': request_id, 'method': request.method,
            'path': request.path, 'status': response.status_code,
            'duration_ms': round((time.monotonic() - started) * 1000, 2),
        }))
        return response

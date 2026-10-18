import json
import logging
import time
import uuid
from datetime import datetime, timezone
from .tracing import trace_fields


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        response = self.get_response(request)
        fields = trace_fields()
        if fields:
            response['X-Trace-ID'] = fields['trace_id']
        response['X-Request-ID'] = request_id
        if request.path == '/api/health/':
            return response
        # No credentials, card numbers, query strings or request bodies in logs.
        logging.getLogger('bank.requests').info(json.dumps({
            **fields,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': 'error' if response.status_code >= 500 else 'warning' if response.status_code >= 400 else 'info',
            'service': 'bank-api', 'request_id': request_id, 'method': request.method,
            'path': request.path, 'status': response.status_code,
            'duration_ms': round((time.monotonic() - started) * 1000, 2),
        }))
        return response

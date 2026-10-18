"""Verify the real Django -> Alloy -> Loki -> Grafana pipeline using only stdlib."""
import base64
import argparse
import json
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--request-id', type=uuid.UUID, help='Verify an earlier probe after restarting monitoring.')
arguments = parser.parse_args()
values = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines()
              if '=' in line and not line.lstrip().startswith('#'))
port = int(values.get('GRAFANA_PORT', '3001'))
grafana = f'http://127.0.0.1:{port}'
password = values.get('GRAFANA_ADMIN_PASSWORD')
if not password:
    raise SystemExit('Run python3 scripts/init_env.py first.')
authorization = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()


def get(path, auth=True):
    request = urllib.request.Request(grafana + path,
        headers={'Authorization': authorization} if auth else {})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def wait_for(check, description, seconds=90):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                print(description + ': OK', flush=True)
                return result
        except (OSError, http.client.HTTPException, ValueError, KeyError, AssertionError) as error:
            last = error
        time.sleep(2)
    raise SystemExit(description + ': not ready (' + type(last).__name__ + ')')


def query(expression, range_query=False):
    params = {'query': expression}
    route = 'query_range' if range_query else 'query'
    if range_query:
        params.update(start=str(int((time.time() - 3600) * 1_000_000_000)),
                      end=str(time.time_ns()), limit='100')
    return get('/api/datasources/proxy/uid/banklab-loki/loki/api/v1/' + route + '?' + urllib.parse.urlencode(params))


wait_for(lambda: get('/api/health', auth=False).get('database') == 'ok', 'Grafana')
wait_for(lambda: get('/api/datasources/uid/banklab-loki/health').get('status') == 'OK', 'Loki datasource')
dashboard = wait_for(lambda: get('/api/dashboards/uid/bank-lab-api').get('dashboard'), 'Provisioned dashboard')

# Read-only probes: one successful request and one expected unauthenticated 401.
if arguments.request_id:
    request_id = str(arguments.request_id)
else:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/docs/', timeout=10) as response:
        response.read()
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/api/bank/', timeout=10)
        raise AssertionError('Bank endpoint must require authentication.')
    except urllib.error.HTTPError as response:
        assert response.code == 401
        request_id = response.headers['X-Request-ID']


def find_request():
    result = query('{service="bank-api", environment="local"} |= "' + request_id + '"', True)
    for stream in result['data']['result']:
        for _, line in stream['values']:
            row = json.loads(line)
            if row.get('request_id') == request_id:
                assert row['status'] == 401 and row['path'] == '/api/bank/'
                assert row['level'] == 'warning' and row['duration_ms'] >= 0
                assert set(row) <= {'timestamp', 'level', 'service', 'request_id', 'method', 'path', 'status', 'duration_ms', 'trace_id', 'span_id'}
                return row
    return None


wait_for(find_request, 'Django request found in Loki through Grafana')
print('Verified X-Request-ID: ' + request_id, flush=True)
checked = 0
for panel in dashboard['panels']:
    if panel['type'] == 'logs':
        continue
    for target in panel.get('targets', []):
        expression = target['expr'].replace('$__range', '1h').replace('$__interval', '1m')
        result = query(expression)
        assert result['status'] == 'success', panel['title']
        if panel['type'] == 'stat':
            assert result['data']['result'], 'No data: ' + panel['title']
        checked += 1
print(f'Dashboard LogQL queries: {checked} OK', flush=True)
print('Open ' + grafana + '/d/bank-lab-api', flush=True)

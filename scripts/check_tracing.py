"""Exercise a real transfer and verify trace propagation, SQL spans and log correlation."""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

values = dict(line.split('=', 1) for line in (Path(__file__).resolve().parent.parent / '.env').read_text().splitlines()
              if '=' in line and not line.startswith('#'))
grafana = 'http://127.0.0.1:' + values.get('GRAFANA_PORT', '3001')
basic = 'Basic ' + base64.b64encode(('admin:' + values['GRAFANA_ADMIN_PASSWORD']).encode()).decode()


def call(url, data=None, headers=None):
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, json.load(response)


def api(path, data=None, headers=None):
    return call('http://127.0.0.1:8000/api/' + path + '/', data, headers)


def get(path):
    status, _, result = call(grafana + path, headers={'Authorization': basic})
    assert status == 200, (status, result)
    return result


def wait(check, label):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                print(label + ': OK', flush=True)
                return result
        except (OSError, ValueError, KeyError, AssertionError):
            pass
        time.sleep(2)
    raise AssertionError(label + ': timed out')


# An isolated disposable user keeps Alice/Bob demo balances unchanged.
password = 'Trace-lab-' + uuid.uuid4().hex
status, _, user = api('auth/register', {'email': 'trace-' + uuid.uuid4().hex + '@banklab.test',
                                       'name': 'Tracing check', 'password': password})
assert status == 201, status
headers = {'Authorization': 'Token ' + user['token']}
accounts = []
for _ in range(2):
    status, _, account = api('accounts', {}, headers)
    assert status == 201
    accounts.append(account)
assert api('topup', {'account_id': accounts[0]['id'], 'amount': '1.00'}, headers)[0] == 200
trace_id, parent_id = uuid.uuid4().hex, uuid.uuid4().hex[:16]
payload = {'account_id': accounts[0]['id'], 'card_number': accounts[1]['card_number'],
           'amount': '0.01', 'request_id': str(uuid.uuid4())}
status, response_headers, body = api('transfers', payload,
    {**headers, 'traceparent': f'00-{trace_id}-{parent_id}-01'})
assert status == 201, (status, body)
assert response_headers['X-Trace-ID'] == trace_id
request_id = response_headers['X-Request-ID']


def find_trace():
    result = get('/api/datasources/proxy/uid/banklab-tempo/api/traces/' + trace_id)
    batches = result.get('batches', result.get('resourceSpans', []))
    spans = [span for batch in batches for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', []))
             for span in scope.get('spans', [])]
    names = [span['name'] for span in spans]
    if 'bank.transfer' not in names or 'bank.balance_change' not in names:
        return None
    assert any('SELECT' in name.upper() for name in names), names
    encoded = json.dumps(result)
    for secret in [password, user['token'], *(account['card_number'] for account in accounts)]:
        assert secret not in encoded, 'Sensitive value in trace'
    assert 'db.statement' not in encoded and 'db.query.text' not in encoded
    server = next(span for span in spans if span.get('kind') in (2, 'SPAN_KIND_SERVER'))
    def hex_id(value):
        return value if len(value) in (16, 32) else base64.b64decode(value).hex()
    assert hex_id(server['parentSpanId']) == parent_id
    return spans, hex_id(server['spanId'])


spans, server_span_id = wait(find_trace, 'Transfer + PostgreSQL spans in Tempo')


def find_log():
    params = urllib.parse.urlencode({'query': '{service="bank-api"} |= "' + request_id + '"',
        'start': str(int((time.time()-300)*1e9)), 'end': str(time.time_ns()), 'limit': '100'})
    result = get('/api/datasources/proxy/uid/banklab-loki/loki/api/v1/query_range?' + params)
    for stream in result['data']['result']:
        for _, line in stream['values']:
            row = json.loads(line)
            if row.get('request_id') == request_id:
                assert row['trace_id'] == trace_id and row['span_id'] == server_span_id
                assert row['status'] == 201
                return row


wait(find_log, 'Loki log matches server span and trace')
source = get('/api/datasources/uid/banklab-loki')
assert source['jsonData']['derivedFields'][0]['url'] == '${__value.raw}'
assert source['jsonData']['derivedFields'][0]['datasourceUid'] == 'banklab-tempo'
tempo_source = get('/api/datasources/uid/banklab-tempo')
assert '${__trace.traceId}' in tempo_source['jsonData']['tracesToLogsV2']['query']
# Replaying one business operation must not charge again, but gets a new HTTP trace.
status, replay_headers, replay = api('transfers', payload, headers)
assert status == 200 and replay['replayed'] and replay['reference'] == body['reference']
status, _, bank = api('bank', headers=headers)
assert status == 200
assert [account['balance'] for account in bank['accounts']] == ['0.99', '0.01']
assert replay_headers['X-Trace-ID'] != trace_id
# Invalid incoming trace context is replaced with a valid server trace.
status, bad_headers, _ = api('bank', headers={**headers, 'traceparent': 'broken'})
assert status == 200 and len(bad_headers['X-Trace-ID']) == 32
print(f'W3C propagation, privacy, replay and invalid context: OK ({len(spans)} spans)')
print('Trace ID: ' + trace_id)
print('Request ID: ' + request_id)
print('Grafana: ' + grafana + '/explore (Bank Lab Tempo → Trace ID)')

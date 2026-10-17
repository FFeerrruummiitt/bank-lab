"""Add missing local secrets without changing existing credentials."""
import secrets
import os
from pathlib import Path

target = Path(__file__).resolve().parent.parent / '.env'
content = target.read_text() if target.exists() else ''
lines = content.splitlines()
sizes = {'POSTGRES_PASSWORD': 24, 'DJANGO_SECRET_KEY': 48, 'GRAFANA_ADMIN_PASSWORD': 24}
present = set()
for index, line in enumerate(lines):
    if '=' not in line or line.lstrip().startswith('#'):
        continue
    key, value = line.split('=', 1)
    key = key.strip()
    present.add(key)
    if key in sizes and not value.strip():
        lines[index] = key + '=' + secrets.token_hex(sizes[key])
additions = []
for key, size in sizes.items():
    if key not in present:
        additions.append(key + '=' + secrets.token_hex(size))
updated = '\n'.join(lines + additions) + '\n'
if updated != content:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write(updated)
target.chmod(0o600)
print('Local secrets ready; existing values preserved. Grafana password is in .env.')

"""Generate local development secrets without overwriting an existing .env."""
import secrets
from pathlib import Path

target = Path(__file__).resolve().parent.parent / '.env'
if target.exists():
    print('.env already exists; kept unchanged.')
else:
    with target.open('x') as file:
        file.write('POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n')
        file.write('DJANGO_SECRET_KEY=' + secrets.token_hex(48) + '\n')
    target.chmod(0o600)
    print('Created .env with random local secrets.')

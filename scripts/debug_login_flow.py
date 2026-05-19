import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()
from app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/auth/login')
print('GET /auth/login', resp.status_code)
print('login page contains flash block?', b'get_flashed_messages' in resp.data)
print('form action contains /auth/login?', b'action="/auth/login"' in resp.data)

import re

match = re.search(r'name="csrf_token" value="([^"]+)"', resp.data.decode('utf-8', errors='ignore'))
if match:
    csrf_token = match.group(1)
    print('csrf token found:', csrf_token[:10], '...')
else:
    csrf_token = None
    print('csrf token not found in login page')

resp2 = client.post('/auth/login', data={'email': 'gestor@horizonte.com.br', 'senha': 'wrongpass', 'csrf_token': csrf_token}, follow_redirects=False)
print('POST /auth/login status', resp2.status_code)
print('redirect location', resp2.headers.get('Location'))
with client.session_transaction() as sess:
    print('session keys after post:', list(sess.keys()))
    print('session flashes after post:', sess.get('_flashes'))

# Follow redirect manually to inspect the final rendered page
if resp2.status_code in (301, 302, 303, 307, 308):
    resp3 = client.get(resp2.headers['Location'])
    print('GET redirect page status', resp3.status_code)
    body = resp3.data.decode('utf-8', errors='ignore')
    print('flash contains invalid?', 'E-mail, senha' in body)
    print('contains Atencao?', 'Atenção' in body)
    print('contains danger?', 'danger' in body)
    print('contains flash container class?', 'bg-red-50 text-red-700' in body)
    print('body length', len(body))
    print(body[:2600])

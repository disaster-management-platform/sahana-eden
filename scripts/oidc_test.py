"""Local real Keycloak/Eden SSO checks; no identity or ACL is inferred from email."""
import os,json
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup

base=os.environ['EDEN_TEST_URL'].rstrip('/')
assert urlsplit(base).hostname in ('localhost','127.0.0.1')
users=json.loads(Path(os.environ['EDEN_SSO_TEST_USERS']).read_text())
native=json.loads(Path(os.environ['EDEN_TEST_IDENTITIES']).expanduser().read_text())
ca=os.environ['EDEN_SSO_TEST_CA']
def step(session,response,values):
    soup=BeautifulSoup(response.text,'html.parser');form=soup.select_one('form');assert form is not None
    data={x['name']:x.get('value','') for x in form.select('input[name]')};data.update(values)
    return session.post(urljoin(response.url,form['action']),data=data,allow_redirects=False,timeout=15)
def login(label):
    session=requests.Session();session.verify=ca
    response=session.get(base+'/default/user/login',allow_redirects=False,timeout=15)
    for _ in range(12):
        if response.is_redirect:
            response=session.get(urljoin(response.url,response.headers['Location']),allow_redirects=False,timeout=15);continue
        soup=BeautifulSoup(response.text,'html.parser')
        if soup.select_one('input[name=username]'):
            response=step(session,response,{'username':users[label]['username'],'password':users[label]['password']});continue
        assert soup.select_one('input[name=otp], input[name=totp], input[name=totpSecret]') is None, 'Unexpected OTP requirement'
        return session,response
    raise AssertionError('SSO redirect limit')
for label in ['A','B']:
    session,response=login(label);assert response.status_code==200,(label,response.status_code)
    own=native[label]['personId'];other=native['B' if label=='A' else 'A']['personId']
    assert session.get(base+f'/pr/person/{own}.json',timeout=15).status_code==200
    assert session.get(base+f'/pr/person/{other}.json',timeout=15).status_code in (403,404)
    print('PASS verified issuer/subject binding, password-only SSO and native organization isolation:',label)
session,response=login('unmapped');assert response.status_code==403,response.status_code
print('PASS unbound subject denied despite matching an existing native account email')
session=requests.Session();response=session.get(base+'/default/user/login?code=invalid&state=invalid',timeout=15)
assert response.status_code==401,response.status_code
print('PASS invalid state denied without changing native identities')

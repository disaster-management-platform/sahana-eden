"""OIDC login for explicitly provisioned Eden accounts; native ACLs remain authoritative."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import jwt
import requests
from gluon import HTTP, current, redirect
from gluon.storage import Storage
from requests.adapters import HTTPAdapter
from s3dal import filter_fields


class ProviderTLS(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        # A private network address still authenticates the public issuer's TLS name.
        kwargs.update(server_hostname=urlsplit(os.environ['EDEN_OIDC_ISSUER']).hostname,
                      assert_hostname=urlsplit(os.environ['EDEN_OIDC_ISSUER']).hostname)
        return super().init_poolmanager(*args, **kwargs)


class EdenOIDC:
    def get_user(self):
        return None

    def _setting(self, name):
        value = os.environ.get('EDEN_OIDC_' + name)
        if not value:
            raise HTTP(503, 'Identity configuration unavailable')
        return value

    def _remote(self, url, data=None):
        issuer = self._setting('ISSUER').rstrip('/')
        if not issuer.startswith('https://') or not url.startswith(issuer + '/'):
            raise HTTP(503, 'Invalid identity endpoint')
        backchannel = os.environ.get('EDEN_OIDC_BACKCHANNEL')
        with requests.Session() as client:
            client.verify = os.environ.get('EDEN_OIDC_CA_FILE') or True
            if backchannel:
                parsed = urlsplit(backchannel)
                if parsed.scheme != 'https' or parsed.username or parsed.query or parsed.fragment:
                    raise HTTP(503, 'Invalid identity backchannel')
                client.mount(backchannel, ProviderTLS())
                url = backchannel.rstrip('/') + url[len(issuer):]
            try:
                response = client.request('POST' if data else 'GET', url, data=data,
                                          timeout=(3, 5), allow_redirects=False, stream=True)
                with response:
                    if response.status_code != 200:
                        raise HTTP(503, 'Identity provider unavailable')
                    content = bytearray()
                    for chunk in response.iter_content(4096):
                        content.extend(chunk)
                        if len(content) > 262144:
                            raise HTTP(503, 'Invalid identity response')
                    return json.loads(content)
            except (requests.RequestException, ValueError):
                raise HTTP(503, 'Identity provider unavailable')

    def login_form(self):
        issuer = self._setting('ISSUER').rstrip('/')
        callback = self._setting('REDIRECT_URI')
        uri = urlsplit(callback)
        if uri.scheme != 'https' and not (uri.scheme == 'http' and uri.hostname in ('127.0.0.1', 'localhost') and os.environ.get('EDEN_OIDC_LOCAL_DEVELOPMENT') == 'true'):
            raise HTTP(503, 'HTTPS callback required')
        metadata = current.cache.ram('platform-oidc:' + issuer,
                                     lambda: self._remote(issuer + '/.well-known/openid-configuration'), 300)
        if metadata.get('issuer') != issuer:
            raise HTTP(503, 'Invalid identity issuer')
        session, variables = current.session, current.request.get_vars
        if variables.get('error'):
            session.pop('platform_oidc_pending', None)
            raise HTTP(401, 'Identity authentication denied')
        if not variables.get('code'):
            verifier = secrets.token_urlsafe(48)
            pending = dict(state=secrets.token_urlsafe(32), nonce=secrets.token_urlsafe(32), verifier=verifier, created=time.time())
            session.platform_oidc_pending = pending
            endpoint = metadata.get('authorization_endpoint', '')
            if not endpoint.startswith(issuer + '/'):
                raise HTTP(503, 'Invalid authorization endpoint')
            redirect(endpoint + '?' + urlencode(dict(client_id=self._setting('CLIENT_ID'), redirect_uri=callback,
                response_type='code', scope='openid', state=pending['state'], nonce=pending['nonce'],
                code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='), code_challenge_method='S256')))
        pending = session.pop('platform_oidc_pending', None)
        if not pending or time.time() - pending['created'] > 300 or not isinstance(variables.get('state'), str) or not hmac.compare_digest(pending['state'], variables.state):
            raise HTTP(401, 'Invalid authentication state')
        tokens = self._remote(metadata['token_endpoint'], dict(grant_type='authorization_code', client_id=self._setting('CLIENT_ID'),
            client_secret=self._setting('CLIENT_SECRET'), code=variables.code, redirect_uri=callback, code_verifier=pending['verifier']))
        try:
            encoded = tokens['id_token']
            header = jwt.get_unverified_header(encoded)
            if header.get('alg') != 'RS256':
                raise ValueError()
            keys = current.cache.ram('platform-oidc-keys:' + issuer, lambda: self._remote(metadata['jwks_uri']), 300)
            key = next(k for k in keys['keys'] if k['kid'] == header['kid'])
            claims = jwt.decode(encoded, jwt.PyJWK.from_dict(key).key, algorithms=['RS256'], issuer=issuer,
                                audience=self._setting('CLIENT_ID'), options={'require': ['iss', 'sub', 'aud', 'exp', 'iat', 'nonce']})
            if claims['nonce'] != pending['nonce'] or claims.get('azp', self._setting('CLIENT_ID')) != self._setting('CLIENT_ID'):
                raise ValueError()
            bindings = json.loads(Path(self._setting('BINDINGS_FILE')).read_text())
            matches = [b for b in bindings if b['issuer'] == issuer and b['subject'] == claims['sub']]
            if len(matches) != 1:
                raise ValueError()
            binding = matches[0]
            auth = current.auth
            table = auth.settings.table_user
            user = table[int(binding['userId'])]
            if not user or user.registration_key not in (None, '') or auth.is_user_locked(user) or str(user.organisation_id) != str(binding['edenOrganizationId']) or claims.get('organization_id') != binding['organizationId']:
                raise ValueError()
        except (ValueError, KeyError, TypeError, OSError, StopIteration, jwt.InvalidTokenError):
            raise HTTP(403, 'Identity is not provisioned for this Eden account')
        auth.login_user(Storage(filter_fields(table, user, allow_id=True)))
        redirect('/' + current.request.application + '/default/index')

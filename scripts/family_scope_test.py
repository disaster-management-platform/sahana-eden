"""Verify the native DVR family viewing scope before automatic group creation."""
import os
import requests
from platform_test import admin, base, identities, rows

owner = identities['A']
foreign = str(identities['B']['personId'])
primary = os.environ['EDEN_FAMILY_OWNER_PERSON']
member = os.environ['EDEN_FAMILY_OWNER_MEMBER']
session = requests.Session()
session.auth = (owner['email'], owner['password'])
before = rows(admin, f'/dvr/person/{foreign}/group_membership.json?limit=100')
response = session.get(base + '/dvr/group_membership.json',
                       params={'viewing': 'pr_person.' + primary}, timeout=20)
assert response.status_code == 200
response = session.post(base + '/dvr/group_membership/create.json',
                        params={'viewing': 'pr_person.' + foreign},
                        data={'person_id': member}, timeout=20, allow_redirects=False)
assert response.status_code in (403, 404)
after = rows(admin, f'/dvr/person/{foreign}/group_membership.json?limit=100')
assert before == after
print('PASS own family scope and foreign rejection before native side effects')

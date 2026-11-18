"""Native Eden provisioning and scoped integration checks; local synthetic records only."""
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

base=os.environ['EDEN_TEST_URL'].rstrip('/')
assert urlparse(base).hostname in ('127.0.0.1','localhost')
config=Path(os.environ['EDEN_ADMIN_CONFIG']).expanduser()
values={k.strip():v.strip().strip('\"\'') for line in config.read_text().splitlines() if '=' in line and not line.lstrip().startswith('#') for k,v in [line.split('=',1)]}
admin=requests.Session();admin.auth=(values['EDEN_ADMIN_USER'],values['EDEN_ADMIN_PASSWORD'])
private=Path(os.environ['EDEN_TEST_IDENTITIES']).expanduser()
if private.exists(): identities=json.loads(private.read_text())
else:
    identities={label:{'email':f"platform{os.environ.get('EDEN_TEST_FLOW','07b')}-{label.lower()}@example.invalid",'password':secrets.token_urlsafe(32)} for label in ('A','B')}
    fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(identities,stream)

def form(session,path,updates,expected_errors=()):
    r=session.get(base+path,timeout=20);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser');f=soup.select_one('form input[name=_formname]')
    assert f is not None,(path,r.status_code)
    parent=f.find_parent('form');data={}
    for e in parent.select('input[name],textarea[name],select[name]'):
        if e.get('type') in ('submit','checkbox','radio'):continue
        if e.name=='select':
            option=e.select_one('option[selected]') or e.select_one('option')
            data[e['name']]=option.get('value','') if option else ''
        else:data[e['name']]=e.get('value',e.text if e.name=='textarea' else '')
    data.update(updates)
    r=session.post(base+path,data=data,timeout=20);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    errors={e.get('id') for e in soup.select('.error')}
    assert errors==set(expected_errors),(path,errors)
    return r

def rows(session,path):
    r=session.get(base+path,timeout=20);r.raise_for_status();data=r.json();assert isinstance(data,list);return data

def provision():
    for label,identity in identities.items():
        name='Platform07B-Org'+label
        organizations=rows(admin,'/org/organisation.json?organisation.name='+name+'&limit=2')
        if not organizations:form(admin,'/org/organisation/create',{'name':name})
        organizations=rows(admin,'/org/organisation.json?organisation.name='+name+'&limit=2');assert len(organizations)==1
        org=organizations[0];identity['organizationId']=org['id'];identity['realm']=org['pe_id']
        users=rows(admin,'/admin/user.json?user.email='+identity['email']+'&limit=2')
        if not users:
            form(admin,'/admin/user/create',{'first_name':'Synthetic '+label,'last_name':'Integration','email':identity['email'],'password':identity['password'],'password_two':identity['password'],'organisation_id':str(org['id'])})
        users=rows(admin,'/admin/user.json?user.email='+identity['email']+'&limit=2');assert len(users)==1
        identity['userId']=users[0]['id']
        print('Provisioned synthetic organization and non-administrative identity',label)
    fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(identities,stream)

def roles():
    soup=BeautifulSoup(admin.get(base+'/admin/role',timeout=20).text,'html.parser')
    return json.loads(soup.select_one('input[name=cache]')['value'])['cacheLastJson']['data']

if __name__ == '__main__':
    provision()
    sessions={}
    for label,identity in identities.items():
        role='PLATFORM_PEOPLE_'+label
        current=[r for r in roles() if r[2]==role]
        if not current:
            permissions=[[0,c,None,None,7,7,identity['realm'],False] for c in ('pr','dvr','cr','event')]
            form(admin,'/admin/role/create',{'uuid':role,'role':role,'permissions':json.dumps(permissions)})
            current=[r for r in roles() if r[2]==role]
        assert len(current)==1
        path=f"/admin/role/{current[0][0]}/update"
        soup=BeautifulSoup(admin.get(base+path,timeout=20).text,'html.parser')
        permissions=json.loads(soup.select_one('input[name=permissions]')['value'])
        for rule in permissions:
            if rule[1] and not rule[2]:rule[4]=rule[5]=2
        for controller,functions in {'pr':('person','group','group_membership'), 'dvr':('person','case','case_activity'), 'cr':('shelter','shelter_registration')}.items():
            for function in functions:
                if not any(rule[1]==controller and rule[2]==function for rule in permissions):permissions.append([0,controller,function,None,7,7,identity['realm'],False])
        for table in ('pr_person','pr_group','pr_group_membership','dvr_case','dvr_case_activity','dvr_need','cr_shelter','cr_shelter_registration'):
            if not any(rule[3]==table for rule in permissions):permissions.append([0,None,None,table,7,7,identity['realm'],False])
        form(admin,path,{'permissions':json.dumps(permissions)})
        response=admin.post(base+f"/admin/user/{identity['userId']}/roles.json",json={'add':[[int(current[0][0]),identity['realm']]]},timeout=20);response.raise_for_status()
        session=requests.Session();session.auth=(identity['email'],identity['password']);sessions[label]=session
        people=rows(session,'/pr/person.json?person.first_name=Platform07B-'+label+'&limit=2')
        if not people:form(session,'/pr/person/create',{'first_name':'Platform07B-'+label,'last_name':'Synthetic'})
        people=rows(session,'/pr/person.json?person.first_name=Platform07B-'+label+'&limit=2');assert len(people)==1
        identity['personId']=people[0]['id']
        print('Native scoped person creation and read:',label)
    for label,session in sessions.items():
        other=identities['B' if label=='A' else 'A']
        response=session.get(base+f"/pr/person/{other['personId']}.json",timeout=20)
        assert response.status_code in (403,404),('cross-organization read',label,response.status_code)
        response=session.get(base+f"/pr/person/{other['personId']}/update",timeout=20,allow_redirects=False)
        assert response.status_code in (403,404) or response.status_code==303 and response.headers.get('Location','').endswith('/pr/index'),('cross-organization update',label,response.status_code)
        assert not rows(session,'/pr/person.json?person.first_name=Platform07B-'+('B' if label=='A' else 'A')+'&limit=2')
    print('PASS: two native organization realms isolate person lists, details and update access')
    fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(identities,stream)

    statuses=rows(admin,'/dvr/case_status.json?limit=1')
    if not statuses:
        form(admin,'/dvr/case_status/create',{'code':'OPEN','name':'Open','workflow_position':'1','is_default':'on'})
    statuses=rows(admin,'/dvr/case_status.json?limit=1');assert statuses
    status_id=statuses[0]['id']
    for label,session in sessions.items():
        identity=identities[label]
        groups=rows(session,'/pr/group.json?group.name=Platform07B-Family'+label+'&limit=2')
        if not groups:form(session,'/pr/group/create',{'name':'Platform07B-Family'+label,'group_type':'7'})
        groups=rows(session,'/pr/group.json?group.name=Platform07B-Family'+label+'&limit=2');assert len(groups)==1
        identity['familyId']=groups[0]['id']
        cases=rows(session,'/dvr/case.json?case.reference=Platform07B-Case'+label+'&limit=2')
        if not cases:form(session,'/dvr/case/create',{'person_id':str(identity['personId']),'reference':'Platform07B-Case'+label,'organisation_id':str(identity['organizationId']),'status_id':str(status_id)})
        cases=rows(session,'/dvr/case.json?case.reference=Platform07B-Case'+label+'&limit=2');assert len(cases)==1
        identity['caseId']=cases[0]['id']
        shelters=rows(session,'/cr/shelter.json?shelter.name=Platform07B-Shelter'+label+'&limit=2')
        if not shelters:
            existing=rows(admin,'/cr/shelter.json?shelter.name=Platform07B-Shelter'+label+'&limit=2')
            if existing:form(admin,f"/cr/shelter/{existing[0]['id']}/update",{'organisation_id':str(identity['organizationId'])})
            else:form(session,'/cr/shelter/create',{'name':'Platform07B-Shelter'+label,'organisation_id':str(identity['organizationId']),'capacity':'10'})
        shelters=rows(session,'/cr/shelter.json?shelter.name=Platform07B-Shelter'+label+'&limit=2');assert len(shelters)==1
        identity['shelterId']=shelters[0]['id']
        print('Native family, case and shelter persisted:',label)
    fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(identities,stream)
    for label,session in sessions.items():
        other=identities['B' if label=='A' else 'A']
        for controller,resource,key in [('pr','group','familyId'),('dvr','case','caseId'),('cr','shelter','shelterId')]:
            response=session.get(base+f"/{controller}/{resource}/{other[key]}.json",timeout=20)
            assert response.status_code in (403,404),(controller,label,response.status_code)
    print('PASS: native family, case and shelter read isolation')

    for label,session in sessions.items():
        identity=identities[label];other=identities['B' if label=='A' else 'A']
        form(session,f"/pr/person/{identity['personId']}/update",{'last_name':'Synthetic checked'})
        own=rows(session,f"/pr/person/{identity['personId']}.json");assert own[0]['last_name']=='Synthetic checked'
        form(session,'/dvr/case/create',{'person_id':str(identity['personId']),'reference':'Platform07B-Forbidden'+label,'organisation_id':str(other['organizationId']),'status_id':str(status_id)},expected_errors=('organisation_id__error',))
        assert not rows(admin,'/dvr/case.json?case.reference=Platform07B-Forbidden'+label+'&limit=2')
        assert session.get(base+'/dvr/case_status/create',allow_redirects=False,timeout=20).status_code in (303,403)
    print('PASS: own native update, denied foreign-organization creation and denied runtime catalog administration')

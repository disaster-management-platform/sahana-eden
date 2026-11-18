"""Native SUPPLY/INV/REQ integration, using isolated non-admin organization identities."""
import os
os.environ['EDEN_TEST_FLOW']='07c'
from platform_test import admin, base, form, rows, roles, identities, private, provision
import json
from bs4 import BeautifulSoup
import requests

provision()
sessions={}
for label,identity in identities.items():
    role='PLATFORM_RESOURCES_'+label
    current=[r for r in roles() if r[2]==role]
    permissions=[[0,c,None,None,2,2,identity['realm'],False] for c in ('supply','inv','req')]
    for c,functions in {'inv':('warehouse','inv_item','send','recv','track_item','adj','adj_item','adj_close'), 'req':('req','req_item','commit','commit_item')}.items():
        for f in functions:permissions.append([0,c,f,None,7,7,identity['realm'],False])
    for table in ('inv_warehouse','inv_adj','inv_adj_item','inv_inv_item','inv_send','inv_recv','inv_track_item','req_req','req_req_item','req_commit','req_commit_item'):
        permissions.append([0,None,None,table,7,7,identity['realm'],False])
    if not current:
        form(admin,'/admin/role/create',{'uuid':role,'role':role,'permissions':json.dumps(permissions)})
        current=[r for r in roles() if r[2]==role]
    assert len(current)==1
    path=f"/admin/role/{current[0][0]}/update"
    existing=json.loads(BeautifulSoup(admin.get(base+path,timeout=20).text,'html.parser').select_one('input[name=permissions]')['value'])
    existing.extend(rule for rule in permissions if not any(old[1:4]==rule[1:4] for old in existing))
    form(admin,path,{'permissions':json.dumps(existing)})
    response=admin.post(base+f"/admin/user/{identity['userId']}/roles.json",json={'add':[[int(current[0][0]),identity['realm']]]},timeout=20);response.raise_for_status()
    session=requests.Session();session.auth=(identity['email'],identity['password']);sessions[label]=session
    warehouses=rows(session,'/inv/warehouse.json?warehouse.name=Platform07C-Warehouse'+label+'&limit=2')
    if not warehouses:form(session,'/inv/warehouse/create',{'name':'Platform07C-Warehouse'+label,'organisation_id':str(identity['organizationId'])})
    warehouses=rows(session,'/inv/warehouse.json?warehouse.name=Platform07C-Warehouse'+label+'&limit=2');assert len(warehouses)==1
    identity['warehouseId']=warehouses[0]['id']
    print('Native scoped warehouse created and queried:',label)
fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as stream:json.dump(identities,stream)
for label,session in sessions.items():
    other=identities['B' if label=='A' else 'A']
    response=session.get(base+f"/inv/warehouse/{other['warehouseId']}.json",timeout=20)
    assert response.status_code in (403,404),('cross-organization warehouse',label,response.status_code)
    assert not rows(session,'/inv/warehouse.json?warehouse.name=Platform07C-Warehouse'+('B' if label=='A' else 'A')+'&limit=2')
    assert session.get(base+'/supply/item/create',allow_redirects=False,timeout=20).status_code in (303,403)
print('PASS: native warehouse isolation and read-only supply catalog access')


def option(session,path,field,label):
    soup=BeautifulSoup(session.get(base+path,timeout=20).text,'html.parser')
    options=soup.select(f'select[name={field}] option')
    matches=[o['value'] for o in options if label in o.text]
    assert len(matches)==1,(field,label)
    return matches[0]

items=rows(admin,'/supply/item.json?item.name=Platform07C-Water&limit=2')
if not items:form(admin,'/supply/item/create',{'name':'Platform07C-Water','catalog_id':'1','um':'L'})
items=rows(admin,'/supply/item.json?item.name=Platform07C-Water&limit=2');assert len(items)==1
item=items[0]['id']
for label,session in sessions.items():
    identity=identities[label]
    site=option(session,'/inv/adj/create','site_id','Platform07C-Warehouse'+label)
    identity['siteId']=site
    adjustments=rows(session,'/inv/adj.json?adj.site_id='+site+'&limit=2')
    if not adjustments:form(session,'/inv/adj/create',{'site_id':site})
    adjustments=rows(session,'/inv/adj.json?adj.site_id='+site+'&limit=2');assert len(adjustments)==1
    identity['adjustmentId']=adjustments[0]['id']
    requests_=rows(session,'/req/req.json?req.site_id='+site+'&limit=2')
    if not requests_:form(session,'/req/req/create',{'site_id':site,'type':'1','priority':'1','req_ref':'Platform07C-Request'+label})
    requests_=rows(session,'/req/req.json?req.site_id='+site+'&limit=2');assert len(requests_)==1
    identity['requestId']=requests_[0]['id']
    print('Native inventory adjustment and resource request persisted:',label)
fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as stream:json.dump(identities,stream)
packs=rows(admin,f'/supply/item_pack.json?item_pack.item_id={item}&limit=2');assert len(packs)==1
pack=packs[0]['id']
for label,session in sessions.items():
    identity=identities[label]
    adj=identity['adjustmentId'];req=identity['requestId']
    stock=rows(session,f"/inv/inv_item.json?inv_item.site_id={identity['siteId']}&limit=2")
    if not stock:
        lines=rows(session,f'/inv/adj/{adj}/adj_item.json?limit=2')
        if not lines:form(session,f'/inv/adj/{adj}/adj_item/create',{'item_id':str(item),'item_pack_id':str(pack),'new_quantity':'10','new_status':'0','new_owner_org_id':str(identity['organizationId'])})
        response=session.get(base+f'/inv/adj_close/{adj}',timeout=20)
        response.raise_for_status()
        stock=rows(session,f"/inv/inv_item.json?inv_item.site_id={identity['siteId']}&limit=2")
    assert len(stock)==1 and float(stock[0]['quantity'])==10
    identity['stockId']=stock[0]['id']
    lines=rows(session,f'/req/req/{req}/req_item.json?limit=2')
    if not lines:form(session,f'/req/req/{req}/req_item/create',{'item_id':str(item),'item_pack_id':str(pack),'quantity':'2'})
    lines=rows(session,f'/req/req/{req}/req_item.json?limit=2');assert len(lines)==1
    identity['requestItemId']=lines[0]['id']
    commits=rows(session,f'/req/commit.json?commit.req_id={req}&limit=2')
    if not commits:form(session,'/req/commit/create',{'site_id':identity['siteId'],'req_id':str(req)})
    commits=rows(session,f'/req/commit.json?commit.req_id={req}&limit=2');assert len(commits)==1
    identity['commitId']=commits[0]['id']
    print('Native stock quantity and item request persisted; commitment created:',label)
fd=os.open(private,os.O_WRONLY|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as stream:json.dump(identities,stream)
for label,session in sessions.items():
    identity=identities[label];other=identities['B' if label=='A' else 'A']
    commit=identity['commitId']
    lines=rows(session,f'/req/commit/{commit}/commit_item.json?limit=2')
    if not lines:form(session,f'/req/commit/{commit}/commit_item/create',{'req_item_id':str(identity['requestItemId']),'item_pack_id':str(pack),'quantity':'2'})
    lines=rows(session,f'/req/commit/{commit}/commit_item.json?limit=2')
    assert len(lines)==1 and float(lines[0]['quantity'])==2
    for resource,key in [('/inv/inv_item/','stockId'),('/req/req/','requestId'),('/req/commit/','commitId')]:
        response=session.get(base+resource+str(other[key])+'.json',timeout=20)
        assert response.status_code in (403,404),(resource,label,response.status_code)
    form(session,'/req/req/create',{'site_id':other['siteId'],'type':'1','priority':'1','req_ref':'Platform07C-Forbidden'+label},expected_errors=('site_id__error',))
    assert not rows(admin,'/req/req.json?req.req_ref=Platform07C-Forbidden'+label+'&limit=2')
print('PASS: native committed quantities, isolated stock/requests/commitments, denied foreign-site requests')

"""Keep coordination references within the owner's native project and realm."""
from functools import partial

from gluon import current


TABLES = ('org_organisation', 'project_project', 'project_task', 'project_activity', 'event_project')


def references_controller(**attr):
    s3 = current.response.s3
    standard_prep = s3.prep

    def prep(r):
        if current.request.controller == "dvr" and current.request.function == "group_membership":
            viewing = r.get_vars.get("viewing")
            if viewing:
                parts = viewing.split(".", 1)
                if len(parts) != 2 or parts[0] != "pr_person" or not parts[1].isdigit():
                    r.error(400, current.T("Invalid request"))
                permission = "read" if r.http == "GET" else "update"
                if not current.auth.s3_has_permission(permission, "pr_person", record_id=int(parts[1])):
                    r.unauthorised()
        result = standard_prep(r) if callable(standard_prep) else standard_prep
        if result is not False and r.representation == 'json' and r.tablename in ('pr_person', 'pr_group'):
            fields = list(r.resource.get_config('list_fields') or ['id'])
            if 'pe_id' not in fields:
                fields.append('pe_id')
            r.resource.configure(list_fields=fields)
        return result

    s3.prep = prep
    return attr


def customise(r, tablename):
    # Register once per request, including nested project components in native imports.
    if current.response.s3.get('platform_coordination_validation'):
        return
    current.response.s3.platform_coordination_validation = True
    for table in TABLES:
        current.s3db.add_custom_callback(table, 'onvalidation', partial(validate, tablename=table))


def validate(form, tablename):
    auth, db, s3db = current.auth, current.db, current.s3db
    if auth.s3_has_role('ADMIN'):
        return
    user = auth.user
    values = form.vars
    table = s3db.table(tablename)
    record_id = values.get('id') or getattr(getattr(form, 'record', None), 'id', None)
    previous = db((table.id == record_id) & (table.deleted == False)).select(table.ALL, limitby=(0, 1)).first() if record_id else None

    def field(name):
        if name in values:
            return values[name]
        return previous[name] if previous and name in previous else None

    def denied(name):
        form.errors[name] = current.T('Not permitted')

    def own_org(organisation):
        return bool(user and user.organisation_id and organisation and str(organisation) == str(user.organisation_id))

    def permitted(resource, identity, permission='read'):
        if not identity or not str(identity).isdigit():
            return False
        c, f = resource.split('_', 1)
        return auth.s3_has_permission(permission, resource, record_id=int(identity), c=c, f=f)

    if tablename == 'org_organisation':
        if previous:
            creator = auth.s3_has_role('PLATFORM_ORG_CREATOR')
            allowed = bool(user and previous.owned_by_user == user.id) if creator else own_org(previous.id)
            if not allowed:
                denied('name')
        return

    if tablename == 'project_project':
        owner = field('organisation_id')
        if not own_org(owner) or previous and str(previous.organisation_id) != str(owner):
            denied('organisation_id')
        return

    project = field('project_id')
    ptable = s3db.project_project
    owner = db((ptable.id == project) & (ptable.deleted == False)).select(ptable.organisation_id, limitby=(0, 1)).first() if project else None
    if not owner or not own_org(owner.organisation_id) or not permitted('project_project', project):
        denied('project_id')
        return
    if previous and str(previous.project_id) != str(project):
        denied('project_id')
        return

    def personnel(person):
        if not person or not permitted('pr_person', person):
            return False
        htable = s3db.hrm_human_resource
        return db((htable.deleted == False) & (htable.person_id == person) &
                  (htable.organisation_id == user.organisation_id)).select(htable.id, limitby=(0, 1)).first() is not None

    if tablename == 'project_task':
        activity = field('activity_id')
        if activity:
            atable = s3db.project_activity
            match = db((atable.id == activity) & (atable.deleted == False) & (atable.project_id == project)).select(atable.id, limitby=(0, 1)).first()
            if not match or not permitted('project_activity', activity):
                denied('activity_id')
        assignee = field('pe_id')
        if assignee:
            pentity = s3db.pr_pentity
            entity = db((pentity.pe_id == assignee) & (pentity.deleted == False)).select(pentity.instance_type, limitby=(0, 1)).first()
            allowed = False
            if entity and entity.instance_type in ('pr_person', 'pr_group', 'org_organisation'):
                resource = s3db.table(entity.instance_type)
                row = db((resource.pe_id == assignee) & (resource.deleted == False)).select(resource.ALL, limitby=(0, 1)).first()
                if row and permitted(entity.instance_type, row.id):
                    if entity.instance_type == 'pr_person':
                        allowed = personnel(row.id)
                    elif entity.instance_type == 'org_organisation':
                        allowed = own_org(row.id)
                    else:
                        realm = s3db.pr_get_pe_id('org_organisation', user.organisation_id)
                        allowed = bool(realm and row.realm_entity == realm and row.group_type == 3)
            if not allowed:
                denied('pe_id')
    elif tablename == 'project_activity':
        contact = field('person_id')
        if contact and not personnel(contact):
            denied('person_id')
    elif tablename == 'event_project':
        event = field('event_id')
        etable = s3db.event_event
        row = db((etable.id == event) & (etable.deleted == False)).select(etable.realm_entity, limitby=(0, 1)).first() if event else None
        realm = s3db.pr_get_pe_id('org_organisation', user.organisation_id)
        if not row or not realm or row.realm_entity != realm or not permitted('event_event', event):
            denied('event_id')

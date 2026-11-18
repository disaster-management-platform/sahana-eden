from functools import partial
from gluon import current
from gluon.storage import Storage
from templates.default.config import config as default_config


def config(settings):
    default_config(settings)
    settings.modules["pr"].access = None
    settings.security.policy = 7
    settings.cr.shelter_registration = True
    for name, title in (("dvr", "Beneficiary Registry"),
                        ("cr", "Shelters"),
                        ("event", "Events")):
        settings.modules[name] = Storage(name_nice=current.T(title), module_type=10)
    settings.auth.realm_entity = realm_entity
    for resource in ("supply_item", "supply_catalog", "supply_item_pack", "supply_item_category"):
        setattr(settings, "customise_" + resource + "_resource", catalog_resource)
    for resource in ("dvr_case", "cr_shelter", "inv_warehouse", "inv_adj", "req_req", "req_commit"):
        setattr(settings, "customise_" + resource + "_resource", organisation_resource)



def realm_entity(table, record):
    if table._tablename in ("pr_person", "pr_group", "cr_shelter", "inv_warehouse", "inv_adj", "inv_adj_item", "inv_inv_item", "inv_send", "inv_recv", "inv_track_item", "req_req", "req_req_item", "req_commit", "req_commit_item"):
        user = current.auth.user
        if user and user.organisation_id:
            return current.s3db.pr_get_pe_id("org_organisation", user.organisation_id)
    return 0


def organisation_resource(r, tablename):
    current.s3db.add_custom_callback(tablename, "onvalidation", organisation_validation)
    current.s3db.add_custom_callback(tablename, "onaccept", partial(organisation_owner, tablename=tablename))


def organisation_validation(form):
    auth = current.auth
    user = auth.user
    if user and not auth.s3_has_role("ADMIN"):
        organisation = form.vars.get("organisation_id")
        if organisation and str(organisation) != str(user.organisation_id):
            form.errors.organisation_id = current.T("Not permitted")
        site = form.vars.get("site_id")
        if site and int(site) not in auth.permitted_facilities(redirect_on_error=False):
            form.errors.site_id = current.T("Not permitted")


def organisation_owner(form, tablename):
    organisation = form.vars.get("organisation_id")
    if organisation:
        current.auth.set_realm_entity(tablename, form.vars.id,
                                     entity=("org_organisation", organisation),
                                     force_update=True)


def catalog_resource(r, tablename):
    if not current.auth.s3_has_roles(("ADMIN", "LOGS_ADMIN")):
        current.s3db.configure(tablename, insertable=False, editable=False, deletable=False)
        if r.http != "GET" or r.method in ("create", "update", "delete"):
            r.unauthorised()

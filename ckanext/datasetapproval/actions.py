import logging
import ckan.authz as authz

from ckan.plugins import toolkit as tk
from ckanext.datasetapproval import mailer
from ckanext.scheming.logic import scheming_dataset_schema_show
from ckan import model

log = logging.getLogger()


def is_unowned_dataset(owner_org):
    return (
        not owner_org
        and authz.check_config_permission("create_dataset_if_not_in_organization")
        and authz.check_config_permission("create_unowned_dataset")
    )


def is_user_editor_of_org(org_id, user_id):
    capacity = authz.users_role_for_group_or_org(org_id, user_id)
    return capacity == "editor"


def is_user_admin_of_org(org_id, user_id):
    capacity = authz.users_role_for_group_or_org(org_id, user_id)
    return capacity == "admin"


def publishing_check(context, data_dict):
    user_id = (
        tk.current_user.id
        if tk.current_user and not tk.current_user.is_anonymous
        else None
    )
    org_id = data_dict.get("owner_org")
    is_active = data_dict.get("state") in ["active", "publish", None, False]

    is_user_editor = is_user_editor_of_org(org_id, user_id)
    is_user_admin = is_user_admin_of_org(org_id, user_id)
    is_sysadmin = hasattr(tk.current_user, "sysadmin") and tk.current_user.sysadmin

    if (is_user_editor or is_unowned_dataset(org_id)) and is_active:
        mailer.mail_package_review_request_to_admins(context, data_dict)
        data_dict["state"] = "inreview"

    # if sysadmin is updating the dataset and it's already in review state
    # then it should remain in review state
    _action_review = context.get("_action_review", False)
    if not _action_review and data_dict.get("id"):
        old_data_dict = tk.get_action("package_show")(
            context, {"id": data_dict.get("id")}
        )
        if (is_user_admin or is_sysadmin) and old_data_dict.get("state") == "inreview":
            data_dict["state"] = old_data_dict.get("state")
    return data_dict

def get_dataset_schema():
    context = {
        'model': model,
        'session': model.Session,
        'user': None,
        'ignore_auth': True
    }
    
    data_dict = {
        'type': 'dataset',
        'expanded': True
    }

    try:
        schema_data = scheming_dataset_schema_show(context, data_dict)
        return schema_data
    except Exception as e:
        print(f"Error retrieving dataset schema: {e}")
        return None

def clean_dictionary(data_dict):
    schema = get_dataset_schema()
    keys = []

    for field_info in schema.get('dataset_fields', []):
        if "repeating_subfields" in field_info.keys():
            keys.append(field_info['field_name'])
    
    cleaned_dict = dict(data_dict)

    for key in keys:
        if key in cleaned_dict:
            remove_key = True
            for entry in cleaned_dict[key]:
                for value in entry.values():
                    if value != "":
                        remove_key = False
                        break
            if remove_key:
                del cleaned_dict[key]

    return cleaned_dict

@tk.chained_action
def package_create(up_func, context, data_dict):
    data_dict = clean_dictionary(data_dict)
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_update(up_func, context, data_dict):
    data_dict = clean_dictionary(data_dict)
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_patch(up_func, context, data_dict):
    data_dict = clean_dictionary(data_dict)
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


def dataset_review(context, data_dict):
    id = data_dict.get("dataset_id")
    action = data_dict.get("action")
    try:
        tk.check_access("dataset_review", context, {"dataset_id": id})
    except tk.NotAuthorized and tk.ObjectNotFound:
        raise tk.NotAuthorized(tk._("User not authorized to review dataset"))

    states = {"reject": "rejected", "approve": "active"}
    mailer.mail_package_approve_reject_notification_to_editors(id, action)
    try:
        tk.get_action("package_patch")(
            {
                **context,
                "_action_review": True,
            },
            {"id": id, "state": states[action]},
        )
    except Exception as e:
        raise tk.ValidationError(str(e))

    return {"success": True}

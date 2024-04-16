import logging
import ckan.authz as authz

from ckan.plugins import toolkit as tk
from ckanext.datasetapproval import mailer

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
    if context.get("allow_publish") or data_dict.get("state") == "inreview":
        return data_dict
    data_dict["state"] = "draft"
    return data_dict


@tk.chained_action
def package_create(up_func, context, data_dict):
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_update(up_func, context, data_dict):
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_patch(up_func, context, data_dict):
    publishing_check(context, data_dict)
    result = up_func(context, data_dict)
    return result


def publish_dataset(context, id):
    tk.check_access("package_update", context, {"id": id})
    data_dict = tk.get_action("package_show")(context, {"id": id})
    user_id = (
        tk.current_user.id
        if tk.current_user and not tk.current_user.is_anonymous
        else None
    )
    org_id = data_dict.get("owner_org")
    is_user_admin = is_user_admin_of_org(org_id, user_id)
    is_sysadmin = hasattr(tk.current_user, "sysadmin") and tk.current_user.sysadmin

    if is_user_admin or is_sysadmin:
        data_dict["state"] = "active"
    else:
        mailer.mail_package_review_request_to_admins(context, data_dict)
        data_dict["state"] = "inreview"
    try:
        result = tk.get_action("package_update")(
            {**context, "allow_publish": True}, data_dict
        )
    except Exception as e:
        raise tk.ValidationError(str(e))

    return {"success": True, "package": result}


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
                "allow_publish": True,
            },
            {"id": id, "state": states[action]},
        )
    except Exception as e:
        raise tk.ValidationError(str(e))

    return {"success": True}

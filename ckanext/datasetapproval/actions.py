import logging
import ckan.authz as authz
from datetime import datetime

from ckan.plugins import toolkit as tk
from ckanext.datasetapproval import mailer
from ckan import logic

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
    if context.get("allow_publish") or data_dict.get("state") == "inreview":
        return data_dict
    data_dict["state"] = "draft"
    return data_dict


def _add_or_update_org(context, package_dict):
    # Add the package to the org group
    if "institution" in package_dict and len(package_dict["institution"]) > 0:
        old_package_dict = tk.get_action("package_show")(
            context, {"id": package_dict.get("id")}
        )

        package_groups = [{"name": package_dict["institution"]}]
        if old_package_dict:
            groups = old_package_dict.get("groups", [])
            orgs_names = []
            non_orgs_names = []

            # This will ensure only one org can be added per
            # dataset and other non-org groups are kept as
            # they are
            if len(groups) > 0:
                groups_names = list(map(lambda g: g.get("name"), groups))
                orgs = tk.get_action("group_list")(
                    context,
                    {"all_fields": True, "type": "institution", "groups": groups_names},
                )
                orgs_names = list(map(lambda g: g.get("name"), orgs))
                non_orgs_names = list(set(groups_names) - set(orgs_names))
                package_groups.extend([{"name": name} for name in non_orgs_names])

        package_dict["groups"] = package_groups

    return package_dict


def get_dataset_schema():
    context = {
        "model": model,
        "session": model.Session,
        "user": None,
        "ignore_auth": True,
    }

    data_dict = {"type": "dataset", "expanded": True}

    try:
        schema_data = scheming_dataset_schema_show(context, data_dict)
        return schema_data
    except Exception as e:
        print(f"Error retrieving dataset schema: {e}")
        return None


def clean_dictionary(data_dict):
    schema = get_dataset_schema()
    keys = []

    for field_info in schema.get("dataset_fields", []):
        if "repeating_subfields" in field_info.keys():
            keys.append(field_info["field_name"])

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
    data_dict = _add_or_update_org(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_update(up_func, context, data_dict):
    data_dict = clean_dictionary(data_dict)
    publishing_check(context, data_dict)
    data_dict = _add_or_update_org(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
def package_patch(up_func, context, data_dict):
    data_dict = clean_dictionary(data_dict)
    publishing_check(context, data_dict)
    data_dict = _add_or_update_org(context, data_dict)
    result = up_func(context, data_dict)
    return result


@tk.chained_action
@tk.side_effect_free
def user_show(up_func, context, data_dict):
    final_result = up_func(context, data_dict)

    user_name = data_dict.get("id")
    if user_name:
        # In order to get "plugin_extras", it's necessary to
        # request "user_show" as a sysadmin and ignore_auth
        # doesn't work, so accessing the model directly.
        user_obj = model.User.get(user_name)

        if user_obj is not None:
            user_has_review_permission = False

            plugin_extras = user_obj.plugin_extras
            if plugin_extras:
                user_has_review_permission = plugin_extras.get(
                    "user_has_review_permission", False
                )

            user_is_sysadmin = user_obj.sysadmin

            # User has review permission if:
            # 1) The user is a sysadmin
            # 2) The user has "user_has_review_permission=True" in plugin_extras
            final_result["user_has_review_permission"] = (
                user_has_review_permission or user_is_sysadmin
            )

    return final_result


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
        data_dict["import_done"] = True
        data_dict["cron"] = {
            "state": "queued",
            "message": "",
            "submitted_date": datetime.now().isoformat(),
            "completed_date": "",
        }
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
        pkg_dict = {
            "id": id,
            "state": states[action],
        }
        if action == "approve":
            pkg_dict.update(
                {
                    "import_done": True,
                    "cron": {
                        "state": "queued",
                        "message": "",
                        "submitted_date": datetime.now().isoformat(),
                        "completed_date": "",
                    },
                }
            )
        tk.get_action("package_patch")(
            {
                **context,
                "allow_publish": True,
            },
            pkg_dict,
        )
    except Exception as e:
        raise tk.ValidationError(str(e))

    return {"success": True}


def _org_autocomplete(context, data_dict):
    q = data_dict["q"]
    limit = data_dict.get("limit", 20)
    model = context["model"]

    query = model.Group.search_by_name_or_title(
        q, group_type="institution", is_org=False, limit=limit
    )

    org_list = []
    for group in query.all():
        result_dict = {}
        for k in ["id", "name", "title"]:
            result_dict[k] = getattr(group, k)
        org_list.append(result_dict)

    return org_list


@tk.side_effect_free
def org_autocomplete(context, data_dict):
    logic.check_access("group_autocomplete", context, data_dict)
    return _org_autocomplete(context, data_dict)

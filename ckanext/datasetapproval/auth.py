import logging
from ckan.plugins import toolkit as tk
import ckan.authz as authz
from ckan.logic.auth.update import package_update as core_package_update
from ckan import model

log = logging.getLogger(__name__)


def dataset_review(context, data_dict=None):
    user = tk.current_user if tk.current_user else None
    if user and not user.is_anonymous:
        user_has_review_permission = False

        plugin_extras = user.plugin_extras
        if plugin_extras:
            user_has_review_permission = plugin_extras.get(
                "user_has_review_permission", False
            )

        if user_has_review_permission or user.sysadmin:
            return {"success": True}
        elif data_dict is None or "dataset_id" not in data_dict:
            # If the user is not sysadmin and doesn't have the review permission
            # and no dataset id was provided
            return {"success": False, "message": "User doesn't have review permission."}
    else:
        return {"success": False, "message": "Anonymous cannot review a dataset"}

    dataset_dict = tk.get_action("package_show")(
        context, {"id": data_dict.get("dataset_id")}
    )
    owner_org = dataset_dict.get("owner_org")

    capacity = authz.users_role_for_group_or_org(owner_org, user.id)
    is_org_admin = capacity == "admin"
    if is_org_admin:
        return {"success": True}
    else:
        return {
            "success": False,
            "msg": "User does not have permission to review dataset",
        }


@tk.auth_sysadmins_check
@tk.auth_allow_anonymous_access
def package_update(context, data_dict):

    current_user = tk.current_user
    is_sysadmin = current_user.is_anonymous or current_user.sysadmin
    package_id = data_dict.get("id")
    previous_data_dict = tk.get_action("package_show")(context, {"id": package_id})
    creator_user_id = previous_data_dict.get("creator_user_id")
    current_state = previous_data_dict.get("state")

    user_has_review_permission = dataset_review(context, {"dataset_id": package_id})[
        "success"
    ]

    def _is_sysadmin_and_dataset_active():
        """Check if the user is a sysadmin and the dataset is active"""
        return is_sysadmin and current_state == "active"

    def _is_dataset_under_review_or_active():
        """Check if the dataset is under review and the user is the creator"""
        return (
            current_state in ["inreview", "active"]
            and creator_user_id == current_user.id
            and not user_has_review_permission
        )

    def _is_creator_or_has_review_permission():
        """Check if the user is the creator or has review permission"""
        return creator_user_id == current_user.id or user_has_review_permission

    def _is_collaborator_with_permission():
        """Check if the user is a collaborator with permission to update the dataset"""
        package_collaborators = tk.get_action("package_collaborator_list")
        privileged_context = {"ignore_auth": True, "model": model}
        collaborators_list = package_collaborators(
            privileged_context, {"id": package_id}
        )

        for collaborator in collaborators_list:
            if collaborator.get("user_id") == current_user.id and collaborator.get(
                "capacity"
            ) in ["admin", "editor"]:
                return True
        return False

    if _is_sysadmin_and_dataset_active():
        return {"success": False, "msg": "Not authorized to update dataset"}

    if _is_dataset_under_review_or_active():
        return {
            "success": False,
            "msg": "User cannot update dataset while it is in review",
        }

    if _is_creator_or_has_review_permission():
        return {"success": True}

    if _is_collaborator_with_permission():
        return {"success": True}

    return {"success": False, "msg": "User not allowed to update this dataset"}

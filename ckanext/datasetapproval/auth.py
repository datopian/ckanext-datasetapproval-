import logging
from ckan.plugins import toolkit as tk
import ckan.authz as authz
from ckan.logic.auth.update import package_update as core_package_update
from ckan import model

log = logging.getLogger(__name__)


def dataset_review(context, data_dict):
    dataset_dict = tk.get_action("package_show")(
        context, {"id": data_dict.get("dataset_id")}
    )
    owner_org = dataset_dict.get("owner_org")
    user_id = tk.current_user.id if tk.current_user else None
    capacity = authz.users_role_for_group_or_org(owner_org, user_id)
    is_org_admin = capacity == "admin"
    if is_org_admin or tk.current_user.sysadmin:
        return {"success": True}
    else:
        return {
            "success": False,
            "msg": "User does not have permission to review dataset",
        }

@tk.auth_allow_anonymous_access
def package_update(context, data_dict):
    # This check doesn't allow to edit dataset
    # which is in alredy in review state
    if data_dict:
        current_user = tk.current_user
        package_id = data_dict.get("id")
        previous_data_dict = tk.get_action("package_show")(
            context, {"id": data_dict.get("id")}
        )
        creator_user_id = previous_data_dict.get("creator_user_id")

        if (
            previous_data_dict.get("state") == "inreview"
            and previous_data_dict.get("creator_user_id") == tk.current_user.id
        ):
            return {
                "success": False,
                "msg": "User cannot update dataset while it is in review",
            }

        if not current_user.is_anonymous and not current_user.sysadmin:
            # Creator can always edit
            if creator_user_id == current_user.id:
                return {
                    "success": True
                }

            # Users with review permission can always edit
            plugin_extras = current_user.plugin_extras
            if plugin_extras:
                user_has_review_permission = plugin_extras.get("user_has_review_permission", False)
                if user_has_review_permission:
                    return {
                        "success": True
                    }

            # By default, if unowned datasets and create_dataset_if_not_in_organization
            # are enabled, any user can update a dataset. We have to override that.
            package_collaborators = tk.get_action("package_collaborator_list")
            privileged_context = {
                "ignore_auth": True,
                "model": model
            }
            collaborators_list = package_collaborators(privileged_context,
                                                       {"id": package_id})

            for collaborator in collaborators_list:
                collaborator_id = collaborator.get("user_id")
                collaborator_capacity = collaborator.get("capacity")

                # If user is collaborator with capacity admin or editor,
                # update is allowed
                if collaborator_id == current_user.id \
                        and collaborator_capacity in ["admin", "editor"]:

                    return {
                        "success": True
                    }

            # If it got to that line, user doesn't have permission to
            # update datasets
            return {
                "success": False,
                "msg": "User not allowed to update this dataset",
            }

    return core_package_update(context, data_dict)

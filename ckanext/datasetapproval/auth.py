import logging
from ckan.plugins import toolkit as tk
import ckan.authz as authz
import ckanext.datasetapproval.helpers as h
from ckan.logic.auth.update import package_update as core_package_update

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
    if data_dict:
        previous_data_dict = tk.get_action("package_show")(
                context, {"id": data_dict.get("id")}
                )

        user_dataset_permissions = h.get_dataset_current_user_permissions(previous_data_dict)

        # This check doesn't allow to edit dataset
        # which is in alredy in review state
        if (
            previous_data_dict.get("state") == "inreview"
            and (
                user_dataset_permissions.get("is_collaborator", False)
                or user_dataset_permissions.get("is_creator", False)
            )
        ):
            return {
                "success": False,
                "msg": "User cannot update dataset while it is in review",
            }

        # In order to be able to edit a dataset, user must be
        # a sysadmin, owner or collaborator
        # TODO: implement archive manager
        response = { 
            "success": user_dataset_permissions.get("can_write", False)
        }

        if not response.get("success"):
            response["msg"] = "User is not authorized to edit dataset"

        return response

    return core_package_update(context, data_dict)

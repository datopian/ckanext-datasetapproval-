import logging
from ckan.plugins import toolkit as tk
import ckan.authz as authz

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

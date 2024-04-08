from ckan.lib.plugins import get_permission_labels
from ckan.logic.auth import get_package_object
from ckan import model
import logging

from ckan.plugins import toolkit as tk
import ckan.authz as authz


log = logging.getLogger()


def is_dataset_owner(data_dict, user_id):
    """
    Check if the dataset belongs to the user
    """
    try:
        dataset = tk.get_action("package_show")(data_dict={"id": data_dict.get("id")})
        return dataset["creator_user_id"] == user_id
    except Exception as e:
        return False


def get_dataset_user_permissions(dataset_dict, user_obj):
    context = {
        "model": model,
        "session": model.Session,
        "user": tk.current_user.name,
        "auth_user_obj": tk.current_user,
        "save": "save" in tk.request.form,
    }
    package = get_package_object(context, dataset_dict)

    permission_labels = get_permission_labels()
    user_labels = permission_labels.get_user_dataset_labels(user_obj)
    dataset_labels = permission_labels.get_dataset_labels(package)

    dataset_creator_labels = list(filter(
        lambda label: label.startswith("creator-"),
        dataset_labels))

    dataset_collaborator_labels = list(filter(
        lambda label: label.startswith("collaborator-"),
        dataset_labels))

    is_creator = False
    if len(dataset_creator_labels) > 0:
        is_creator = dataset_creator_labels.pop() in user_labels

    is_collaborator = False
    if len(dataset_collaborator_labels) > 0:
        is_collaborator = dataset_collaborator_labels.pop() in user_labels

    is_sysadmin = user_obj.sysadmin if not user_obj.is_anonymous else False

    roles = {
            "is_creator": is_creator,
            "is_collaborator": is_collaborator,
            "is_sysadmin": is_sysadmin,
            # TODO: is_archive_manager or smth
            "can_read": is_creator or is_collaborator or is_sysadmin or package.private is False,
            # NOTE: can_write is currently unused, default permissions 
            # seem to suffice
            "can_write": is_creator or is_collaborator or is_sysadmin
            }

    return roles


def get_dataset_current_user_permissions(dataset_dict):
    return get_dataset_user_permissions(dataset_dict, tk.current_user)


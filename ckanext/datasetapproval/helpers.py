import logging

from ckan.plugins import toolkit as tk
from ckan import model


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


def is_dataset_collaborator(data_dict, user_id):
    try:
        context = {"ignore_auth": True, "model": model}
        collaborators = tk.get_action("package_collaborator_list")(
            context, data_dict={"id": data_dict.get("id")}
        )

        for collaborator in collaborators:
            collaborator_id = collaborator.get("user_id")
            if user_id == collaborator_id:
                return True

        return False
    except Exception as e:
        log.error(e)
        return False

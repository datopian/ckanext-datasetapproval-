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

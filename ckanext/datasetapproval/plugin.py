# Standard library imports
import logging
import json

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckan.authz as authz

from ckanext.datasetapproval import auth, actions, helpers, validation
from ckan.lib.plugins import DefaultPermissionLabels

from ckanext.datasetapproval import views
from ckanext.datasetapproval.actions import get_dataset_schema
from ckan import logic

log = logging.getLogger(__name__)


class DatasetapprovalPlugin(
    plugins.SingletonPlugin, DefaultPermissionLabels, tk.DefaultDatasetForm
):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IPermissionLabels, inherit=True)
    plugins.implements(plugins.IPackageController, inherit=True)

    # IPackageController
    def before_dataset_index(self, data_dict):
        schema = get_dataset_schema()
        field_names = []

        for field_info in schema.get("dataset_fields", []):
            if "repeating_subfields" in field_info.keys():
                field_names.append(field_info["field_name"])

        for field_name in field_names:
            if field_name in data_dict and data_dict[field_name] is not None:
                data_dict[field_name] = json.dumps(data_dict[field_name])

        return data_dict

    # IConfigurer
    def update_config(self, config_):
        tk.add_template_directory(config_, "templates")
        tk.add_public_directory(config_, "public")
        tk.add_resource("assets", "datasetapproval")

    # IActions
    def get_actions(self):
        return {
            "package_create": actions.package_create,
            "package_update": actions.package_update,
            "dataset_review": actions.dataset_review,
            "publish_dataset": actions.publish_dataset,
            "org_autocomplete": actions.org_autocomplete,
            "user_show": actions.user_show,
        }

    # ITemplateHelpers
    def get_helpers(self):
        return {
            "is_dataset_owner": helpers.is_dataset_owner,
            "is_dataset_collaborator": helpers.is_dataset_collaborator,
        }

    # IBlueprint
    def get_blueprint(self):
        blueprints = [
            views.dataset.registred_views(),
            views.review.registred_views(),
            views.user.registred_views(),
            views.admin.registred_views(),
        ]
        blueprints.extend(views.resource.registred_views())
        return blueprints

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            "dataset_review": auth.dataset_review,
            "package_update": auth.package_update,
        }

    def get_user_dataset_labels(self, user_obj):
        labels = super(DatasetapprovalPlugin, self).get_user_dataset_labels(user_obj)

        user_has_review_permission = False
        if user_obj and not user_obj.is_anonymous:
            plugin_extras = user_obj.plugin_extras
            if plugin_extras:
                user_has_review_permission = plugin_extras.get(
                    "user_has_review_permission", False
                )

            if user_has_review_permission:
                labels.append("review-permission")

        return labels

    def get_dataset_labels(self, dataset_obj):
        labels = super(DatasetapprovalPlugin, self).get_dataset_labels(dataset_obj)

        labels.append("review-permission")

        user_id = None
        if tk.current_user and tk.current_user.is_authenticated:
            user_id = tk.c.userobj.id

        # TODO: the code below likely can be removed
        if dataset_obj.owner_org:
            capacity = authz.users_role_for_group_or_org(dataset_obj.owner_org, user_id)
            is_org_admin = capacity == "admin"
            # Editor shouldn't be able to collaborate on a dataset
            if (
                dataset_obj.creator_user_id != user_id
                and dataset_obj.state not in ["active"]
                and not is_org_admin
            ):
                return []

        return labels

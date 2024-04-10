# Standard library imports
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckan.authz as authz

from ckanext.datasetapproval import auth, actions, helpers, validation
from ckan.lib.plugins import DefaultPermissionLabels

from ckanext.datasetapproval import views

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
            "package_patch": actions.package_patch,
            "dataset_review": actions.dataset_review,
            "org_autocomplete": actions.org_autocomplete
        }

    # ITemplateHelpers
    def get_helpers(self):
        return {
            "is_dataset_owner": helpers.is_dataset_owner,
            "get_dataset_current_user_permissions": helpers.get_dataset_current_user_permissions
        }

    # IBlueprint
    def get_blueprint(self):
        blueprints = [views.dataset.registred_views(), views.review.registred_views()]
        blueprints.extend(views.resource.registred_views())
        return blueprints

    # IAuthFunctions
    def get_auth_functions(self):
        return {
            "dataset_review": auth.dataset_review,
            "package_update": auth.package_update,
        }

    def get_dataset_labels(self, dataset_obj):
        # Override CKAN core
        labels = []
        if dataset_obj.state == u'active' and not dataset_obj.private:
            labels.append(u'public')

        if authz.check_config_permission('allow_dataset_collaborators'):
            # Add a generic label for all this dataset collaborators
            labels.append(u'collaborator-%s' % dataset_obj.id)
        else:
            labels = []

        if dataset_obj.owner_org:
            labels.append(u'member-%s' % dataset_obj.owner_org)
        else:
            labels.append(u'creator-%s' % dataset_obj.creator_user_id)

        # End of override

        # user_id = None
        # if tk.current_user and tk.current_user.is_authenticated:
        #     user_id = tk.c.userobj.id
        #
        # capacity = authz.users_role_for_group_or_org(dataset_obj.owner_org, user_id)
        # is_org_admin = capacity == "admin"
        # # Editor shouldn't be able to collaborate on a dataset
        # if dataset_obj.creator_user_id != user_id and dataset_obj.get("state") not in [
        #     "active"
        # ] and not is_org_admin:
        #     return []
        return labels

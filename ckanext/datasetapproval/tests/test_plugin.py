# encoding: utf-8


import pytest

from ckan.tests import factories, helpers
from ckan.lib.helpers import url_for
from ckan.logic.action.get import package_show as core_package_show
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

import logging

log = logging.getLogger(__name__)


@pytest.mark.usefixtures("non_clean_db")
@pytest.mark.ckan_config("ckan.auth.allow_dataset_collaborators", True)
class TestDatasetCreate(object):
    def setup_org_and_users(self, app, org_name, user_roles):
        sysadmin = factories.User(sysadmin=True)

        context = {
            "user": sysadmin["name"],
            "return_id_only": True,
        }
        org = helpers.call_action(
            "organization_create",
            context=context,
            name=org_name,
            title="Test Org",
            description="Test Org Description",
        )

        users = {}
        for user_role in user_roles:
            user = factories.User()
            helpers.call_action(
                "organization_member_create",
                id=org,
                username=user["name"],
                role=user_role,
            )
            if user_role not in users:
                users[user_role] = []
            users[user_role].append(user)

        return org, users, sysadmin

    def test_other_member_or_anon_user_cannot_view_draft_dataset(self, app):
        org, users, sysadmin = self.setup_org_and_users(
            app, "test-org", ["editor", "member"]
        )
        dataset = factories.Dataset(state="draft", owner_org=org)

        # When anonymous user tries to access the dataset
        response_for_anonymous = app.get(
            url_for("dataset.read", id=dataset["name"]), status=404
        )

        member = users["member"][0]
        token = factories.APIToken(user=member["name"])
        env = {"Authorization": token["token"].decode("utf-8")}

        # When member user tries to access the dataset
        response_for_member_user = app.get(
            url_for("dataset.read", id=dataset["name"]), extra_environ=env, status=404
        )
        assert response_for_anonymous.status_code == 404
        assert response_for_member_user.status_code == 404

    def test_other_editor_cannot_edit_draft_dataset_created_by_others(self, app):
        org, users, sysadmin = self.setup_org_and_users(
            app, "test-org-2", ["editor", "editor"]
        )
        dataset = factories.Dataset(
            state="draft", owner_org=org, user=users["editor"][0]
        )
        second_editor = users["editor"][1]
        token = factories.APIToken(user=second_editor["name"])
        env = {"Authorization": token["token"].decode("utf-8")}

        # When another editor tries to edit the dataset expect 403
        response = app.get(
            url_for("dataset.edit", id=dataset["name"]), extra_environ=env, status=404
        )

        assert response.status_code == 404

    def test_editor_can_edit_draft_dataset_own_dataset(self, app):
        org, users, sysadmin = self.setup_org_and_users(app, "test-org-3", ["editor"])
        dataset = factories.Dataset(
            state="draft", owner_org=org, user=users["editor"][0]
        )

        token = factories.APIToken(user=users["editor"][0]["name"])
        env = {"Authorization": token["token"].decode("utf-8")}

        # When editor tries to edit the dataset expect 200
        response = app.get(
            url_for("dataset.edit", id=dataset["name"]), extra_environ=env, status=200
        )

        assert response.status_code == 200

    def test_sysadmin_can_access_draft_dataset(self, app):
        org, users, sysadmin = self.setup_org_and_users(app, "test-org-4", ["editor"])
        dataset = factories.Dataset(
            state="draft", owner_org=org, user=users["editor"][0]
        )

        token = factories.APIToken(user=sysadmin["name"])
        env = {"Authorization": token["token"].decode("utf-8")}

        # When sysadmin tries to access the dataset
        response = app.get(
            url_for("dataset.read", id=dataset["name"]), extra_environ=env, status=200
        )

        assert response.status_code == 200

    def test_organization_admins_can_access_edit_draft_dataset(self, app):
        org, users, sysadmin = self.setup_org_and_users(
            app, "test-org-5", ["editor", "admin"]
        )
        dataset = factories.Dataset(
            state="draft", owner_org=org, user=users["editor"][0]
        )

        token = factories.APIToken(user=users["admin"][0]["name"])
        env = {"Authorization": token["token"].decode("utf-8")}

        # When organization admin tries to access the dataset
        response = app.get(
            url_for("dataset.edit", id=dataset["name"]), extra_environ=env, status=200
        )

        assert response.status_code == 200

# encoding: utf-8
import logging

from flask import Blueprint
from ckan.views.user import (
    EditView as BaseEditView,
)
from ckan import logic
import ckan.lib.navl.dictization_functions as dictization_functions
from ckan.common import (
    _,
    request,
    current_user,
)
import ckan.lib.base as base
from ckan.plugins import toolkit as tk

log = logging.getLogger(__name__)

user = Blueprint("approval_user", __name__, url_prefix="/user")

# TODO: register view?


class EditView(BaseEditView):
    def __init__(self):
        super().__init__()

    def get(self, id, data=None, errors=None, error_summary=None):
        log.error(data)
        return super().get(id, data, errors, error_summary)

    def post(self, id):
        context, id = self._prepare(id)
        if not context["save"]:
            return self.get(id)

        try:
            data_dict = logic.clean_dict(
                dictization_functions.unflatten(
                    logic.tuplize_dict(logic.parse_params(request.form))
                )
            )

        except dictization_functions.DataError:
            base.abort(400, _("Integrity Error"))

        if current_user.sysadmin:
            # Only allow to update the review permission if requester
            # is sysadmin
            has_review_permission = data_dict.get("user_has_review_permission", False)
            user_name = data_dict.get("name")
            plugin_extras = {
                "user_has_review_permission": has_review_permission != False
            }
            patch_data_dict = {"id": user_name, "plugin_extras": plugin_extras}
            tk.get_action("user_patch")(context, patch_data_dict)

        return super().post(id)


user.add_url_rule("/edit/<id>", view_func=EditView.as_view(str("edit")))


def registred_views():
    return user

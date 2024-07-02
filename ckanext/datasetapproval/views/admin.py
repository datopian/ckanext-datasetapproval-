import logging

from flask import Blueprint
import sqlalchemy
import ckan.model as model
import ckan.lib.base as base
from ckan.common import request, asbool, current_user, _
import ckan.logic as logic
from ckan.lib.helpers import helper_functions as h


log = logging.getLogger(__name__)

admin = Blueprint("sigma2-admin", __name__, url_prefix="/ckan-admin")


def _get_managers():
    User = model.User  # Alias for readability
    q = model.Session.query(User).filter(
        # fmt: off
        User.plugin_extras.op("->>")("user_has_review_permission").cast(sqlalchemy.Boolean) == True,
        User.state == "active",
    )
    return q


def managers() -> str:
    data = dict(sysadmins=[a.name for a in _get_managers()])
    return base.render("admin/managers.html", extra_vars=data)


def manager():
    username = request.form.get("username")
    status = asbool(request.form.get("status"))

    try:
        context = {
            "model": model,
            "session": model.Session,
            "user": current_user.name,
            "auth_user_obj": current_user,
        }

        data_dict = {
            "id": username,
            "plugin_extras": {"user_has_review_permission": status},
        }
        user = logic.get_action("user_patch")(context, data_dict)
    except logic.NotAuthorized:
        return base.abort(403, _("Not authorized to promote user to archive manager"))
    except logic.NotFound:
        return base.abort(404, _("User not found"))

    if status:
        h.flash_success(
            _("Promoted {} to archive manager".format(user["display_name"]))
        )
    else:
        h.flash_success(
            _("Revoked archive manager permission from {}".format(user["display_name"]))
        )
    return h.redirect_to("sigma2-admin.managers")


admin.add_url_rule(
    "/managers", view_func=managers, methods=["GET"], strict_slashes=False
)
admin.add_url_rule(rule="/manager", view_func=manager, methods=["POST"])


def registred_views():
    return admin

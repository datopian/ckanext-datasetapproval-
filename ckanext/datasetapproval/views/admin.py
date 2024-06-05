import logging

from flask import Blueprint
import sqlalchemy
import ckan.model as model
import ckan.lib.base as base
from ckan.common import request, asbool, current_user, _
from typing import cast, Any
from ckan.types import Context, Schema, Response
import ckan.logic as logic
from ckan.lib.helpers import helper_functions as h


log = logging.getLogger(__name__)

admin = Blueprint("sigma2-admin", __name__, url_prefix="/ckan-admin")


def _get_managers():
    q = model.Session.query(model.User).filter(
        model.User.plugin_extras.op("->>")("user_has_review_permission").cast(sqlalchemy.Boolean) == True,
        model.User.state == u'active')

    return q


def managers() -> str:
    data = dict(sysadmins=[a.name for a in _get_managers()])
    return base.render(u'admin/managers.html', extra_vars=data)


def manager():
    username = request.form.get(u'username')
    status = asbool(request.form.get(u'status'))

    try:
        context = cast(Context, {
            u'model': model,
            u'session': model.Session,
            u'user': current_user.name,
            u'auth_user_obj': current_user,
        })
        data_dict: dict[str, Any] = {u'id': username, u'plugin_extras': { "user_has_review_permission": status }}
        user = logic.get_action(u'user_patch')(context, data_dict)
    except logic.NotAuthorized:
        return base.abort(
            403,
            _(u'Not authorized to promote user to archive manager')
        )
    except logic.NotFound:
        return base.abort(404, _(u'User not found'))

    if status:
        h.flash_success(
            _(u'Promoted {} to archive manager'.format(user[u'display_name']))
        )
    else:
        h.flash_success(
            _(
                u'Revoked archive manager permission from {}'.format(
                    user[u'display_name']
                )
            )
        )
    return h.redirect_to(u'sigma2-admin.managers')


admin.add_url_rule(
    u'/managers', view_func=managers, methods=['GET'], strict_slashes=False
)
admin.add_url_rule(rule=u'/manager', view_func=manager, methods=['POST'])


def registred_views():
    return admin

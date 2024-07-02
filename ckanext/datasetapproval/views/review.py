# Standard library imports
import logging
from functools import partial

# Related third-party imports
from flask import Blueprint, redirect, url_for
from flask.views import MethodView

# Local application/library specific imports
from ckan import model
from ckan.lib import base
import ckan.lib.helpers as h
from ckan.plugins import toolkit as tk
from ckan.views.dataset import url_with_params
from ckan.views.user import _extra_template_variables
from ckan import logic

log = logging.getLogger(__name__)

blueprint = Blueprint(
    "approval",
    __name__,
)


def _pager_url(params_nopage, package_type, q=None, page=None):
    params = list(params_nopage)
    params.append(("page", page))
    return search_url(params, package_type)


def search_url(params, package_type=None):
    url = h.url_for("approval.review", id=tk.c.user)
    return url_with_params(url, params)


class DatasetReviewView(MethodView):
    def _prepare(self):
        context = {
            "model": model,
            "session": model.Session,
            "user": tk.current_user.name,
            "auth_user_obj": tk.current_user,
            "save": "save" in tk.request.form,
        }
        return context

    def get(self, id):
        context = self._prepare()
        user_id = tk.current_user.id

        limit = 20
        page = h.get_page_number(tk.request.args)

        params_nopage = [
            (k, v) for k, v in tk.request.args.items(multi=True) if k != "page"
        ]

        pager_url = partial(_pager_url, params_nopage, "dataset")

        fq = "+state:(inreview OR pending OR rejected)"

        search_dict = {
            "fq": fq,
            "include_private": True,
            "include_drafts": True,
            "rows": limit,
            "start": limit * (page - 1),
            "sort": "state asc, metadata_modified desc",
        }

        data_dict = {"id": id, "user_obj": tk.c.userobj, "include_num_followers": True}

        extra_vars = _extra_template_variables(context, data_dict)

        try:
            user_has_review_permission = tk.check_access("dataset_review", context, None)
        except logic.NotAuthorized:
            user_has_review_permission = False

        if user_has_review_permission:
            context["ignore_auth"] = True
        dataset_result = tk.get_action("package_search")(context, search_dict)

        extra_vars["user_dict"].update(
            {
                "datasets": dataset_result["results"],
                "total_count": dataset_result["count"],
            }
        )

        extra_vars["page"] = h.Page(
            collection=dataset_result["results"],
            page=page,
            url=pager_url,
            item_count=dataset_result["count"],
            items_per_page=limit,
        )
        extra_vars["page"].items = dataset_result["results"]

        return base.render("user/review.html", extra_vars)


def review_action(id, action):
    context = {
        "model": model,
        "session": model.Session,
        "user": tk.c.user,
    }
    if action == "publish":
        context = {
            "model": model,
            "session": model.Session,
            "user": tk.c.user,
        }
        result = tk.get_action("publish_dataset")(context, id)
        if result.get("package").get("state") == "active":
            tk.h.flash_success(tk._("Dataset has been published."))
        return tk.redirect_to(controller="dataset", action="read", id=id)

    data_dict = {"dataset_id": id, "action": action}
    tk.get_action("dataset_review")(context, data_dict)
    if action == "reject":
        tk.h.flash_error(tk._("Dataset has been reviewed and rejected."))
    else:
        tk.h.flash_success(tk._("Dataset has been reviewed and approved."))
    return tk.redirect_to(controller="dataset", action="read", id=id)


def register_review_plugin_rules(blueprints):
    blueprints.add_url_rule(
        "/user/<id>/dataset/review", view_func=DatasetReviewView.as_view("review")
    )
    blueprints.add_url_rule("/dataset/review/<id>/<action>", view_func=review_action)


register_review_plugin_rules(blueprint)


def registred_views():
    return blueprint

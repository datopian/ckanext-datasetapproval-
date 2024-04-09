# encoding: utf-8
import logging

from flask import Blueprint
from ckan.common import current_user
from ckan.plugins import toolkit as tk
import ckan.model as model
from ckan.views.dataset import (
    CreateView as BaseCreateView,
    EditView as BaseEditView,
    _get_package_type,
    _setup_template_variables,
    _get_pkg_template,
    _tag_string_to_list,
    _form_save_redirect,
)
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic


log = logging.getLogger(__name__)

dataset = Blueprint(
    "approval_dataset",
    __name__,
    url_prefix="/dataset",
    url_defaults={"package_type": "dataset"},
)


class CreateView(BaseCreateView):
    def __init__(self):
        super().__init__()

    def get(self, package_type, data=None, errors=None, error_summary=None):
        if data and data.get("agree") == "on":
            data["terms_agreed"] = True
            return super().get(package_type, data, {}, {})

        if error_summary:
            return super().get(package_type, data, errors, error_summary)
        return terms_and_conditions(package_type)

    def post(self, package_type):
        save_draft = tk.request.form.get("save") == "save-draft"
        alread_saved = tk.request.form.get("pkg_name")
        context = self._prepare()
        try:
            data_dict = logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(logic.parse_params(tk.request.form))
                )
            )
        except dict_fns.DataError:
            return tk.base.abort(400, tk._("Integrity Error"))
        try:
            if save_draft:
                data_dict["state"] = "draft"
                action = "package_update" if alread_saved else "package_create"
                pkg_dict = tk.get_action(action)(context, data_dict)
                tk.h.flash_success(tk._("Dataset saved as draft"))
                return self.get(package_type, data=pkg_dict)
        except tk.NotAuthorized:
            return tk.base.abort(403, tk._("Unauthorized to read package"))
        except tk.ObjectNotFound:
            return tk.base.abort(404, tk._("Dataset not found"))
        except tk.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(
                package_type, data=data_dict, errors=errors, error_summary=error_summary
            )

        return super().post(package_type)


class EditView(BaseEditView):
    def __init__(self):
        super().__init__()

    def get(self, package_type, id, data=None, errors=None, error_summary=None):
        context = self._prepare()
        package_type = _get_package_type(id) or package_type

        try:
            view_context = context.copy()
            view_context["for_view"] = True
            pkg_dict = tk.get_action("package_show")(view_context, {"id": id})
            context["for_edit"] = True
            old_data = tk.get_action("package_show")(context, {"id": id})

            if data:
                old_data.update(data)
            data = old_data
        except (tk.ObjectNotFound, tk.NotAuthorized):
            return tk.base.abort(404, tk._("Dataset not found"))

        assert data is not None

        pkg = context.get("package")
        resources_json = tk.h.dump_json(data.get("resources", []))
        user = current_user.name

        try:
            tk.check_access("package_update", context)
        except tk.NotAuthorized:
            return tk.base.abort(
                403, tk._("User %r not authorized to edit %s") % (user, id)
            )

        if data and not data.get("tag_string"):
            data["tag_string"] = ", ".join(
                tk.h.dict_list_reduce(pkg_dict.get("tags", {}), "name")
            )

        errors = errors or {}
        form_snippet = _get_pkg_template("package_form", package_type=package_type)
        form_vars = {
            "data": data,
            "errors": errors,
            "error_summary": error_summary,
            "action": "edit",
            "dataset_type": package_type,
            "form_style": "edit",
        }
        errors_json = tk.h.dump_json(errors)

        tk.g.pkg = pkg
        tk.g.resources_json = resources_json
        tk.g.errors_json = errors_json

        _setup_template_variables(context, {"id": id}, package_type=package_type)

        form_vars["stage"] = ["active"]
        if data.get("state", "").startswith("draft"):
            form_vars["stage"] = ["active", "complete"]

        edit_template = _get_pkg_template("edit_template", package_type)
        return tk.base.render(
            edit_template,
            extra_vars={
                "form_vars": form_vars,
                "form_snippet": form_snippet,
                "dataset_type": package_type,
                "pkg_dict": pkg_dict,
                "pkg": pkg,
                "resources_json": resources_json,
                "form_snippet": form_snippet,
                "errors_json": errors_json,
            },
        )

    def post(self, package_type, id):
        context = self._prepare()
        package_type = _get_package_type(id) or package_type
        log.debug("Package save request name: %s POST: %r", id, tk.request.form)
        save_draft = tk.request.form.get("save") == "save-draft"

        try:
            data_dict = logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(logic.parse_params(tk.request.form))
                )
            )
        except dict_fns.DataError:
            return tk.abort(400, tk._("Integrity Error"))

        try:
            if "_ckan_phase" in data_dict:
                # we allow partial updates to not destroy existing resources
                context["allow_partial_update"] = True
                if "tag_string" in data_dict:
                    data_dict["tags"] = _tag_string_to_list(data_dict["tag_string"])
                del data_dict["_ckan_phase"]
                del data_dict["save"]
            data_dict["id"] = id
            if save_draft:
                data_dict["state"] = "draft"
            pkg_dict = tk.get_action("package_update")(context, data_dict)
            if save_draft:
                tk.h.flash_success(tk._("Dataset saved as draft"))
                return self.get(package_type, id, data=pkg_dict)
            else:
                return tk.redirect_to("approval_dataset.dataset_review", id=id)
        except tk.NotAuthorized:
            return tk.abort(403, tk._("Unauthorized to read package %s") % id)
        except tk.ObjectNotFound:
            return tk.abort(404, tk._("Dataset not found"))
        except tk.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(package_type, id, data_dict, errors, error_summary)


def terms_and_conditions(package_type):
    data_dict = {}
    if tk.request.method == "POST":
        data_dict["terms_agreed"] = True
        if "agree" in tk.request.form:
            return tk.redirect_to(tk.url_for("dataset.new"), {"terms_agreed": True})
        else:
            pass
    return tk.render(
        "package/snippets/terms_and_conditions.html", extra_vars={"pkg_dict": data_dict}
    )


def dataset_review(package_type, id):
    # Retrieve the context for CKAN's logic functions
    context = {
        "model": model,
        "session": model.Session,
        "user": tk.c.user or tk.c.author,
    }
    try:
        package_dict = tk.get_action("package_show")(context, {"id": id})
    except tk.ObjectNotFound:
        tk.abort(404, tk._("Dataset not found"))
    except tk.NotAuthorized:
        tk.abort(401, tk._("Unauthorized to read dataset"))

    return tk.render(
        "package/snippets/review.html",
        extra_vars={"pkg_dict": package_dict, "data": package_dict},
    )


def dataset_publish(package_type, id):
    context = {
        "model": model,
        "session": model.Session,
        "user": tk.c.user or tk.c.author,
    }
    pkg_dict = tk.get_action("package_show")(context, {"id": id})
    resources = pkg_dict.get("resources", [])
    resources = sorted(resources, key=lambda x: x["created"], reverse=True)

    if tk.request.form["save"] == "go-resource":
        return tk.redirect_to("resource.edit", id=pkg_dict["id"], resource_id=resources[0]["id"])

    tk.get_action("package_patch")(context, {"id": id, "state": "active"})
    return tk.redirect_to("{}.read".format("dataset"), id=id)


dataset.add_url_rule("/new", view_func=CreateView.as_view(str("new")))
dataset.add_url_rule("/edit/<id>", view_func=EditView.as_view(str("edit")))
dataset.add_url_rule("/terms/agree", view_func=terms_and_conditions)
dataset.add_url_rule("/<id>/review", view_func=dataset_review)
dataset.add_url_rule("/<id>/publish", view_func=dataset_publish, methods=["POST"])


def registred_views():
    return dataset

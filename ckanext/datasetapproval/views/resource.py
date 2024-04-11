# encoding: utf-8
import logging
import cgi

from flask import Blueprint
from ckan.common import current_user
from ckan.plugins import toolkit as tk
from ckan.views.resource import CreateView as BaseCreateView, EditView as BaseEditView
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic
from ckan import model

log = logging.getLogger(__name__)

resource = Blueprint(
    "approval_dataset_resource",
    __name__,
    url_prefix="/dataset/<id>/resource",
    url_defaults={"package_type": "dataset"},
)

prefixed_resource = Blueprint(
    "approval_resource",
    __name__,
    url_prefix="/dataset/<id>/resource",
    url_defaults={"package_type": "dataset"},
)


class CreateView(BaseCreateView):
    def __init__(self):
        super().__init__()

    def post(self, package_type, id):
        save_action = tk.request.form.get("save")

        data = logic.clean_dict(
            dict_fns.unflatten(logic.tuplize_dict(logic.parse_params(tk.request.form)))
        )
        data.update(
            logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(logic.parse_params(tk.request.files))
                )
            )
        )

        del data["save"]
        resource_id = data.pop("id")

        context = {
            "model": model,
            "session": model.Session,
            "user": current_user.name,
            "auth_user_obj": current_user,
        }

        # see if we have any data that we are trying to save
        data_provided = False
        for key, value in data.items():
            if (
                value or isinstance(value, cgi.FieldStorage)
            ) and key != "resource_type":
                data_provided = True
                break

        if not data_provided and save_action != "go-dataset-complete":
            if save_action == "go-dataset":
                # go to final stage of adddataset
                return tk.h.redirect_to("{}.edit".format(package_type), id=id)
            # see if we have added any resources
            try:
                data_dict = tk.get_action("package_show")(context, {"id": id})
            except tk.NotAuthorized:
                return tk.abort(403, tk._("Unauthorized to update dataset"))
            except tk.ObjectNotFound:
                return tk.abort(
                    404, tk._("The dataset {id} could not be found.").format(id=id)
                )
            if not len(data_dict["resources"]):
                # no data so keep on page
                msg = tk._("You must add at least one data resource")
                # On new templates do not use flash message

                errors = {}
                error_summary = {tk._("Error"): msg}
                return self.get(package_type, id, data, errors, error_summary)

            data_dict = tk.get_action("package_show")(context, {"id": id})
            tk.get_action("package_update")(
                dict(context, allow_state_change=True), dict(data_dict, state="active")
            )
            return tk.h.redirect_to("{}.read".format(package_type), id=id)

        data["package_id"] = id
        try:
            if resource_id:
                data["id"] = resource_id
                tk.get_action("resource_update")(context, data)
            else:
                data = tk.get_action("resource_create")(context, data)
        except tk.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            if data.get("url_type") == "upload" and data.get("url"):
                data["url"] = ""
                data["url_type"] = ""
                data["previous_upload"] = True
            return self.get(package_type, id, data, errors, error_summary)
        except tk.NotAuthorized:
            return tk.abort(403, tk._("Unauthorized to create a resource"))
        except tk.ObjectNotFound:
            return tk.abort(
                404, tk._("The dataset {id} could not be found.").format(id=id)
            )
        if save_action == "go-metadata":
            # XXX race condition if another user edits/deletes
            data_dict = tk.get_action("package_show")(context, {"id": id})
            tk.get_action("package_update")(
                dict(context, allow_state_change=True), dict(data_dict, state="active")
            )
            return tk.redirect_to("{}.read".format(package_type), id=id)
        elif save_action == "go-dataset":
            # go to first stage of add dataset
            return tk.redirect_to("{}.edit".format(package_type), id=id)
        elif save_action == "go-dataset-complete":

            return tk.redirect_to("{}.read".format(package_type), id=id)
        elif save_action == "save-draft":
            tk.h.flash_success(tk._("Saved as draft."))
            return self.get(package_type, id, data)
        else:
            # add more resources
            return tk.redirect_to("{}_resource.new".format(package_type), id=id)


def register_dataset_plugin_rules(blueprint):
    blueprint.add_url_rule("/new", view_func=CreateView.as_view(str("new")))


register_dataset_plugin_rules(resource)
register_dataset_plugin_rules(prefixed_resource)


def registred_views():
    return resource, prefixed_resource

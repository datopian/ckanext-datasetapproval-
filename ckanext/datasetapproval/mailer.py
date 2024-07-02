import logging

from ckan import model
from ckan.common import config
from ckan.plugins import toolkit
from ckan.lib.mailer import mail_user
from ckan.logic.action.get import member_list as core_member_list

log = logging.getLogger(__name__)


def mail_package_review_request_to_admins(
    context,
    data_dict,
    _type="new",
):
    sysadmins = (
        model.Session.query(model.User.id)
        .filter(model.User.state != model.State.DELETED, model.User.sysadmin == True)
        .all()
    )
    # if dataset is not owned by any organization
    if data_dict.get("owner_org") is None:
        admins = [admin[0] for admin in sysadmins]
    else:
        members = core_member_list(
            context=context, data_dict={"id": data_dict.get("owner_org")}
        )
        org_admin = [i[0] for i in members if i[2] == "Admin"]
        # Merged org admin and sysadmin so that sysadmin also gets the email.

        admins = list(set(org_admin + [admin[0] for admin in sysadmins]))

    for admin_id in admins:
        user = model.User.get(admin_id)
        if user.email:
            subj = _compose_email_subj_for_admins(_type)
            body = _compose_email_body_for_admins(context, data_dict, user, _type)
            mail_user(user, subj, body)
            log.debug(
                "[email] Dataset review request email sent to {0}".format(user.name)
            )


def mail_package_approve_reject_notification_to_editors(package_id, status):
    package_dict = toolkit.get_action("package_show")(
        {"ignore_auth": True}, {"id": package_id}
    )
    editor = model.User.get(package_dict.get("creator_user_id"))
    if editor.email:
        subj = _compose_email_subj_for_editors(status)
        body = _compose_email_body_for_editors(editor, package_dict, status)
        mail_user(editor, subj, body)
        log.debug(
            "[email] Dataset approved/rejected notfication email sent to {0}".format(
                editor.name
            )
        )


def _compose_email_subj_for_admins(_type):
    return " A {0} dataset is requested for review.".format(_type)


def _compose_email_subj_for_editors(state):
    if state == "approve":
        return "Dataset request has been reviewed and approved by the administrator."
    else:
        return "Your dataset request has been reviewed by the administrator."


def _get_publisher_name(context, id):
    try:
        user_dict = toolkit.get_action("user_show")(context, {"id": id})
        return user_dict.get("display_name")
    except toolkit.ObjectNotFound as e:
        return "None"


def _compose_email_body_for_admins(context, data_dict, user, _type):
    pkg_link = toolkit.url_for("dataset_read", id=data_dict["name"], qualified=True)
    admin_name = user.fullname or user.name
    site_title = config.get("ckan.site_title")
    site_url = config.get("ckan.site_url")
    package_title = data_dict.get("title")
    package_description = data_dict.get("notes", "")
    package_url = pkg_link
    publisher_name = _get_publisher_name(context, data_dict.get("creator_user_id"))

    email_body = f"""
        Dear {admin_name},

        {'An'if _type == 'updated' else 'A'} {_type} dataset has been requested for review by {publisher_name}:

            {package_title}

            {package_description}

        To approve or reject the request, please visit the following page (logged in as an admin):

            {package_url}

        Have a nice day.


        --
        Message sent by {site_title} ({site_url})
        This is an automated message, please don't respond to this address.
        """
    return email_body


def _compose_email_body_for_editors(user, package_dict, state):
    pkg_link = toolkit.url_for("dataset_read", id=package_dict["name"], qualified=True)
    editor_name = user.fullname or user.name
    site_title = config.get("ckan.site_title")
    site_url = config.get("ckan.site_url")
    package_title = package_dict.get("title")
    package_description = package_dict.get("notes", "")
    package_url = pkg_link

    email_body = f"""
        Dear {editor_name},

        {'Your dataset has been approved and published by the administrator.' 
        if state == 'approved' else 'Your dataset request has been reviewed and rejected by the administrator.'} 

            {package_title}

            {package_description}

       To view the dataset, please visit following page:

            {package_url}

        Have a nice day.

        --
        Message sent by {site_title} ({site_url})
        This is an automated message, please don't respond to this address.
        """
    return email_body

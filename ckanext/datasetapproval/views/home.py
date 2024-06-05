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
from ckan.lib.helpers import helper_functions as h

log = logging.getLogger(__name__)

home = Blueprint("sigma2-home", __name__, url_prefix="/")

def about():
    return h.redirect_to('home.index')

home.add_url_rule(u'/about', view_func=about, methods=['GET'], strict_slashes=False)

def registred_views():
    return home

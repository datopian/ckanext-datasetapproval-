import logging

from flask import Blueprint
from ckan.lib.helpers import helper_functions as h
from ckan.lib.helpers import helper_functions as h

log = logging.getLogger(__name__)

home = Blueprint("sigma2-home", __name__, url_prefix="/")

def about():
    return h.redirect_to('home.index')

home.add_url_rule(u'/about', view_func=about, methods=['GET'], strict_slashes=False)

def registred_views():
    return home

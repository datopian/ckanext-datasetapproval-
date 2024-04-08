import ckan.plugins.toolkit as toolkit

import logging as log

log = log.getLogger(__name__)


def state_validator(key, data, errors, context):
    print("=================++> state_validator")
    data[key] = "draft"
    return

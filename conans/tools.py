"""
    Conan tools: classes and function in this module are intended to be used out of the box
    with the Conan configuration already currified into them. This configuration refers
    mainly to two items:
     - requester: on network calls, this will include proxy definition.
     - output: the output configuration

    Here in this module there should be no logic, all functions and classes must be implemented
    elsewhere (mainly in conans.util or conans.client.tools) and ready to be used without
    the currification.
"""

from __future__ import print_function

import requests
import sys

from conans.client.output import ConanOutput

# noinspection PyUnresolvedReferences
from conans.client import tools as client_tools
# noinspection PyUnresolvedReferences
from conans.util.env_reader import get_env
# noinspection PyUnresolvedReferences
from conans.util.files import (_generic_algorithm_sum, load, sha256sum,
                               sha1sum, md5sum, md5, touch, relative_dirs,
                               rmdir, mkdir, to_file_bytes, save, save_append)


# This global variables are intended to store the configuration of the running Conan application
_global_output = None
_global_requester = None


def set_global_instances(the_output, the_requester):
    global _global_output
    global _global_requester

    # TODO: pass here the configuration file, and make the work here (explicit!)
    _global_output = the_output
    _global_requester = the_requester


# Assign a default, will be overwritten in the factory of the ConanAPI
set_global_instances(the_output=ConanOutput(sys.stdout, True), the_requester=requests)


"""
From here onwards only currification is expected, no logic
"""


def save(path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    # TODO: This function is not currified, should be moved out of here
    if append:
        save_append(path=path, content=content)
    else:
        save(path=path, content=content, only_if_modified=False)


def download(*args, **kwargs):
    return client_tools.download(out=_global_output, requester=_global_requester, *args, **kwargs)


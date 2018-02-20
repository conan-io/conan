""" ConanFile user tools, as download, etc"""
from __future__ import print_function

import requests
from conans.client.tools import *
from conans.client.output import ConanOutput
# noinspection PyUnresolvedReferences
from conans.util.env_reader import get_env
# noinspection PyUnresolvedReferences
from conans.util.files import (_generic_algorithm_sum, load, save, sha256sum,
                               sha1sum, md5sum, md5, touch, relative_dirs, rmdir, mkdir)


# Global instances
def set_global_instances(the_output, the_requester):
    # Assign global variables to needed modules
    from conans.client.tools import files as _files
    from conans.client.tools import net as _net
    from conans.client.tools import oss as _oss
    from conans.client.tools import system_pm as _system_pm
    from conans.client.tools import win as _win

    _files._global_output = the_output
    _oss._global_output = the_output
    _system_pm._global_output = the_output
    _win._global_output = the_output
    _net._global_requester = the_requester


set_global_instances(ConanOutput(sys.stdout), requests)

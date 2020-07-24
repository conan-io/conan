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

import requests

from conans.client.output import ConanOutput
# Tools from conans.client.tools
from conans.client.tools import files as tools_files, net as tools_net, oss as tools_oss, \
    system_pm as tools_system_pm, win as tools_win
from conans.client.tools.env import *  # pylint: disable=unused-import
from conans.client.tools.pkg_config import *  # pylint: disable=unused-import
from conans.client.tools.scm import *  # pylint: disable=unused-import
from conans.client.tools.settings import *  # pylint: disable=unused-import
from conans.client.tools.apple import *
from conans.client.tools.android import *
# Tools form conans.util
from conans.util.env_reader import get_env
from conans.util.log import logger
from conans.client.tools.version import Version
from conans.client.build.cppstd_flags import cppstd_flag_new as cppstd_flag  # pylint: disable=unused-import


"""
From here onwards only currification is expected, no logic
"""




# From conans.client.tools.net




# from conans.client.tools.files




# from conans.client.tools.oss








# from conans.client.tools.win









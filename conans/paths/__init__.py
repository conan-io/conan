# coding=utf-8

import os
import platform

if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user
else:
    from conans.util.files import rmdir

    conan_expand_user = os.path.expanduser
    rm_conandir = rmdir


def get_conan_user_home():
    user_home = os.getenv("CONAN_USER_HOME", "~")
    tmp = conan_expand_user(user_home)
    if not os.path.isabs(tmp):
        raise Exception("Invalid CONAN_USER_HOME value '%s', "
                        "please specify an absolute or path starting with ~/ "
                        "(relative to user home)" % tmp)
    return os.path.abspath(tmp)

# coding=utf-8
from configparser import ConfigParser
import os
import platform


if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user
else:
    conan_expand_user = os.path.expanduser

DEFAULT_CONAN_HOME = ".conan2"


def get_conan_user_home():
    conanrc_home = None

    conanrc_config = ConfigParser()
    conanrc_file = conanrc_config.read(os.path.join(os.getcwd(), "conan.conanrc"))

    if conanrc_file:
        try:
            init_section = conanrc_config["init"]
            conanrc_home = init_section["conan_home"]
        except KeyError:
            pass

    if conanrc_home and (conanrc_home[:2] in ("./", ".\\") or conanrc_home.startswith("..")):  # local
        conanrc_home = os.path.abspath(os.path.join(os.getcwd(), conanrc_home))

    user_home = conanrc_home or os.getenv("CONAN_HOME")
    if user_home is None:
        # the default, in the user home
        user_home = os.path.join(conan_expand_user("~"), DEFAULT_CONAN_HOME)
    else:  # Do an expansion, just in case the user is using ~/something/here
        user_home = conan_expand_user(user_home)
    if not os.path.isabs(user_home):
        raise Exception("Invalid CONAN_HOME value '%s', "
                        "please specify an absolute or path starting with ~/ "
                        "(relative to user home)" % user_home)
    return user_home


# Files
CONANFILE = 'conanfile.py'
CONANFILE_TXT = "conanfile.txt"
CONAN_MANIFEST = "conanmanifest.txt"
CONANINFO = "conaninfo.txt"
PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"
EXPORT_SOURCES_TGZ_NAME = "conan_sources.tgz"
DEFAULT_PROFILE_NAME = "default"
DATA_YML = "conandata.yml"

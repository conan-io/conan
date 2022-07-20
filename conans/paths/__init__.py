# coding=utf-8
import os
import platform


if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user
else:
    conan_expand_user = os.path.expanduser

DEFAULT_CONAN_HOME = ".conan2"


def get_conan_user_home():
    def _read_user_home_from_rc():
        try:
            conanrc_path = os.path.join(os.getcwd(), "conan.conanrc")
            values = {k: str(v) for k, v in
                      (line.split('=') for line in open(conanrc_path).read().splitlines() if
                       not line.startswith("#"))}
            conan_home = values["conan_home"]
            # check if it's a local folder
            if conan_home[:2] in ("./", ".\\") or conan_home.startswith(".."):
                conan_home = os.path.abspath(os.path.join(os.getcwd(), conan_home))
            return conan_home
        except (IOError, KeyError):
            return None

    user_home = _read_user_home_from_rc() or os.getenv("CONAN_HOME")
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

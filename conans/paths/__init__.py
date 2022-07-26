# coding=utf-8
import os
import platform
from pathlib import Path

if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user
else:
    conan_expand_user = os.path.expanduser

DEFAULT_CONAN_HOME = ".conan2"


def get_conan_user_home():

    def _find_conanrc_file():
        path = Path(os.getcwd())
        while path.is_dir() and len(path.parts) > 1:  # finish at '/'
            conanrc_file = path / ".conanrc"
            if conanrc_file.is_file():
                return conanrc_file
            else:
                path = path.parent

    def _user_home_from_conanrc_file():
        try:
            conanrc_path = _find_conanrc_file()

            with open(conanrc_path) as conanrc_file:
                values = {k: str(v) for k, v in
                          (line.split('=') for line in conanrc_file.read().splitlines() if
                           not line.startswith("#"))}

            conan_home = values["conan_home"]
            # check if it's a local folder
            if conan_home[:2] in ("./", ".\\") or conan_home.startswith(".."):
                conan_home = conanrc_path.parent.absolute() / conan_home
            return conan_home
        except (OSError, KeyError, TypeError):
            return None

    user_home = _user_home_from_conanrc_file() or os.getenv("CONAN_HOME")
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

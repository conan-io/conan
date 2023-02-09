import os

from conan.cli.commands import make_abs_path
from conans.errors import ConanException


class LocalAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @staticmethod
    def get_conanfile_path(path, cwd, py):
        """
        param py= True: Must be .py, None: Try .py, then .txt
        """
        path = make_abs_path(path, cwd)

        if os.path.isdir(path):  # Can be a folder
            path_py = os.path.join(path, "conanfile.py")
            if py:
                path = path_py
            else:
                path_txt = os.path.join(path, "conanfile.txt")
                if os.path.isfile(path_py) and os.path.isfile(path_txt):
                    raise ConanException("Ambiguous command, both conanfile.py and conanfile.txt exist")
                path = path_py if os.path.isfile(path_py) else path_txt

        if not os.path.isfile(path):  # Must exist
            raise ConanException("Conanfile not found at %s" % path)

        if py and not path.endswith(".py"):
            raise ConanException("A conanfile.py is needed, " + path + " is not acceptable")

        return path

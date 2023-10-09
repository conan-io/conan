from conans.model.conan_file import ConanFile
from conan.tools.scm import Version as _Version
from conans import __version__


conan_version = _Version(__version__)

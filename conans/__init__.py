# Allow conans to import ConanFile from here
# to allow refactors
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.settings import Settings
from conans.client.cmake import CMake
from conans.client.gcc import GCC
from conans.util.files import load
import os

version_file = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt"))
__version__ = load(version_file)

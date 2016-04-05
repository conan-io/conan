# Allow conans to import ConanFile from here
# to allow refactors
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.settings import Settings
from conans.client.cmake import CMake
from conans.client.gcc import GCC
from conans.client.configure_environment import ConfigureEnvironment
from conans.util.files import load
import os

__version__ = '0.8.6'

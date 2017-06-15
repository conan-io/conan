# Allow conans to import ConanFile from here
# to allow refactors
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.settings import Settings
from conans.client.cmake import CMake
from conans.client.gcc import GCC
from conans.client.configure_environment import ConfigureEnvironment
from conans.client.configure_build_environment import (AutoToolsBuildEnvironment, VisualStudioBuildEnvironment)
from conans.client.run_environment import RunEnvironment
from conans.util.files import load
import os

# complex_search: With ORs and not filtering by not restricted settings
COMPLEX_SEARCH_CAPABILITY = "complex_search"
SERVER_CAPABILITIES = [COMPLEX_SEARCH_CAPABILITY, ]

__version__ = '0.24.0.rc1'


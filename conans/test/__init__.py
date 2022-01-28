import os
import warnings

CONAN_TEST_FOLDER = os.getenv('CONAN_TEST_FOLDER', None)

# Enable warnings as errors only for `conan[s]` module
# warnings.filterwarnings("error", module="(.*\.)?conans\..*")

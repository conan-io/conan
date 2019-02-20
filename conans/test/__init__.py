import os
import warnings

CONAN_TEST_FOLDER = os.getenv('CONAN_TEST_FOLDER', None)
os.environ["CONAN_RECIPE_LINTER"] = "False"

# Enable warnings as errors only for `conans` module
warnings.filterwarnings("error", module="conans.*")

import os

from conans.util.env_reader import get_env

CONAN_TEST_FOLDER = os.getenv('CONAN_TEST_FOLDER', None)
os.environ["CONAN_RECIPE_LINTER"] = "False"

revisions_enabled = get_env("CONAN_TESTING_SERVER_REVISIONS_ENABLED", False)

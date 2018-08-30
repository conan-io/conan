import os

CONAN_TEST_FOLDER = os.getenv('CONAN_TEST_FOLDER', None)
os.environ["CONAN_RECIPE_LINTER"] = "False"

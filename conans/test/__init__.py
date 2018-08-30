import os

CONAN_TEST_FOLDER = os.getenv('CONAN_TEST_FOLDER', None)


def setUpModule():
    os.environ["CONAN_RECIPE_LINTER"] = "False"


def tearDownModule():
    del os.environ["CONAN_RECIPE_LINTER"]

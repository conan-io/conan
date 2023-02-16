import json
import os

from conan.api.conan_api import ConanAPI
from conans.model.conf import BUILT_IN_CONFS
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


def test_missing_subarguments():
    """ config MUST run  with a subcommand. Otherwise, it MUST exits with error.
    """
    client = TestClient()
    client.run("config", assert_error=True)
    assert "ERROR: Exiting with code: 2" in client.out


class TestConfigHome:
    """ The test framework cannot test the CONAN_HOME env-var because it is not using it
    (it will break tests for maintainers that have the env-var defined)
    """
    def test_config_home_default(self):
        client = TestClient()
        client.run("config home")
        assert f"{client.cache.cache_folder}\n" == client.stdout

        client.run("config home --format=text")
        assert f"{client.cache.cache_folder}\n" == client.stdout

    def test_api_uses_env_var_home(self):
        cache_folder = os.path.join(temp_folder(), "custom")
        with environment_update({"CONAN_HOME": cache_folder}):
            api = ConanAPI()
            assert api.cache_folder == cache_folder


def test_config_list():
    """
    'conan config list' shows all the built-in Conan configurations
    """
    client = TestClient()
    client.run("config list")
    for k, v in BUILT_IN_CONFS.items():
        assert f"{k}: {v}" in client.out
    client.run("config list --format=json")
    assert f"{json.dumps(BUILT_IN_CONFS, indent=4)}\n" == client.stdout

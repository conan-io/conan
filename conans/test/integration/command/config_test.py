import json
import os


from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load, save_append
from conans.test.utils.test_files import temp_folder
from conans.util.env_reader import environment_set
from conans.model.conf import DEFAULT_CONFIGURATION


def _assert_dict_subset(expected, actual):
    actual = {k: v for k, v in actual.items() if k in expected}
    assert all(v == actual[k] for k, v in expected.items()) and len(expected) == len(actual)


def test_missing_subarguments():
    """ config MUST run  with a subcommand. Otherwise, it MUST exits with error.
    """
    client = TestClient()
    client.run("config", assert_error=True)
    assert "ERROR: Exiting with code: 2" in client.out


def test_config_home_default():
    """ config home MUST show conan home path
    """
    client = TestClient()
    client.run("config home")
    assert client.cache.cache_folder in client.out
    client.run("config home --json home.json")
    _assert_dict_subset({"home": client.cache.cache_folder}, json.loads(client.load("home.json")))


def test_config_home_custom_home_dir():
    """ config home MUST accept CONAN_USER_HOME as custom home path
    """
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_set({"CONAN_USER_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder)
        client.run("config home")
        assert cache_folder in client.out
        client.run("config home --json home.json")
        _assert_dict_subset({"home": cache_folder}, json.loads(client.load("home.json")))


def test_config_home_custom_install():
    """ config install MUST accept CONAN_USER_HOME as custom home path
    """
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_set({"CONAN_USER_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder)
        client.save({"conanfile.py": GenConanfile()})
        client.run("install .")
        assert "conanfile.py: Installing package" in client.out


def test_init():
    """ config init MUST initialize conan.conf, remotes, settings and default profile
    """
    client = TestClient()
    client.run('config init')
    assert os.path.exists(client.cache.conan_conf_path)
    assert os.path.exists(client.cache.remotes_path)
    assert os.path.exists(client.cache.settings_path)
    assert not os.path.exists(client.cache.default_profile_path)


def test_init_overwrite():
    """ config init --force MUST override current content
    """
    client = TestClient()
    client.run('config init')
    dummy_content = 'DUMMY CONTENT. SHOULD BE REMOVED!'
    save_append(client.cache.conan_conf_path, dummy_content)
    save_append(client.cache.remotes_path, dummy_content)
    save_append(client.cache.settings_path, dummy_content)
    save_append(client.cache.default_profile_path, dummy_content)

    client.run('config init --force')
    assert dummy_content not in load(client.cache.conan_conf_path)
    assert dummy_content not in load(client.cache.conan_conf_path)
    assert dummy_content not in load(client.cache.settings_path)
    assert dummy_content not in load(client.cache.remotes_path)
    assert not os.path.exists(client.cache.default_profile_path)


def test_config_list():
    """ config list MUST show all configuration available for global.conf
    """
    client = TestClient()
    client.run('config list')
    assert "Supported Conan *experimental* global.conf and [conf] properties:" in client.out
    for key, value in DEFAULT_CONFIGURATION.items():
        assert "{}: {}".format(key, value) in client.out

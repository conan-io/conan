import json
import os


from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load, save_append
from conans.test.utils.test_files import temp_folder
from conans.client.tools import environment_append
from conans.model.conf import DEFAULT_CONFIGURATION


def _assert_dict_subset(expected, actual):
    actual = {k: v for k, v in actual.items() if k in expected}
    assert all(v == actual[k] for k, v in expected.items()) and len(expected) == len(actual)


def test_basic():
    """ config get MUST show full file
    """
    client = TestClient()
    client.run("config get")
    assert "default_profile = default" in client.out
    assert "path = ./data" in client.out


def test_storage():
    """ config get storage.path MUST show cache path
    """
    client = TestClient()
    client.run("config get storage")
    assert "path = ./data" in client.out

    client.run("config get storage.path")
    full_path = os.path.join(client.cache_folder, "data")
    assert full_path in client.out
    assert "path:" not in client.out


def test_errors():
    """ Invalid properties MUST be considered an error
    """
    client = TestClient()
    client.run("config get whatever", assert_error=True)
    assert "'whatever' is not a section of conan.conf" in client.out

    client.run("config get whatever.what", assert_error=True)
    assert "'whatever' is not a section of conan.conf" in client.out

    client.run("config get storage.what", assert_error=True)
    assert "'what' doesn't exist in [storage]" in client.out

    client.run('config set proxies=https:', assert_error=True)
    assert "You can't set a full section, please specify a section.key=value" in client.out

    client.run('config set proxies.http:Value', assert_error=True)
    assert "Please specify 'key=value'" in client.out


def test_define():
    """ config set MUST add/override conan.conf properties
    """
    client = TestClient()
    client.run("config set general.fakeos=Linux")
    conf_file = load(client.cache.conan_conf_path)
    assert "fakeos = Linux" in conf_file

    client.run('config set general.compiler="Other compiler"')
    conf_file = load(client.cache.conan_conf_path)
    assert 'compiler = Other compiler' in conf_file

    client.run('config set general.compiler.version=123.4.5')
    conf_file = load(client.cache.conan_conf_path)
    assert 'compiler.version = 123.4.5' in conf_file
    assert "14" not in conf_file

    client.run('config set general.new_setting=mysetting')
    conf_file = load(client.cache.conan_conf_path)
    assert 'new_setting = mysetting' in conf_file

    client.run('config set proxies.https=myurl')
    conf_file = load(client.cache.conan_conf_path)
    assert "https = myurl" in conf_file.splitlines()


def test_set_with_weird_path():
    """ config MUST support symbols in path
       https://github.com/conan-io/conan/issues/4110
    """
    client = TestClient()
    client.run("config set log.trace_file=/recipe-release%2F0.6.1")
    client.run("config get log.trace_file")
    assert "/recipe-release%2F0.6.1", client.out


def test_remove():
    """ config rm MUST remove property value and key
    """
    client = TestClient()
    client.run('config set proxies.https=myurl')
    client.run('config rm proxies.https')
    conf_file = load(client.cache.conan_conf_path)
    assert 'myurl' not in conf_file


def test_remove_section():
    """ config rm MUST remove sections
    """
    client = TestClient()
    client.run('config rm proxies')
    conf_file = load(client.cache.conan_conf_path)
    assert '[proxies]' not in conf_file


def test_remove_envvar():
    """ config MUST add/remove env vars in conan.conf
    """
    client = TestClient()
    client.run('config set env.MY_VAR=MY_VALUE')
    conf_file = load(client.cache.conan_conf_path)
    assert 'MY_VAR = MY_VALUE' in conf_file
    client.run('config rm env.MY_VAR')
    conf_file = load(client.cache.conan_conf_path)
    assert 'MY_VAR' not in conf_file


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
    with environment_append({"CONAN_USER_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder)
        client.run("config home")
        assert cache_folder in client.out
        client.run("config home --json home.json")
        _assert_dict_subset({"home": cache_folder}, json.loads(client.load("home.json")))


def test_config_home_custom_install():
    """ config install MUST accept CONAN_USER_HOME as custom home path
    """
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_append({"CONAN_USER_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder, cache_autopopulate=False)
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
    assert os.path.exists(client.cache.default_profile_path)


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
    assert dummy_content not in load(client.cache.default_profile_path)


def test_config_list():
    """ config list MUST show all configuration available for global.conf
    """
    client = TestClient()
    client.run('config list')
    assert "Supported Conan *experimental* global.conf and [conf] properties:" in client.out
    for key, value in DEFAULT_CONFIGURATION.items():
        assert "{}: {}".format(key, value) in client.out

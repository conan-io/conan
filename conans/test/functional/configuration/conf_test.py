import textwrap

from conans.test.utils.tools import TestClient


def test_core_required_version():
    client = TestClient()
    global_conf = "core:required_conan_version = >=1.0"
    profile = textwrap.dedent("""
    [conf]
    tools.gnu.make:jobs=40
    """)
    client.save({client.cache.new_config_path: global_conf})
    client.save({client.cache.default_profile_path: profile})
    client.run("config get")
    assert textwrap.dedent("""
    [conf]
    core:required_conan_version=>=1.0
    tools.gnu.make:jobs=40""") in client.out

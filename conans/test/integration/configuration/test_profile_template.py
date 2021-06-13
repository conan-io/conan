import platform
import textwrap

from conans.client.tools import environment_append
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_profile_template():
    client = TestClient()
    tpl = textwrap.dedent("""
        [settings]
        os = {{ {"Darwin": "Macos"}.get(platform.system(), platform.system()) }}
        build_type = {{ os.getenv("MY_BUILD_TYPE") }}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1.tpl": tpl})
    with environment_append({"MY_BUILD_TYPE": "Debug"}):
        client.run("install . -pr=profile1.tpl")

    current_os = {"Darwin": "Macos"}.get(platform.system(), platform.system())
    assert "os={}".format(current_os)
    assert "build_type=Debug"

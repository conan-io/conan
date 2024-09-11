import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestErrorsProfilePlugin:
    """ when the plugin fails, we want a clear message and a helpful trace
    """
    def test_error_profile_plugin(self):
        c = TestClient()
        profile_plugin = textwrap.dedent("""\
            def profile_plugin(profile):
                settings = profile.kk
            """)
        save(os.path.join(c.cache.plugins_path, "profile.py"), profile_plugin)

        c.run("install --requires=zlib/1.2.3", assert_error=True)
        assert "Error while processing 'profile.py' plugin, line 2" in c.out
        assert "settings = profile.kk" in c.out

    def test_remove_plugin_file(self):
        c = TestClient()
        c.run("version")  # to trigger the creation
        os.remove(os.path.join(c.cache.plugins_path, "profile.py"))
        c.run("profile show", assert_error=True)
        assert "ERROR: The 'profile.py' plugin file doesn't exist" in c.out

    def test_remove_tools_host(self):
        tc = TestClient(light=True)
        profile_plugin = textwrap.dedent("""\
            import subprocess
            def profile_plugin(profile, **kwargs):
                if kwargs.get("context") == "build":
                    if subprocess.getstatusoutput("cmakee")[0] != 0:
                        profile.tool_requires["!cmake/*"] = ["cmake/[*]"]
                else:
                    profile.tool_requires.clear()

        """)
        save(os.path.join(tc.cache.plugins_path, "profile.py"), profile_plugin)
        tc.save({"profile": "[tool_requires]\nlib/1.0"})
        tc.run("profile show -pr:a=profile -f=json", redirect_stdout="out.json")
        profiles = json.loads(tc.load("out.json"))
        assert len(profiles["host"]["tool_requires"]) == 0
        assert profiles["build"]["tool_requires"] == {"!cmake/*": ["cmake/[*]"], "*": ["lib/1.0"]}


def test_android_ndk_version():
    c = TestClient()
    c.run("profile show -s os=Android")
    assert "os.ndk_version" not in c.out
    c.run("profile show -s os=Android -s os.ndk_version=r26")
    assert "os.ndk_version=r26" in c.out
    c.run("profile show -s os=Android -s os.ndk_version=r26a")
    assert "os.ndk_version=r26a" in c.out

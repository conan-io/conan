import os
import textwrap

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


def test_android_ndk_version():
    c = TestClient()
    c.run("profile show -s os=Android")
    assert "os.ndk_version" not in c.out
    c.run("profile show -s os=Android -s os.ndk_version=r26")
    assert "os.ndk_version=r26" in c.out
    c.run("profile show -s os=Android -s os.ndk_version=r26a")
    assert "os.ndk_version=r26a" in c.out

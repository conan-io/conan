import os
import textwrap

from conans.test.utils.tools import TestClient
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

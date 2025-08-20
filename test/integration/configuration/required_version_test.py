import os
import mock

from conan import __version__
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


class TestRequiredVersion:

    @mock.patch("conan.__version__", "1.26.0")
    def test_wrong_version(self):
        required_version = "1.23.0"
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version={required_version}"})
        client.run("help", assert_error=True)
        assert ("Current Conan version (1.26.0) does not satisfy the defined "
                f"one ({required_version})") in client.out

    @mock.patch("conan.__version__", "1.22.0")
    def test_exact_version(self):
        required_version = "1.22.0"
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version={required_version}"})
        client.run("--help")

    @mock.patch("conan.__version__", "2.1.0")
    def test_lesser_version(self):
        required_version = "<3.0"
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version={required_version}"})
        client.run("--help")

    @mock.patch("conan.__version__", "1.0.0")
    def test_greater_version(self):
        required_version = ">0.1.0"
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version={required_version}"})
        client.run("--help")

    @mock.patch("conan.__version__", "1.0.0")
    def test_greater_version_cc_override(self):
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version=>0.1.0"})
        client.run("config home -cc core:required_conan_version=>2.0", assert_error=True)
        assert f"Current Conan version (1.0.0) does not satisfy the defined one (>2.0)" in client.out

    @mock.patch("conan.__version__", "1.0.0")
    def test_version_check_before_hooks(self):
        client = TestClient(light=True)
        client.save_home({"global.conf": f"core:required_conan_version=>2.0",
                          # The hook shouldn't matter, version check happens earlier
                          "extensions/hooks/hook_trim.py": "some error here"})
        client.run("config home", assert_error=True)
        assert f"Current Conan version (1.0.0) does not satisfy the defined one (>2.0)" in client.out

    def test_bad_format(self):
        required_version = "1.0.0.0-foobar"
        cache_folder = temp_folder()
        save(os.path.join(cache_folder, "global.conf"),
             f"core:required_conan_version={required_version}")
        c = TestClient(cache_folder, light=True)
        c.run("version", assert_error=True)
        assert (f"Current Conan version ({__version__}) does not satisfy "
                f"the defined one ({required_version})") in c.out

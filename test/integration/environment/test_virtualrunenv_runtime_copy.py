import glob
import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


class TestVirtualRunEnvRuntimeCopy:

    dep_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
            package_type = "shared-library"

            def package(self):
                save(self, os.path.join(self.package_folder, "bin", "dep_app.exe"), "APP_CONTENT")
                save(self, os.path.join(self.package_folder, "lib", "dep_lib.so"), "LIB_CONTENT")
        """)

    consumer_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.env import VirtualRunEnv

        class Consumer(ConanFile):
            settings = "os"
            requires = "dep/1.0"

            def generate(self):
                VirtualRunEnv(self, win_copy_folder="myruntime").generate()
        """)

    def test_win_copy_folder(self):
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": self.consumer_conanfile})

        c.run("create dep -s os=Windows")
        c.run("install consumer -s os=Windows")

        assert c.load("consumer/myruntime/dep_app.exe") == "APP_CONTENT"
        assert not os.path.exists(os.path.join(c.current_folder, "consumer",
                                               "myruntime", "dep_lib.so"))

        runenv_files = glob.glob(os.path.join(c.current_folder, "consumer", "conanrunenv.*"))
        assert len(runenv_files) == 1
        runenv = c.load(runenv_files[0])
        assert "myruntime" in runenv

    def test_win_copy_folder_absolute_path_error(self):
        c = TestClient(light=True)
        abs_path = os.path.abspath("myruntime").replace("\\", "/")
        consumer = self.consumer_conanfile.replace('"myruntime"', f'r"{abs_path}"')
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": consumer})

        c.run("create dep -s os=Windows")
        c.run("install consumer -s os=Windows", assert_error=True)
        assert "win_copy_folder must be a relative path" in c.out

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
    def test_win_copy_folder_with_full_deploy(self):
        # Files must be copied from the deployed location, not the cache
        c = TestClient(light=True)
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": self.consumer_conanfile})

        c.run("create dep -s os=Windows")
        c.run("install consumer -s os=Windows --deployer=full_deploy "
              "--deployer-folder=deployed")

        assert c.load("deployed/full_deploy/host/dep/1.0/bin/dep_app.exe") == "APP_CONTENT"
        assert c.load("consumer/myruntime/dep_app.exe") == "APP_CONTENT"

        runenv_files = glob.glob(os.path.join(c.current_folder, "consumer", "conanrunenv.*"))
        assert len(runenv_files) == 1
        runenv = c.load(runenv_files[0])
        # PATH points to the deployed copy folder, not the cache or the deploy source
        assert r"PATH=%~dp0\myruntime" in runenv
        assert "deployed" not in runenv
        assert ".conan2" not in runenv

import glob
import os
import textwrap

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
            requires = "dep/1.0"

            def generate(self):
                VirtualRunEnv(self{}).generate()
        """)

    def test_runtime_copy_from_recipe(self):
        c = TestClient(light=True)
        conanfile = self.consumer_conanfile.format(', runtime_copy="myruntime"')
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": conanfile})

        c.run("create dep")
        c.run("install consumer")

        assert c.load("consumer/myruntime/dep_app.exe") == "APP_CONTENT"
        assert c.load("consumer/myruntime/dep_lib.so") == "LIB_CONTENT"

        runenv_files = glob.glob(os.path.join(c.current_folder, "consumer", "conanrunenv.*"))
        assert len(runenv_files) == 1
        runenv = c.load(runenv_files[0])
        assert "myruntime" in runenv

    def test_runtime_copy_from_conf(self):
        c = TestClient(light=True)
        conanfile = self.consumer_conanfile.format("")
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": conanfile})

        c.run("create dep")
        c.run("install consumer -c tools.env:runtime_copy=myconfruntime")

        assert c.load("consumer/myconfruntime/dep_app.exe") == "APP_CONTENT"
        assert c.load("consumer/myconfruntime/dep_lib.so") == "LIB_CONTENT"

        runenv_files = glob.glob(os.path.join(c.current_folder, "consumer", "conanrunenv.*"))
        assert len(runenv_files) == 1
        runenv = c.load(runenv_files[0])
        assert "myconfruntime" in runenv

    def test_conf_has_priority_over_recipe(self):
        c = TestClient(light=True)
        conanfile = self.consumer_conanfile.format(', runtime_copy="recipecopy"')
        c.save({"dep/conanfile.py": self.dep_conanfile,
                "consumer/conanfile.py": conanfile})

        c.run("create dep")
        c.run("install consumer -c tools.env:runtime_copy=confcopy")

        assert c.load("consumer/confcopy/dep_app.exe") == "APP_CONTENT"
        assert c.load("consumer/confcopy/dep_lib.so") == "LIB_CONTENT"
        assert not os.path.exists(os.path.join(c.current_folder, "consumer", "recipecopy"))

        runenv_files = glob.glob(os.path.join(c.current_folder, "consumer", "conanrunenv.*"))
        assert len(runenv_files) == 1
        runenv = c.load(runenv_files[0])
        assert "confcopy" in runenv
        assert "recipecopy" not in runenv

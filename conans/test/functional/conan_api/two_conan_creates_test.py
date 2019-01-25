import os
import platform
import sys
import unittest

from six import StringIO
from textwrap import dedent

from conans.client.conan_api import ConanAPIV1
from conans.client.tools.env import environment_append
from conans.client.tools.files import chdir
from conans.model.ref import PackageReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import load, save


class ConanCreateTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() == "Windows", "only Windows test")
    def test_preprocessor_called_second_api_call(self):
        """"When calling twice to conan create with the Conan python API, the default
        settings shouldn't be cached. To test that the default profile is not cached,
        this test is verifying that the setting preprocessor is adjusting the runtime
        to MDd when build_type=Debug after a different call to conan create that could
        cache the runtime to MD (issue reported at: #4246) """
        tmp = temp_folder()
        with environment_append({"CONAN_USER_HOME": tmp}):
            with chdir(tmp):
                api, cache, _ = ConanAPIV1.factory()
                api.new(name="lib/1.0@conan/stable", bare=True)

                def get_conaninfo(info):
                    package_id = info["installed"][0]["packages"][0]["id"]
                    folder = cache.package(PackageReference.loads("lib/1.0@conan/stable:%s"
                                                                  % package_id))
                    return load(os.path.join(folder, "conaninfo.txt"))

                settings = ["compiler=Visual Studio", "compiler.version=15", "build_type=Release"]
                info = api.create(".", user="conan", channel="stable", settings=settings)
                self.assertIn("compiler.runtime=MD", get_conaninfo(info))

                settings = ["compiler=Visual Studio", "compiler.version=15", "build_type=Debug"]
                info = api.create(".", user="conan", channel="stable", settings=settings)
                self.assertIn("compiler.runtime=MDd", get_conaninfo(info))

    def test_api_conanfile_loader_shouldnt_cache(self):
        tmp = temp_folder()
        with environment_append({"CONAN_USER_HOME": tmp}):
            with chdir(tmp):
                try:
                    old_stdout = sys.stdout
                    result = StringIO()
                    sys.stdout = result
                    api, _, _ = ConanAPIV1.factory()
                    api._user_io.out = TestBufferConanOutput()
                    conanfile = dedent("""
                        from conans import ConanFile
                        class Pkg(ConanFile):
                            def build(self):
                                self.output.info("NUMBER 42!!")
                        """)
                    save("conanfile.py", conanfile)
                    api.create(".", "pkg", "version", "user", "channel")
                    self.assertIn("pkg/version@user/channel: NUMBER 42!!", result.getvalue())
                    save("conanfile.py", conanfile.replace("42", "123"))
                    api.create(".", "pkg", "version", "user", "channel")
                    self.assertIn("pkg/version@user/channel: NUMBER 123!!", result.getvalue())
                finally:
                    sys.stdout = old_stdout

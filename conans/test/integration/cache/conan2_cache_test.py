import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient


class TestCache:
    def test_conan_export(self):
        client = TestClient()
        client.run_command("open '{}'".format(client.cache_folder))
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("export . mypkg/1.0@user/channel")
        client.run("export . mypkg/2.0@user/channel")

        conanfile = GenConanfile().with_scm({"type": "git", "revision": "auto",
                                             "url": "auto"})
        path, _ = create_local_git_repo({"conanfile.py": str(conanfile),
                                         "source.txt": "somesource"})
        client.current_folder = path
        client.run("export . mypkg/3.0@user/channel")

    def test_conan_create(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake, tools


            class MypkgConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                options = {"shared": [True, False], "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}
                generators = "cmake"
                exports_sources = ["file.txt"]

                def build_id(self):
                    self.info_build.settings.build_type = "Any"

                def source(self):
                    self.run("git clone https://github.com/conan-io/hello.git")

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="hello")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="hello")
                    self.copy("*hello.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.dylib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["hello"]
            """)

        client = TestClient()

        client.save({"conanfile.py": conanfile,
                     "file.txt": ""})

        client.run("create . mypkg/1.0@user/channel")
        client.run("create . mypkg/2.0@user/channel")

        conanfile = GenConanfile().with_scm({"type": "git", "revision": "auto",
                                             "url": "auto"})
        path, _ = create_local_git_repo({"conanfile.py": str(conanfile),
                                         "source.txt": "somesource"})
        client.current_folder = path
        client.run("create . mypkg/3.0@user/channel")

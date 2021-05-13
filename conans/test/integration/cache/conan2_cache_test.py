import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient, TestServer


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

        # conanfile = GenConanfile().with_exports_sources("source.txt")
        # client.save({"conanfile.py": conanfile,
        #              "source.txt": "sources"})
        # client.run("create . mypkg/1.0@user/channel")
        # client.run("create . mypkg/1.0@user/channel")

        client.run("remote add conan-center https://center.conan.io")
        client.run("install zlib/1.2.11@ -r conan-center")
        client.run("install zlib/1.2.11@")
        client.run("install zlib/1.2.11@#08c5163c8e302d1482d8fa2be93736af -r conan-center")
        client.run("install zlib/1.2.11@#514b772abf9c36ad9be48b84cfc6fdc2 -r conan-center")
        client.run("install zlib/1.2.11@ -r conan-center")
        client.run("install zlib/1.2.11@ -r conan-center")
        client.run("install zlib/1.2.11@")
        # client.run("install zlib/1.2.11@ -r conan-center")
        #
        # client.run("install zlib/1.2.11@ -r conan-center --build")
        # conanfile = GenConanfile().with_exports_sources("source.txt")
        # client.save({"conanfile.py": conanfile,
        #              "source.txt": "sources"})
        # client.run("create . mypkg/1.0@user/channel")
        # client.run("create . mypkg/1.0@user/channel")
        #
        # client.run("new mypkg/1.0")
        #
        # client.run("create .")
        # client.run("create .")
        #
        # client.save({"conanfile.py": conanfile,
        #              "file.txt": ""})
        #
        # client.run("create . mypkg/2.0@user/channel")
        # client.run("create . mypkg/3.0@user/channel")
        #
        # conanfile = GenConanfile().with_scm({"type": "git", "revision": "auto",
        #                                      "url": "auto"})
        # path, _ = create_local_git_repo({"conanfile.py": str(conanfile),
        #                                  "source.txt": "somesource"})
        # client.current_folder = path
        # client.run("create . mypkg/3.0@user/channel")

    def test_conan_upload(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.run("new mypkg/1.0 -s")
        client.run("create .")
        client.run("upload mypkg/1.0 -r default")
        client.run("new mypkg/2.0 -s")
        client.run("upload mypkg/2.0")

import os
import platform
from shutil import copy

import mock
import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient, zipdir

app_name = "Release/my_app.exe" if platform.system() == "Windows" else "my_app"


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("no_copy_source", ["False", "True"])
def test_exports_source_with_src_subfolder(no_copy_source):
    """If we have the sources in a subfolder, specifying it in the self.folders.source will
    work both locally (conan build) or in the cache (exporting the sources)"""
    conan_file = GenConanfile() \
        .with_name("app").with_version("1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_exports_sources("my_src/*")\
        .with_cmake_build()\
        .with_class_attribute("no_copy_source={}".format(no_copy_source))

    conan_file = str(conan_file)
    conan_file += """
    def layout(self):
        self.folders.source = "my_src"
        self.folders.build = str(self.settings.build_type)
    """
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"])
    app = gen_function_cpp(name="main")

    client = TestClient()
    client.save({"conanfile.py": conan_file,
                 "my_src/main.cpp": app,
                 "my_src/CMakeLists.txt": cmake})
    client.run("build .")
    assert os.path.exists(os.path.join(client.current_folder, "Release", app_name))
    client.run("create . ")
    assert "Created package revision" in client.out


def test_exports():
    """If we have some sources in the root (like the CMakeLists.txt)
    we don't declare folders.source"""
    conan_file = GenConanfile() \
        .with_name("app").with_version("1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_exports("*.py") \
        .with_import("from my_tools import FOO")

    conan_file = str(conan_file)
    conan_file += """
    def layout(self):
        self.folders.source = "my_src"
    def build(self):
        # This FOO comes from the my_tools.py
        self.output.warning("FOO: {}".format(FOO))
    """

    client = TestClient()
    client.save({"conanfile.py": conan_file,
                 "my_tools.py": "FOO=1"})
    client.run("build .")
    assert "FOO: 1" in client.out

    client.run("create . ")
    assert "FOO: 1" in client.out


@pytest.mark.tool("cmake")
def test_exports_source_without_subfolder():
    """If we have some sources in the root (like the CMakeLists.txt)
    we don't declare folders.source"""
    conan_file = GenConanfile() \
        .with_name("app").with_version("1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_exports_sources("CMakeLists.txt", "my_src/*")\
        .with_cmake_build()

    conan_file = str(conan_file)
    conan_file += """
    def layout(self):
        self.folders.build = str(self.settings.build_type)
    """
    cmake = gen_cmakelists(appname="my_app", appsources=["my_src/main.cpp"])
    app = gen_function_cpp(name="main")

    client = TestClient()
    client.save({"conanfile.py": conan_file,
                 "my_src/main.cpp": app,
                 "CMakeLists.txt": cmake})
    client.run("build .")
    assert os.path.exists(os.path.join(client.current_folder, "Release", app_name))
    client.run("create . ")
    assert "Created package revision" in client.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("no_copy_source", ["False", "True"])
def test_zip_download_with_subfolder_new_tools(no_copy_source):
    """If we have a zip with the sources in a subfolder, specifying it in the self.folders.source
    will unzip in the base and will work both locally (conan build) or in the cache
    (exporting the sources)"""

    tmp = TestClient()  # Used only to save some files, sorry for the lazyness
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"])
    app = gen_function_cpp(name="main")
    tmp.save({"subfolder/main.cpp": app,
              "subfolder/CMakeLists.txt": cmake,
              "ignored_subfolder/ignored.txt": ""})
    zippath = os.path.join(tmp.current_folder, "my_sources.zip")
    zipdir(tmp.current_folder, zippath)

    conan_file = GenConanfile() \
        .with_import("import os") \
        .with_import("from conan.tools.files import get") \
        .with_import("from conan.tools.cmake import CMake") \
        .with_name("app").with_version("1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_generator("CMakeToolchain") \
        .with_class_attribute("no_copy_source={}".format(no_copy_source))

    conan_file = str(conan_file)
    conan_file += """
    def source(self):
        get(self, "http://fake_url/my_sources.zip")

    def layout(self):
        self.folders.source = "src"

    def build(self):
        assert os.path.exists(os.path.join(self.source_folder, "subfolder", "CMakeLists.txt"))
        assert os.path.exists(os.path.join(self.source_folder,
                                           "ignored_subfolder", "ignored.txt"))
        cmake = CMake(self)
        cmake.configure(build_script_folder="subfolder")
        cmake.build()
    """
    client = TestClient()
    client.save({"conanfile.py": conan_file})

    with mock.patch("conan.tools.files.files.download") as mock_download:
        def download_zip(*args, **kwargs):
            copy(zippath, os.getcwd())
        mock_download.side_effect = download_zip
        client.run("create . ")

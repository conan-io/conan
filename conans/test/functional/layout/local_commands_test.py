import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient

def test_local_build():
    """If we configure a build folder in the layout, the installed files in a "conan build ."
    go to the specified folder: "my_build"
    """
    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """

    def configure(self):
        self.layout.build.folder = "my_build"

    def build(self):
        tools.save("build_file.dll", "bar")

"""
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    # FIXME: This should change to "build ." when "conan build" computes the graph
    client.run("build . -if=my_install")
    dll = os.path.join(client.current_folder, "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_build_change_base():
    """If we configure a build folder in the layout, the build files in a "conan build ."
    go to the specified folder: "my_build under the modified base one "common"
    """
    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def configure(self):
        self.layout.build.folder = "my_build"
    def build(self):
        tools.save("build_file.dll", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=common")
    client.run("build . -if=common -bf=common")
    dll = os.path.join(client.current_folder, "common", "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_source():
    """If we configure a source folder in the layout, the downloaded files in a "conan source ."
    go to the specified folder: "my_source"
    """
    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def configure(self):
        self.layout.source.folder = "my_source"

    def source(self):
        tools.save("downloaded.h", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    # FIXME: This should change to "source ." when "conan source" computes the graph
    client.run("source . -if=my_install")
    header = os.path.join(client.current_folder, "my_source", "downloaded.h")
    assert os.path.exists(header)


def test_local_source_change_base():
    """If we configure a source folder in the layout, the souce files in a "conan source ."
    go to the specified folder: "my_source under the modified base one "all_source"
    """
    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    def configure(self):
        self.layout.source.folder = "my_source"

    def source(self):
        tools.save("downloaded.h", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=common")
    client.run("source . -if=common -sf=common")
    header = os.path.join(client.current_folder, "common", "my_source", "downloaded.h")
    assert os.path.exists(header)


def test_local_package():
    """If we configure a package folder in the layout, the packaged files in a "conan package ."
    go to the specified folder: "my_package" and takes everything from the correct build and
    source declared folders
    """
    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True

    def configure(self):
        self.layout.source.folder = "my_source"
        self.layout.build.folder = "my_build"
        self.layout.package.folder = "my_package"

    def source(self):
        tools.save("downloaded.h", "bar")

    def build(self):
        tools.save("library.lib", "bar")
        tools.save("generated.h", "bar")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -if=my_install")
    # FIXME: This should change to "source ." when "conan source" computes the graph
    client.run("source . -if=my_install")
    client.run("build . -if=my_install")
    source_header = os.path.join(client.current_folder, "my_source", "downloaded.h")
    build_header = os.path.join(client.current_folder, "my_build", "generated.h")
    build_library = os.path.join(client.current_folder, "my_build", "library.lib")
    assert os.path.exists(source_header)
    assert os.path.exists(build_header)
    assert os.path.exists(build_library)

    client.run("package . -if=my_install")

    source_header = os.path.join(client.current_folder, "my_package", "downloaded.h")
    build_header = os.path.join(client.current_folder, "my_package", "generated.h")
    build_library = os.path.join(client.current_folder, "my_package", "library.lib")
    assert os.path.exists(source_header)
    assert os.path.exists(build_header)
    assert os.path.exists(build_library)
    assert not os.path.exists(os.path.join(client.current_folder, "package"))

    # If I change the package folder with the -pf the "my_package" go inside
    client.run("package . -if=my_install -pf=parent_package")

    source_header = os.path.join(client.current_folder,
                                 "parent_package", "my_package", "downloaded.h")
    build_header = os.path.join(client.current_folder,
                                "parent_package", "my_package", "generated.h")
    build_library = os.path.join(client.current_folder,
                                 "parent_package", "my_package", "library.lib")
    assert os.path.exists(source_header)
    assert os.path.exists(build_header)
    assert os.path.exists(build_library)

    # If not package layout is specified, the default invented "package/" folder is still used
    # (testing not breaking behavior)
    conan_file = conan_file.replace('self.layout.package.folder = "my_package"', '')
    client.save({"conanfile.py": conan_file})
    client.run("package .  -if=my_install ")
    source_header = os.path.join(client.current_folder, "package", "downloaded.h")
    build_header = os.path.join(client.current_folder, "package", "generated.h")
    build_library = os.path.join(client.current_folder, "package", "library.lib")
    assert os.path.exists(source_header)
    assert os.path.exists(build_header)
    assert os.path.exists(build_library)

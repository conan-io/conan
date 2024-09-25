import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_amentdeps():
    """
    Test that the amentdeps generator generates conan_<name> folders and place CMake files
    in the correct path
    """
    client = TestClient()
    conanfile1 = textwrap.dedent('''
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Recipe(ConanFile):
            name = "lib1"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "lib1"), "")
        ''')
    conanfile2 = textwrap.dedent('''
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Recipe(ConanFile):
            name = "lib2"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires('lib1/1.0')

            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "lib2"), "")
        ''')
    conanfile3 = textwrap.dedent('''
        [requires]
        lib2/1.0
        [generators]
        AmentDeps
        ''')
    client.save({
        "conanfile1.py": conanfile1,
        "conanfile2.py": conanfile2,
        "conanfile3.txt": conanfile3
    })

    client.run("create conanfile1.py")
    client.run("create conanfile2.py")
    client.run("install conanfile3.txt --output-folder install")
    assert "Generating CMake files for lib2 dependency" in client.out
    # Check direct dependencies package.xml file generation
    conan_lib2_package_xml = os.path.join(client.current_folder, "conan_lib2", "package.xml")
    assert os.path.exists(conan_lib2_package_xml)
    # Check CMake files generated
    lib2_cmake_config = os.path.join(client.current_folder, "install", "conan_lib2", "share",
                                     "lib2", "cmake", "lib2-config.cmake")
    assert os.path.exists(lib2_cmake_config)
    # Check lib2's transitive dependency
    lib1_cmake_config = os.path.join(client.current_folder, "install", "conan_lib2", "share",
                                     "lib1", "cmake", "lib1-config.cmake")
    assert os.path.exists(lib1_cmake_config)


def test_amentdeps_environment_shared_libraries():
    """
    Test that the library path file is properly generated so that the environment is set up correctly
    so that the executables generated can found the shared libraries of conan packages
    """
    client = TestClient()
    c1 = GenConanfile("lib1", "1.0").with_shared_option(False).with_package_file("lib/lib2", "lib-content")
    c2 = GenConanfile("lib2", "1.0").with_shared_option(False).with_requirement("lib1/1.0").with_package_file("lib/lib2", "lib-content")
    c3 = textwrap.dedent('''
           [requires]
           lib2/1.0
           [generators]
           AmentDeps
           ''')
    client.save({
        "conanfile1.py": c1,
        "conanfile2.py": c2,
        "conanfile3.txt": c3
    })

    client.run("create conanfile1.py -o *:shared=True")
    client.run("create conanfile2.py -o *:shared=True")
    client.run("install conanfile3.txt -o *:shared=True --output-folder install")
    library_path_content = client.load("install/conan_lib2/share/conan_lib2/environment/library_path.dsv")
    client.run(
        "cache path lib1/1.0#a77a22ae2a9a8dba9b408d95db4e9880:1744785cb24e3bdca70e27041dc5abd20476f947")
    lib1_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib1_lib_path in library_path_content
    client.run(
        "cache path lib2/1.0#4b7a6063ba107d770458ce10385beb52:5c3c2e56259489f7ffbc8e494921eda4b747ef21")
    lib2_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib2_lib_path in library_path_content
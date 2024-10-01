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
        os.path.join("ros_package", "conanfile3.txt"): conanfile3
    })

    client.run("create conanfile1.py")
    client.run("create conanfile2.py")
    client.run("install ros_package/conanfile3.txt --output-folder install")
    assert "Generating CMake files for lib2 dependency" in client.out
    # Check CMake files generated
    lib2_cmake_config = os.path.join(client.current_folder, "install", "ros_package", "share",
                                     "lib2", "cmake", "lib2-config.cmake")
    assert os.path.exists(lib2_cmake_config)
    # Check lib2's transitive dependency
    lib1_cmake_config = os.path.join(client.current_folder, "install", "ros_package", "share",
                                     "lib1", "cmake", "lib1-config.cmake")
    assert os.path.exists(lib1_cmake_config)

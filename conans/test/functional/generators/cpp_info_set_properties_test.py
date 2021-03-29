import os
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def setup_client():
    client = TestClient()
    custom_generator = textwrap.dedent("""
        from conans.model import Generator
        from conans import ConanFile
        from conans.model.conan_generator import GeneratorComponentsMixin
        import textwrap
        import os

        class custom_generator(GeneratorComponentsMixin, Generator):
            @property
            def filename(self):
                return "my-generator.txt"

            def _get_components(self, pkg_name, cpp_info):
                components = super(custom_generator, self)._get_components(pkg_name, cpp_info)
                ret = []
                for comp_genname, comp, comp_requires_gennames in components:
                    ret.append("{}:{}".format(comp.name, comp_genname))
                return ret

            @property
            def content(self):
                info = []
                for pkg_name, cpp_info in self.deps_build_info.dependencies:
                    info.extend(self._get_components(pkg_name, cpp_info))
                return os.linesep.join(info)
        """)
    client.save({"custom_generator.py": custom_generator})
    client.run("config install custom_generator.py -tf generators")

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].set_property("names", "mycomponent-name")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")

    consumer = textwrap.dedent("""
        from conans import ConanFile, CMake
        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            generators = "cmake", "cmake_find_package", "custom_generator"
            requires = "mypkg/1.0"
        """)
    client.save({"consumer.py": consumer})
    return client


def test_same_results(setup_client):
    client = setup_client
    client.run("install consumer.py --build missing")
    properties_find_package = os.path.join(client.current_folder, "Findmypkg.cmake")
    properties_find_package_content = open(properties_find_package).read()
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].names["cmake_find_package"] = "mycomponent-name"
        """)
    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")
    client.run("install consumer.py")
    normal_find_package = os.path.join(client.current_folder, "Findmypkg.cmake")
    normal_find_package_content = open(normal_find_package).read()
    assert properties_find_package_content == normal_find_package_content


@pytest.mark.tool_compiler
@pytest.mark.tool_cmake
def test_custom_generator_access_properties(setup_client):
    client = setup_client()

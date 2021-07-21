import types

import pytest
from mock import Mock

from conan.tools.cmake import CMakeToolchain
from conan.tools.cmake.toolchain import Block, GenericSystemBlock
from conans import ConanFile, Settings
from conans.model.conf import Conf
from conans.model.env_info import EnvValues


@pytest.fixture
def conanfile():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "gcc"
    c.settings.compiler.libcxx = "libstdc++"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_cmake_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "Release"' in content


def test_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks.remove("generic_system")
    content = toolchain.content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_template_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].template = ""
    content = toolchain.content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_template_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"].template
    toolchain.blocks["generic_system"].template = tmp.replace("CMAKE_BUILD_TYPE", "OTHER_THING")
    content = toolchain.content
    assert 'set(OTHER_THING "Release"' in content


def test_context_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"]

    def context(self):
        assert self
        return {"build_type": "SuperRelease"}
    tmp.context = types.MethodType(context, tmp)
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_context_update(conanfile):
    toolchain = CMakeToolchain(conanfile)
    build_type = toolchain.blocks["generic_system"].values["build_type"]
    toolchain.blocks["generic_system"].values["build_type"] = "Super" + build_type
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_context_replace(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].values = {"build_type": "SuperRelease"}
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_replace_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "HelloWorld"

        def context(self):
            return {}

    toolchain.blocks["generic_system"] = MyBlock
    content = toolchain.content
    assert 'HelloWorld' in content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_add_new_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "Hello {{myvar}}!!!"

        def context(self):
            return {"myvar": "World"}

    toolchain.blocks["mynewblock"] = MyBlock
    content = toolchain.content
    assert 'Hello World!!!' in content
    assert 'CMAKE_BUILD_TYPE' in content


def test_extend_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(GenericSystemBlock):
        template = "Hello {{build_type}}!!"

        def context(self):
            c = super(MyBlock, self).context()
            c["build_type"] = c["build_type"] + "Super"
            return c

    toolchain.blocks["generic_system"] = MyBlock
    content = toolchain.content
    assert 'Hello ReleaseSuper!!' in content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_user_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["user_toolchain"].user_toolchain = "myowntoolchain.cmake"
    content = toolchain.content
    assert 'include(myowntoolchain.cmake)' in content

    toolchain = CMakeToolchain(conanfile)
    content = toolchain.content
    assert 'include(' not in content

@pytest.fixture
def conanfile_apple():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": {"Macos": {"version": ["10.15"]}},
                           "compiler": {"apple-clang": {"libcxx": ["libc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "apple-clang"
    c.settings.compiler.libcxx = "libc++"
    c.settings.os = "Macos"
    c.settings.os.version = "10.15"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c

def test_osx_deployment_target(conanfile_apple):
    toolchain = CMakeToolchain(conanfile_apple)
    content = toolchain.content
    assert 'set(CMAKE_OSX_DEPLOYMENT_TARGET 10.15)' in content

import os
import textwrap

import pytest

from conan.tools.cmake.cmakedeps.cmakedeps import FIND_MODE_CONFIG, FIND_MODE_MODULE, \
    FIND_MODE_BOTH, FIND_MODE_NONE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("cmake_find_mode", [FIND_MODE_CONFIG, FIND_MODE_MODULE,
                                             FIND_MODE_BOTH, FIND_MODE_NONE, None])
def test_reuse_with_modules_and_config(cmake_find_mode):
    t = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            def package_info(self):
                {}
        """)

    if cmake_find_mode is not None:
        s = 'self.cpp_info.set_property("cmake_find_mode", "{}")'.format(cmake_find_mode)
        conanfile = conanfile.format(s)
    t.save({"conanfile.py": conanfile})
    t.run("create . --name=mydep --version=1.0")

    conanfile = GenConanfile().with_name("myapp").with_require("mydep/1.0")\
                                                 .with_generator("CMakeDeps")\
                                                 .with_settings("build_type", "os", "arch")
    t.save({"conanfile.py": conanfile})

    t.run("install . --output-folder=install -s os=Linux -s compiler=gcc -s compiler.version=6 "
          "-s compiler.libcxx=libstdc++11")

    def exists_config():
        return os.path.exists(os.path.join(t.current_folder, "install", "mydep-config.cmake"))

    def exists_module():
        return os.path.exists(os.path.join(t.current_folder, "install", "Findmydep.cmake"))

    if cmake_find_mode == FIND_MODE_CONFIG or cmake_find_mode is None:
        # None is default "config"
        assert exists_config()
        assert not exists_module()
    elif cmake_find_mode == FIND_MODE_MODULE:
        assert not exists_config()
        assert exists_module()
    elif cmake_find_mode == FIND_MODE_BOTH:
        assert exists_config()
        assert exists_module()
    elif cmake_find_mode == FIND_MODE_NONE:
        assert not exists_config()
        assert not exists_module()

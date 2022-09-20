import os
import textwrap

import pytest

from conan.tools.cmake.cmakedeps.cmakedeps import FIND_MODE_CONFIG, FIND_MODE_MODULE, FIND_MODE_BOTH, \
    FIND_MODE_NONE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("cmake_find_mode", [FIND_MODE_CONFIG, FIND_MODE_MODULE,
                                             FIND_MODE_BOTH, FIND_MODE_NONE, None])
def test_reuse_with_modules_and_config(cmake_find_mode):
    t = TestClient()
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Conan(ConanFile):
                name = "mydep"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"

                def package_info(self):
                    {}

            """)

    if cmake_find_mode is not None:
        s = 'self.cpp_info.set_property("cmake_find_mode", "{}")'.format(cmake_find_mode)
        conanfile = conanfile.format(s)
    t.save({"conanfile.py": conanfile})
    t.run("create .")

    conanfile = GenConanfile().with_name("myapp").with_require("mydep/1.0")\
                                                 .with_generator("CMakeDeps")\
                                                 .with_settings("build_type", "os", "arch", "compiler")
    t.save({"conanfile.py": conanfile})

    t.run("install . -if=install")

    ifolder = os.path.join(t.current_folder, "install")

    def exists_config(ifolder):
        return os.path.exists(os.path.join(ifolder, "mydep-config.cmake"))

    def exists_module(ifolder):
        return os.path.exists(os.path.join(ifolder, "Findmydep.cmake"))

    if cmake_find_mode == FIND_MODE_CONFIG or cmake_find_mode is None:
        # None is default "config"
        assert exists_config(ifolder)
        assert not exists_module(ifolder)
    elif cmake_find_mode == FIND_MODE_MODULE:
        assert not exists_config(ifolder)
        assert exists_module(ifolder)
    elif cmake_find_mode == FIND_MODE_BOTH:
        assert exists_config(ifolder)
        assert exists_module(ifolder)
    elif cmake_find_mode == FIND_MODE_NONE:
        assert not exists_config(ifolder)
        assert not exists_module(ifolder)

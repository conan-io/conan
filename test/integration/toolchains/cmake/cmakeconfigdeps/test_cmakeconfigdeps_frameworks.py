import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_package_framework_needs_location():
    conanfile = textwrap.dedent(f"""
    import os
    from conan import ConanFile

    class MyFramework(ConanFile):
        name = "frame"
        version = "1.0"
        settings = "os", "arch", "compiler", "build_type"
        package_type = 'static-library'

        def package_info(self):
            self.cpp_info.type = 'static-library'
            self.cpp_info.package_framework = "MyFramework"
    """)
    test_conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile

    class LibTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "CMakeConfigDeps", "CMakeToolchain"

        def requirements(self):
            self.requires(self.tested_reference_str)
    """)
    client = TestClient()
    client.save({
        'test_package/conanfile.py': test_conanfile,
        'conanfile.py': conanfile
    })
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value}", assert_error=True)
    assert "Error in generator 'CMakeConfigDeps': cpp_info.location missing for framework MyFramework" in client.out


def test_framework_only_component_generates_target():
    conanfile = textwrap.dedent(f"""
    import os
    from conan import ConanFile

    class MyFramework(ConanFile):
        name = "frame"
        version = "1.0"
        settings = "os", "arch", "compiler", "build_type"

        def package_info(self):
            self.cpp_info.frameworks = ["MyFramework"]
            self.cpp_info.libdirs = []
            self.cpp_info.includedirs = []
    """)

    tc = TestClient()
    tc.save({"conanfile.py": conanfile})
    tc.run("create .")
    tc.run(f"install --requires=frame/1.0 -g CMakeConfigDeps -c=tools.cmake.cmakedeps:new={new_value}")
    targets = tc.load("frame-Targets-release.cmake")
    assert "add_library(frame::frame INTERFACE IMPORTED)" in targets

import textwrap

from conan.test.utils.tools import TestClient


def test_profile_tool_requires_host_context_not_in_path_for_transitive():
    """
    test for https://github.com/conan-io/conan/issues/20165
    """
    tc = TestClient()

    bbb_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os, platform

        class mypkgRecipe(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            package_type = "application"
            name = "bbb"
            version = "1.0"

            def package(self):
                bin_dir = os.path.join(self.package_folder, "bin")
                os.makedirs(bin_dir, exist_ok=True)
                if platform.system() == "Windows":
                    script = "@echo off\\necho Im am bbb\\n"
                    path = os.path.join(bin_dir, "bbb.bat")
                else:
                    script = "#!/bin/bash\\necho 'Im am bbb'\\n"
                    path = os.path.join(bin_dir, "bbb")
                save(self, path, script)
                os.chmod(path, 0o755)
    """)

    aaa_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os, platform, textwrap

        class mypkgRecipe(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            package_type = "application"
            name = "aaa"
            version = "1.0"

            def build(self):
                self.run("bbb")

            def package(self):
                bin_dir = os.path.join(self.package_folder, "bin")
                os.makedirs(bin_dir, exist_ok=True)
                if platform.system() == "Windows":
                    script = "@echo off\\necho Im am aaa\\n"
                    path = os.path.join(bin_dir, "aaa.bat")
                else:
                    script = "#!/bin/bash\\necho 'Im am aaa'\\n"
                    path = os.path.join(bin_dir, "aaa")
                save(self, path, script)
                os.chmod(path, 0o755)
    """)

    ccc_conanfile = textwrap.dedent("""
        from conan import ConanFile

        class mypkgRecipe(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            package_type = "application"
            name = "ccc"
            version = "1.0"

            def build_requirements(self):
                self.tool_requires("aaa/1.0")
    """)

    profile = textwrap.dedent("""
        include(default)

        {% if context == "host" %}
        [tool_requires]
        bbb/1.0
        {% endif %}
    """)

    tc.save({
        "b/conanfile.py": bbb_conanfile,
        "a/conanfile.py": aaa_conanfile,
        "c/conanfile.py": ccc_conanfile,
        "myprofile": profile,
    })

    tc.run("create b -pr=myprofile")
    assert "bbb/1.0" in tc.out

    tc.run("create a -pr=myprofile")
    assert "Im am bbb" in tc.out

    # Remove the binary of aaa but keep its recipe
    tc.run("remove 'aaa:*' -c")

    tc.run("create c -pr=myprofile --build=missing")
    assert "Im am bbb" in tc.out

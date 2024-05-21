import textwrap

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import load, save


def test_legacy_names_filenames():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.components["comp"].names["cmake_find_package"] = "hello"
                self.cpp_info.components["comp"].names["cmake_find_package_multi"] = "hello"
                self.cpp_info.components["comp"].build_modules["cmake_find_package"] = ["nice_rel_path"]
                self.cpp_info.components["comp"].build_modules["cmake_find_package"].append("some_file_name")
                self.cpp_info.components["comp"].build_modules["cmake_find_package_multi"] = ["nice_rel_path"]

                self.cpp_info.names["cmake_find_package"] = "absl"
                self.cpp_info.names["cmake_find_package_multi"] = "absl"
                self.cpp_info.filenames["cmake_find_package"] = "tensorflowlite"
                self.cpp_info.filenames["cmake_find_package_multi"] = "tensorflowlite"
                self.cpp_info.build_modules["cmake_find_package"] = ["nice_rel_path"]
                self.cpp_info.build_modules["cmake_find_package_multi"] = ["nice_rel_path"]

                self.env_info.whatever = "whatever-env_info"
                self.env_info.PATH.append("/path/to/folder")
                self.user_info.whatever = "whatever-user_info"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    for name in ["cpp_info.names", "cpp_info.filenames", "env_info", "user_info", "cpp_info.build_modules"]:
        assert f"WARN: deprecated:     '{name}' used in: pkg/1.0" in c.out

    save(c.cache.new_config_path, 'core:skip_warnings=["deprecated"]')
    c.run("create .")
    for name in ["cpp_info.names", "cpp_info.filenames", "env_info", "user_info",
                 "cpp_info.build_modules"]:
        assert f"'{name}' used in: pkg/1.0" not in c.out


class TestLegacy1XRecipes:
    def test_legacy_imports(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
            """)
        c.save({"pkg/conanfile.py": conanfile,
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("pkg/1.0")})
        # With EDITABLE, we can emulate errors without exporting
        c.run("export pkg")
        layout = c.get_latest_ref_layout(RecipeReference.loads("pkg/1.0"))
        conanfile = layout.conanfile()
        content = load(conanfile)
        content = content.replace("from conan", "from conans")
        save(conanfile, content)
        c.run("install app", assert_error=True)
        assert "Recipe 'pkg/1.0' seems broken." in c.out
        assert "It is possible that this recipe is not Conan 2.0 ready" in c.out


import textwrap

from conans.test.utils.tools import TestClient


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
                self.cpp_info.components["comp"].build_modules["cmake_find_package_multi"] = ["nice_rel_path"]

                self.cpp_info.names["cmake_find_package"] = "absl"
                self.cpp_info.names["cmake_find_package_multi"] = "absl"
                self.cpp_info.filenames["cmake_find_package"] = "tensorflowlite"
                self.cpp_info.filenames["cmake_find_package_multi"] = "tensorflowlite"
                self.cpp_info.build_modules["cmake_find_package"] = ["nice_rel_path"]
                self.cpp_info.build_modules["cmake_find_package_multi"] = ["nice_rel_path"]

                self.env_info.whatever = "whatever-env_info"
                self.user_info.whatever = "whatever-user_info"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    message = "WARN: The use of '{}' is deprecated in Conan 2.0 and will be removed in " \
              "Conan 2.X. Please, update your recipes unless you are maintaining compatibility " \
              "with Conan 1.X"

    for name in ["cpp_info.names", "cpp_info.filenames", "env_info", "user_info", "cpp_info.build_modules"]:
        assert message.format(name) in c.out

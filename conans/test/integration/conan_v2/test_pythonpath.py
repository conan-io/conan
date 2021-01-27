import textwrap

from conans.model.ref import ConanFileReference
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase
import six

class PythonBuildTest(ConanV2ModeTestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class ConanToolPackage(ConanFile):
            name = "conantool"
            version = "1.0"
            exports = "*"
            build_policy = "missing"

            def package(self):
                self.copy("*")

            def package_info(self):
                self.env_info.PYTHONPATH.append(self.package_folder)
        """)

    tooling = textwrap.dedent("""
        def bar(output):
            output.info("Hello Bar")
        """)

    reuse = textwrap.dedent("""
        from conans import ConanFile, tools

        class ToolsTest(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "conantool/1.0@conan/stable"

            def build(self):
                pythonpath = self.deps_env_info["conantool"].PYTHONPATH
                ppath = [it.replace("\\\\", "/") for it in pythonpath]
                self.output.info("PYTHONPATH: {}".format(ppath))

            def package_info(self):
                import tooling
                tooling.bar(self.output)
        """)

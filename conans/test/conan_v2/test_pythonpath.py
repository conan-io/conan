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

    def test_deprecate_pythonpath(self):
        conantool_ref = ConanFileReference.loads("conantool/1.0@conan/stable")
        # Create a package that exports python code
        t = self.get_client()
        t.save({'conanfile.py': self.conanfile,
                'tooling.py': self.tooling})
        t.run("export . conan/stable")

        # Try to reuse it
        t.save({'conanfile.py': self.reuse}, clean_first=True)
        t.run("create .", assert_error=True)
        packages_path = t.cache.package_layout(conantool_ref).packages().replace('\\', '/')
        self.assertIn("consumer/0.1: PYTHONPATH: ['{}".format(packages_path), t.out)
        if six.PY2:
            self.assertIn("ImportError: No module named tooling", t.out)
        else:
            self.assertIn("ModuleNotFoundError: No module named 'tooling'", t.out)

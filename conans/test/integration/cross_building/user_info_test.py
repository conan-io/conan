import textwrap
import unittest

from conans.test.utils.tools import TestClient


class UserInfoTestCase(unittest.TestCase):
    """ When using several contexts (xbuild feature) the user information from each of the
        contexts should be accessible, Conan will provide 'deps_user_info' attribute to access
        information from the 'host' context (like it is doing with 'deps_cpp_info'), but
        information from other contexts will be accessible via attributes 'user_info_<context>'.
    """

    library = textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            name = "library"
            settings = "os"

            def package_info(self):
                self.user_info.DATA = "{}-{}".format(self.name, self.settings.os)
    """)

    br = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            settings = "os"

            requires = "library/1.0"

            def package_info(self):
                self.user_info.DATA = "{}-{}".format(self.name, self.settings.os)
    """)

    app = textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            name = "app"
            settings = "os"

            def requirements(self):
                self.requires("library/1.0")

            def build_requirements(self):
                self.build_requires("br_build/1.0")
                self.build_requires("br_host/1.0", force_host_context=True)

            def build(self):
                _info = self.output.info
                _info("[deps] {}".format(', '.join(sorted(self.deps_user_info.keys()))))
                _info("[deps] library.DATA={}".format(self.deps_user_info["library"].DATA))
                _info("[deps] br_host.DATA={}".format(self.deps_user_info["br_host"].DATA))

                _info("[build] {}".format(', '.join(sorted(self.user_info_build.keys()))))
                _info("[build] library.DATA={}".format(self.user_info_build["library"].DATA))
                _info("[build] br_build.DATA={}".format(self.user_info_build["br_build"].DATA))
    """)

    @classmethod
    def setUpClass(cls):
        super(UserInfoTestCase, cls).setUpClass()
        cls.t = TestClient()
        cls.t.save({'library.py': cls.library,
                    'build_requires.py': cls.br,
                    'app.py': cls.app,
                    'host': '[settings]\nos=Windows',
                    'build': '[settings]\nos=Linux', })
        cls.t.run("create library.py library/1.0@ --profile=host")
        cls.t.run("create library.py library/1.0@ --profile=build")
        cls.t.run("create build_requires.py br_host/1.0@ --profile=host")
        cls.t.run("create build_requires.py br_build/1.0@ --profile=build")

    def _check_user_info_data(self, app_scope, output):
        # Check information from the host context (using deps_user_info attribute)
        self.assertIn(app_scope + ": [deps] br_host, library", output)
        self.assertIn(app_scope + ": [deps] library.DATA=library-Windows", output)
        self.assertIn(app_scope + ": [deps] br_host.DATA=br_host-Windows", output)

        # Check information from the build context (using user_info_build attribute)
        self.assertIn(app_scope + ": [build] br_build, library", output)
        self.assertIn(app_scope + ": [build] library.DATA=library-Linux", output)
        self.assertIn(app_scope + ": [build] br_build.DATA=br_build-Linux", output)

    def test_user_info_from_requirements(self):
        self.t.run("create app.py app/1.0@ --profile:host=host --profile:build=build")
        self._check_user_info_data("app/1.0", self.t.out)

    def test_user_info_local_workflow(self):
        self.t.run("install app.py app/1.0@ --profile:host=host --profile:build=build")
        self.t.run("build app.py")
        self._check_user_info_data("app.py (app/1.0)", self.t.out)

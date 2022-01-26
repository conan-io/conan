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
        from conan import ConanFile

        class Library(ConanFile):
            name = "library"
            settings = "os"

            def package_info(self):
                self.user_info.DATA = "{}-{}".format(self.name, self.settings.os)
    """)

    br = textwrap.dedent("""
        from conan import ConanFile

        class BuildRequires(ConanFile):
            settings = "os"

            requires = "library/1.0"

            def package_info(self):
                self.user_info.DATA = "{}-{}".format(self.name, self.settings.os)
    """)

    # FIXME: Commented build_requires, interface not defined yet
    app = textwrap.dedent("""
        from conan import ConanFile

        class Library(ConanFile):
            name = "app"
            settings = "os"

            def requirements(self):
                self.requires("library/1.0")

            def build_requirements(self):
                self.build_requires("br_build/1.0")
                self.test_requires("br_host/1.0")

            def build(self):
                _info = self.output.info
                lib_info = self.dependencies["library"].user_info
                br_host_info = self.dependencies["br_host"].user_info
                _info("[deps] library.DATA={}".format(lib_info.DATA))
                _info("[deps] br_host.DATA={}".format(br_host_info.DATA))

                # lib_info = self.dependencies.build["library"].user_info
                # br_build = self.dependencies.build["br_build"].user_info

                #_info("[build] library.DATA={}".format(lib_info.DATA))
                #_info("[build] br_build.DATA={}".format(br_build.DATA))
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
        cls.t.run("create library.py --name=library --version=1.0 --profile=host")
        cls.t.run("create library.py --name=library --version=1.0 --profile=build")
        cls.t.run("create build_requires.py --name=br_host --version=1.0 --profile=host")
        cls.t.run("create build_requires.py --name=br_build --version=1.0 --profile=build")

    def _check_user_info_data(self, app_scope, output):
        # Check information from the host context (using deps_user_info attribute)
        self.assertIn(app_scope + ": [deps] library.DATA=library-Windows", output)
        self.assertIn(app_scope + ": [deps] br_host.DATA=br_host-Windows", output)

        # Check information from the build context (using user_info_build attribute)
        #self.assertIn(app_scope + ": [build] br_build, library", output)
        #self.assertIn(app_scope + ": [build] library.DATA=library-Linux", output)
        #self.assertIn(app_scope + ": [build] br_build.DATA=br_build-Linux", output)

    def test_user_info_from_requirements(self):
        self.t.run("create app.py --name=app --version=1.0 --profile:host=host --profile:build=build")
        self._check_user_info_data("app/1.0", self.t.out)

    def test_user_info_local_workflow(self):
        self.t.run("build app.py --name=app --version=1.0 --profile:host=host --profile:build=build")
        self._check_user_info_data("app.py (app/1.0)", self.t.out)

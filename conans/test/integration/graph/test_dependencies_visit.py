import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_dependencies_visit():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . openssl/0.1@")
    client.run("create . openssl/0.2@")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.2")})
    client.run("create . cmake/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/0.1"
            build_requires = "cmake/0.1"

            def generate(self):
                dep = self.dependencies["openssl"]
                self.output.info("DefRef: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRef: {}!!!".format(repr(dep.pref)))
                dep = self.dependencies.build["openssl"]
                self.output.info("DefRefBuild: {}!!!".format(repr(dep.ref)))
                self.output.info("DefPRefBuild: {}!!!".format(repr(dep.pref)))
                for r, d in self.dependencies.build.items():
                    self.output.info("DIRECTBUILD {}: {}".format(r.direct, d))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows")  # Use 2 contexts
    assert "DefRef: openssl/0.1#f3367e0e7d170aa12abccb175fee5f97!!!" in client.out
    assert "DefPRef: openssl/0.1#f3367e0e7d170aa12abccb175fee5f97:"\
           "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"\
           "83c38d3b4e5f1b8450434436eec31b00!!!" in client.out

    assert "DefRefBuild: openssl/0.2#f3367e0e7d170aa12abccb175fee5f97!!!" in client.out
    assert "DefPRefBuild: openssl/0.2#f3367e0e7d170aa12abccb175fee5f97:" \
           "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#" \
           "83c38d3b4e5f1b8450434436eec31b00!!!" in client.out

    assert "conanfile.py: DIRECTBUILD True: cmake/0.1" in client.out
    assert "conanfile.py: DIRECTBUILD False: openssl/0.2" in client.out


def test_dependencies_visit_settings_options():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_settings("os").
                with_option("shared", [True, False]).with_default_option("shared", False)})
    client.run("create . openssl/0.1@ -s os=Linux")
    client.save({"conanfile.py": GenConanfile().with_requires("openssl/0.1")})
    client.run("create . pkg/0.1@  -s os=Linux")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "pkg/0.1"

            def generate(self):
                dep = self.dependencies["openssl"]
                self.output.info("SETTINGS: {}!".format(dep.settings.os))
                self.output.info("OPTIONS: shared={}!".format(dep.options.shared))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s os=Linux")
    assert "conanfile.py: SETTINGS: Linux!" in client.out
    assert "conanfile.py: OPTIONS: shared=False!" in client.out


def test_dependencies_visit_build_requires_profile():
    """ At validate() time, in Conan 1.X, the build-requires are not available yet, because first
    the binary package_id is computed, then the build-requires are resolved.
    It is necessary to avoid in Conan 1.X the caching of the ConanFile.dependencies, because
    at generate() time it will have all the graph info, including build-requires
    """
    # https://github.com/conan-io/conan/issues/10304
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . cmake/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):

            def validate(self):
                self.output.info("VALIDATE DEPS: {}!!!".format(len(self.dependencies.items())))

            def generate(self):
                for req, dep in self.dependencies.items():
                    self.output.info("GENERATE REQUIRE: {}!!!".format(dep.ref))
                dep = self.dependencies.build["cmake"]
                self.output.info("GENERATE CMAKE: {}!!!".format(dep.ref))
        """)
    client.save({"conanfile.py": conanfile,
                 "profile": "[build_requires]\ncmake/0.1"})
    client.run("install . -pr:b=default -pr:h=profile --build")  # Use 2 contexts
    # Validate time, build-requires not available yet
    assert "conanfile.py: VALIDATE DEPS: 0!!!" in client.out
    # generate time, build-requires already available
    assert "conanfile.py: GENERATE REQUIRE: cmake/0.1!!!" in client.out
    assert "conanfile.py: GENERATE CMAKE: cmake/0.1!!!" in client.out


def test_dependency_interface():
    """
    Quick test for the ConanFileInterface exposed
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "1.0"
            homepage = "myhome"
            url = "myurl"
            license = "MIT"
        """)
    user = textwrap.dedent("""
        from conan import ConanFile
        class User(ConanFile):
            requires = "dep/1.0"
            def generate(self):
                self.output.info("HOME: {}".format(self.dependencies["dep"].homepage))
                self.output.info("URL: {}".format(self.dependencies["dep"].url))
                self.output.info("LICENSE: {}".format(self.dependencies["dep"].license))
                self.output.info("RECIPE: {}".format(self.dependencies["dep"].recipe_folder))
                self.output.info("CONANDATA: {}".format(self.dependencies["dep"].conan_data))

            """)
    c.save({"dep/conanfile.py": conanfile,
            "dep/conandata.yml": "",
            "user/conanfile.py": user})
    c.run("create dep")
    c.run("install user")
    assert "conanfile.py: HOME: myhome" in c.out
    assert "conanfile.py: URL: myurl" in c.out
    assert "conanfile.py: LICENSE: MIT" in c.out
    assert "conanfile.py: RECIPE:" in c.out
    assert "conanfile.py: CONANDATA: {}" in c.out

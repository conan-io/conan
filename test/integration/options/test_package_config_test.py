import pytest

from conan.test.utils.tools import TestClient

test_conanfile = """from conan import ConanFile

class Test(ConanFile):
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def requirements(self):
        self.requires(self.tested_reference_str)
        self.output.info("shared (requirements): %s" % (self.options.shared))

    def configure(self):
        self.output.info("shared (configure): %s" % (self.options.shared))

    def build(self):
        self.output.info("shared (build): %s" % (self.options.shared))

    def test(self):
        self.output.info("shared (test): %s" % (self.options.shared))
"""


dep = """from conan import ConanFile

class PkgConan(ConanFile):
    name = "dep"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def configure(self):
        self.output.info("shared (configure): %s" % str(self.options.shared))

    def requirements(self):
        self.output.info("shared (requirements): %s" % str(self.options.shared))

    def build(self):
        self.output.info("shared (build): %s" % str(self.options.shared))
"""


conanfile = """from conan import ConanFile

class PkgConan(ConanFile):
    name = "pkg"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def configure(self):
        self.output.info("shared (configure): %s" % str(self.options.shared))

    def requirements(self):
        self.requires("dep/0.1")
        self.output.info("shared (requirements): %s" % str(self.options.shared))

    def build(self):
        self.output.info("shared (build): %s" % str(self.options.shared))
"""


class TestPackageOptionsCreate:

    def test_test_package(self):
        """ non scoped options will be put in the package scope
        -o shared=True <=> -o pkg:shared=True
        """
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile,
                "test_package/conanfile.py": test_conanfile})
        c.run("export dep")
        c.run("create . -o shared=True --build=missing")

        assert "dep/0.1: shared (configure): False" in c.out
        assert "dep/0.1: shared (requirements): False" in c.out
        assert "dep/0.1: shared (build): False" in c.out

        assert "pkg/0.1: shared (configure): True" in c.out
        assert "pkg/0.1: shared (requirements): True" in c.out
        assert "pkg/0.1: shared (build): True" in c.out

        assert "pkg/0.1 (test package): shared (configure): False" in c.out
        assert "pkg/0.1 (test package): shared (requirements): False" in c.out
        assert "pkg/0.1 (test package): shared (build): False" in c.out
        assert "pkg/0.1 (test package): shared (test): False" in c.out

    def test_test_package_all_shared(self):
        """
        all shared should affect both the package and the test_package
        """
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile,
                "test_package/conanfile.py": test_conanfile})
        c.run("export dep")
        c.run("create . -o *:shared=True --build=missing")

        assert "dep/0.1: shared (configure): True" in c.out
        assert "dep/0.1: shared (requirements): True" in c.out
        assert "dep/0.1: shared (build): True" in c.out

        assert "pkg/0.1: shared (configure): True" in c.out
        assert "pkg/0.1: shared (requirements): True" in c.out
        assert "pkg/0.1: shared (build): True" in c.out

        assert "pkg/0.1 (test package): shared (configure): True" in c.out
        assert "pkg/0.1 (test package): shared (requirements): True" in c.out
        assert "pkg/0.1 (test package): shared (build): True" in c.out
        assert "pkg/0.1 (test package): shared (test): True" in c.out

    def test_test_package_consumers(self):
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile,
                "test_package/conanfile.py": test_conanfile})
        c.run("export dep")
        c.run("create . -o &:shared=True --build=missing")

        assert "dep/0.1: shared (configure): False" in c.out
        assert "dep/0.1: shared (requirements): False" in c.out
        assert "dep/0.1: shared (build): False" in c.out

        assert "pkg/0.1: shared (configure): True" in c.out
        assert "pkg/0.1: shared (requirements): True" in c.out
        assert "pkg/0.1: shared (build): True" in c.out

        assert "pkg/0.1 (test package): shared (configure): True" in c.out
        assert "pkg/0.1 (test package): shared (requirements): True" in c.out
        assert "pkg/0.1 (test package): shared (build): True" in c.out
        assert "pkg/0.1 (test package): shared (test): True" in c.out

        c.run("install --requires=dep/0.1 -o &:shared=True -b=missing")
        assert "dep/0.1: shared (configure): True" in c.out
        assert "dep/0.1: shared (requirements): True" in c.out
        assert "dep/0.1: shared (build): True" in c.out

    def test_test_package_non_consumers(self):
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile,
                "test_package/conanfile.py": test_conanfile})
        c.run("export dep")
        c.run("create . -o !&:shared=True --build=missing")

        assert "dep/0.1: shared (configure): True" in c.out
        assert "dep/0.1: shared (requirements): True" in c.out
        assert "dep/0.1: shared (build): True" in c.out

        assert "pkg/0.1: shared (configure): False" in c.out
        assert "pkg/0.1: shared (requirements): False" in c.out
        assert "pkg/0.1: shared (build): False" in c.out

        assert "pkg/0.1 (test package): shared (configure): False" in c.out
        assert "pkg/0.1 (test package): shared (requirements): False" in c.out
        assert "pkg/0.1 (test package): shared (build): False" in c.out
        assert "pkg/0.1 (test package): shared (test): False" in c.out

    def test_test_package_only(self):
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile,
                "test_package/conanfile.py": test_conanfile})
        c.run("export dep")
        c.run("create . -o &:shared=True -o shared=False --build=missing")

        assert "dep/0.1: shared (configure): False" in c.out
        assert "dep/0.1: shared (requirements): False" in c.out
        assert "dep/0.1: shared (build): False" in c.out

        assert "pkg/0.1: shared (configure): False" in c.out
        assert "pkg/0.1: shared (requirements): False" in c.out
        assert "pkg/0.1: shared (build): False" in c.out

        assert "pkg/0.1 (test package): shared (configure): True" in c.out
        assert "pkg/0.1 (test package): shared (requirements): True" in c.out
        assert "pkg/0.1 (test package): shared (build): True" in c.out
        assert "pkg/0.1 (test package): shared (test): True" in c.out


class TestPackageOptionsInstall:

    @pytest.mark.parametrize("pattern", ["", "*:", "&:"])
    def test_test_package(self, pattern):
        c = TestClient()
        c.save({"dep/conanfile.py": dep,
                "conanfile.py": conanfile})
        c.run("export dep")
        c.run(f"build . -o {pattern}shared=True --build=missing")

        dep_shared = "False" if "*" not in pattern else "True"
        assert f"dep/0.1: shared (configure): {dep_shared}" in c.out
        assert f"dep/0.1: shared (requirements): {dep_shared}" in c.out
        assert f"dep/0.1: shared (build): {dep_shared}" in c.out

        assert "conanfile.py (pkg/0.1): shared (configure): True" in c.out
        assert "conanfile.py (pkg/0.1): shared (requirements): True" in c.out
        assert "conanfile.py (pkg/0.1): shared (build): True" in c.out

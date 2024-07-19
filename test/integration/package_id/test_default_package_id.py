import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("typedep, typeconsumer, different_id",
                         [("header-library", "application", False),
                          ("header-library", "shared-library", False),
                          ("header-library", "static-library", False),
                          ("static-library", "application", True),
                          ("static-library", "shared-library", True),
                          ("static-library", "header-library", False),
                          ("static-library", "static-library", False),
                          ("shared-library", "header-library", False),
                          ("shared-library", "static-library", False),
                          ("shared-library", "shared-library", False),
                          ("shared-library", "application", False)
                          ])
def test_default_package_id_options(typedep, typeconsumer, different_id):
    """ test that some consumer package ids are changed when the dependency change one of its
    options
    """
    c = TestClient(light=True)
    dep = GenConanfile("dep", "0.1").with_option("myopt", [True, False]) \
        .with_package_type(typedep).with_class_attribute('implements = ["auto_shared_fpic", "auto_header_only"]')
    consumer = GenConanfile("consumer", "0.1").with_requires("dep/0.1")\
        .with_package_type(typeconsumer).with_class_attribute('implements = ["auto_shared_fpic", "auto_header_only"]')

    c.save({"dep/conanfile.py": dep,
            "consumer/conanfile.py": consumer})
    c.run("create dep -o dep/*:myopt=True")
    pid1 = c.created_package_id("dep/0.1")
    c.run("create dep -o dep/*:myopt=False")
    pid2 = c.created_package_id("dep/0.1")
    if typedep != "header-library":
        assert pid1 != pid2

    c.run("create consumer -o dep/*:myopt=True")
    pid1 = c.created_package_id("consumer/0.1")
    c.run("create consumer -o dep/*:myopt=False")
    pid2 = c.created_package_id("consumer/0.1")
    if different_id:
        assert pid1 != pid2
    else:
        assert pid1 == pid2


@pytest.mark.parametrize("typedep, versiondep, typeconsumer, different_id",
                         [("static-library", "1.1", "header-library", False),
                          ("static-library", "1.0.1", "static-library", False),
                          ("static-library", "1.1", "static-library", True),
                          ("shared-library", "1.1", "header-library", False),
                          ("shared-library", "1.0.1", "static-library", False),
                          ("shared-library", "1.1", "static-library", True),
                          ("shared-library", "1.0.1", "shared-library", False),
                          ("shared-library", "1.1", "shared-library", True),
                          ("shared-library", "1.0.1", "application", False),
                          ("shared-library", "1.1", "application", True),
                          ("application", "2.1", "application", False),
                          ])
def test_default_package_id_versions(typedep, versiondep, typeconsumer, different_id):
    """ test that some consumer package ids are changed when the dependency changes its version
    """
    c = TestClient(light=True)
    dep = GenConanfile("dep").with_package_type(typedep)
    consumer = GenConanfile("consumer", "0.1").with_requires("dep/[>0.0]") \
        .with_package_type(typeconsumer)
    c.save({"dep/conanfile.py": dep,
            "consumer/conanfile.py": consumer})
    c.run("create dep --version=1.0")
    c.run("create consumer")
    pid1 = c.created_package_id("consumer/0.1")

    c.run(f"create dep --version={versiondep}")
    c.run("create consumer")
    pid2 = c.created_package_id("consumer/0.1")
    if different_id:
        assert pid1 != pid2
    else:
        assert pid1 == pid2

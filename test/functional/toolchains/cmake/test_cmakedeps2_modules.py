from conan.test.utils.tools import TestClient, GenConanfile


def test_create_consume_module():

    # main ->   mod   -> dep/1.0
    #      -> dep/2.0
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile("dep", "1.0").with_generator("CMakeDeps").with_settings("build_type").with_package_type("shared-library")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    tc.save({"conanfile.py": GenConanfile("dep", "2.0").with_generator("CMakeDeps").with_settings("build_type").with_package_type("shared-library")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    tc.save({"conanfile.py": GenConanfile("mod", "1.0").with_requirement("dep/1.0").with_package_type("module").with_generator("CMakeDeps").with_settings("build_type")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    conanfile = GenConanfile("main", "1.0").with_requirement("dep/2.0").with_requirement("mod/1.0").with_generator("CMakeDeps").with_settings("build_type")
    tc.save({"conanfile.py": conanfile})
    tc.run("graph info . -f=json")
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .',assert_error=True)
    assert True

def test_help():
    a = """
from conan import ConanFile
class MyModule(ConanFile):
    name = 'mod'
    version = '1.0'
    package_type = 'module'
    generators = "CMakeDeps"

    def requirements(self):
        self.requires("dep/1.0", visible=False)
    settings = "build_type"
    """
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile("dep", "1.0").with_generator("CMakeDeps").with_settings("build_type")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    tc.save({"conanfile.py": a})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    assert False


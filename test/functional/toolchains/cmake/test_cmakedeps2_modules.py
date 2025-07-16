from conan.test.utils.tools import TestClient, GenConanfile
import textwrap

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
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .', assert_error=True) #Not valid
    assert "ERROR: Version conflict: Conflict between dep/1.0 and dep/2.0 in the graph." in tc.out #TODO FIX THIS TEST
    assert False

def test_skip_binaries():
    c = TestClient(default_server_user=True)
    pkg1 = GenConanfile("module_dep", "1.0").with_generator("CMakeDeps").with_settings("build_type").with_package_type("module").with_class_attribute('upload_policy = "skip"')
    pkg2 = GenConanfile("module", "1.0").with_generator("CMakeDeps").with_settings("build_type").with_package_type("module").with_requirement("module_dep/1.0", visible=False)
    pkg3 = GenConanfile("main", "1.0").with_generator("CMakeDeps").with_settings("build_type").with_requirement("module/1.0")
    c.save({"module_dep/conanfile.py": pkg1,
            "module/conanfile.py": pkg2,
            "main/conanfile.py": pkg3,
            })
    c.run("create module_dep")
    c.run("create module")
    c.run("remove module_dep/*:* -c")  # remove binaries
    c.run("create main --build=missing")
    assert r"Skipped binaries(\s*)module_dep/1.0" in  c.out

def test_modules_package_id():
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile("mod1", "1.0").with_package_type("module").with_generator("CMakeDeps").with_settings("build_type")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    conanfile = GenConanfile("main", "1.0").with_requirement("mod1/1.0").with_generator("CMakeDeps").with_settings("build_type")
    tc.save({"conanfile.py": conanfile})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    package_id_1 = tc.created_package_id("main/1.0")

    tc.run("remove main/*:* -c")

    tc.save({"conanfile.py": GenConanfile("mod2", "1.0").with_package_type("module").with_generator(
        "CMakeDeps").with_settings("build_type")})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    conanfile = GenConanfile("main", "1.0").with_requirement("mod2/1.0").with_generator(
        "CMakeDeps").with_settings("build_type")
    tc.save({"conanfile.py": conanfile})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" .')
    package_id_2 = tc.created_package_id("main/1.0")
    assert package_id_1 == package_id_2

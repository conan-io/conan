from conan.test.utils.tools import TestClient, GenConanfile
import re


def test_module_conflict_half_diamond():
    # main ->   mod   -> dep/1.0
    #      -> dep/2.0
    tc = TestClient()
    dep_1 = GenConanfile("dep", "1.0").with_generator("CMakeDeps").with_settings(
        "build_type").with_package_type("shared-library")
    dep_2 = GenConanfile("dep", "2.0").with_generator("CMakeDeps").with_settings(
        "build_type").with_package_type("shared-library")
    module = GenConanfile("mod", "1.0").with_requirement(
        "dep/1.0").with_package_type("module").with_generator("CMakeDeps").with_settings(
        "build_type")
    main = GenConanfile("main", "1.0").with_requirement("dep/2.0").with_requirement(
        "mod/1.0").with_generator("CMakeDeps").with_settings("build_type")
    tc.save({"dep_1/conanfile.py": dep_1,
             "dep_2/conanfile.py": dep_2,
             "module/conanfile.py": module,
             "main/conanfile.py": main})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" dep_1')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" dep_2')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" module')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" main', assert_error=True)
    assert "ERROR: Version conflict: Conflict between dep/1.0 and dep/2.0 in the graph." in tc.out


def test_create_consume_module_full_diamond():
    # main ->   mod1   -> dep/1.0
    #      ->   mod2   -> dep/2.0
    tc = TestClient()
    dep_1 = GenConanfile("dep", "1.0").with_generator("CMakeDeps").with_settings(
        "build_type").with_package_type("shared-library")
    dep_2 = GenConanfile("dep", "2.0").with_generator("CMakeDeps").with_settings(
        "build_type").with_package_type("shared-library")
    mod1 = GenConanfile("mod1", "1.0").with_requirement(
        "dep/1.0").with_package_type("module").with_generator("CMakeDeps").with_settings(
        "build_type")
    mod2 = GenConanfile("mod2", "1.0").with_requirement(
        "dep/2.0").with_package_type("module").with_generator("CMakeDeps").with_settings(
        "build_type")
    main = GenConanfile("main", "1.0").with_requirement("dep/2.0").with_requirement(
        "mod1/1.0").with_generator("CMakeDeps").with_requirement(
        "mod2/1.0").with_generator("CMakeDeps").with_settings("build_type")
    tc.save({"dep_1/conanfile.py": dep_1,
             "dep_2/conanfile.py": dep_2,
             "mod1/conanfile.py": mod1,
             "mod2/conanfile.py": mod2,
             "main/conanfile.py": main})
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" dep_1')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" dep_2')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" mod1')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" mod2')
    tc.run('create -c tools.cmake.cmakedeps:new="will_break_next" main', assert_error=True)
    assert "ERROR: Version conflict: Conflict between dep/1.0 and dep/2.0 in the graph." in tc.out


def test_skip_binaries():
    c = TestClient()
    module_dep = (GenConanfile("module_dep", "1.0").with_generator("CMakeDeps")
                  .with_settings("build_type").with_package_type("module"))
    module = (GenConanfile("module", "1.0").with_generator("CMakeDeps")
              .with_settings("build_type").with_package_type("module")
              .with_requirement("module_dep/1.0", visible=False))
    main = (GenConanfile("main", "1.0").with_generator("CMakeDeps").with_settings("build_type")
            .with_requirement("module/1.0"))
    c.save({"module_dep/conanfile.py": module_dep,
            "module/conanfile.py": module,
            "main/conanfile.py": main,
            })
    c.run("create module_dep")
    c.run("create module")
    c.run("remove module_dep/*:* -c")
    c.run("install main")
    assert re.search(r"Skipped binaries(\s*)module_dep/1.0", c.out)

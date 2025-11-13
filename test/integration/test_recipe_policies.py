from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_build_policies_in_conanfile():
    client = TestClient(default_server_user=True, light=True)
    base = GenConanfile("hello0", "1.0").with_exports("*")
    conanfile = str(base) + "\n    build_policy = 'missing'"
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=lasote --channel=stable")

    # Install, it will build automatically if missing (without the --build missing option)
    client.run("install --requires=hello0/1.0@lasote/stable")
    assert "Building" in client.out

    # Try to do it again, now we have the package, so no build is done
    client.run("install --requires=hello0/1.0@lasote/stable")
    assert "Building" not in client.out

    # Try now to upload all packages, should not crash because of the "missing" build policy
    client.run("upload hello0/1.0@lasote/stable -r default")

    #  --- Build policy to always ---
    conanfile = str(base) + "\n    build_policy = 'always'"
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("export . --user=lasote --channel=stable")

    # Install, it will build automatically if missing (without the --build missing option)
    client.run("install --requires=hello0/1.0@lasote/stable", assert_error=True)
    assert "ERROR: hello0/1.0@lasote/stable: build_policy='always' has been removed" in client.out


def test_build_policy_missing():
    c = TestClient(default_server_user=True, light=True)
    conanfile = GenConanfile("pkg", "1.0").with_class_attribute('build_policy = "missing"')\
                                          .with_class_attribute('upload_policy = "skip"')
    c.save({"conanfile.py": conanfile})
    c.run("export .")

    # the --build=never has higher priority
    c.run("install --requires=pkg/1.0@ --build=never", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/1.0'" in c.out

    c.run("install --requires=pkg/1.0@")
    assert "pkg/1.0: Building package from source as defined by build_policy='missing'" in c.out

    # If binary already there it should do nothing
    c.run("install --requires=pkg/1.0@")
    assert "pkg/1.0: Building package from source" not in c.out

    c.run("upload * -r=default -c")
    assert "Uploading package" not in c.out
    assert "pkg/1.0: Skipping upload of binaries, because upload_policy='skip'" in c.out

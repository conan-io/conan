from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestEditablePackageTest:

    def test_install_ok(self):
        ref = "--name=lib --version=version  --user=user --channel=name"
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        assert "Reference 'lib/version@user/name' in editable mode" in t.out

    def test_editable_list_search(self):
        ref = "--name=lib --version=version  --user=user --channel=name"
        t = TestClient()
        t.save({'conanfile.py': GenConanfile()})
        t.run('editable add . {}'.format(ref))
        t.run("editable list")
        assert "lib/version@user/name" in t.out
        assert "    Path:" in t.out

    def test_missing_subarguments(self):
        t = TestClient()
        t.run("editable", assert_error=True)
        assert "ERROR: Exiting with code: 2" in t.out

    def test_conanfile_name(self):
        t = TestClient()
        t.save({'othername.py': GenConanfile("lib", "version")})
        t.run('editable add ./othername.py --user=user --channel=name')
        assert "Reference 'lib/version@user/name' in editable mode" in t.out
        t.run('install --requires=lib/version@user/name')
        t.assert_listed_require({"lib/version@user/name": "Editable"})

    def test_pyrequires_remote(self):
        t = TestClient(default_server_user=True)
        t.save({"conanfile.py": GenConanfile("pyreq", "1.0")})
        t.run("create .")
        t.run("upload pyreq/1.0 -c -r=default")
        t.run("remove pyreq/1.0 -c")
        t.save({"conanfile.py": GenConanfile("pkg", "1.0").with_python_requires("pyreq/1.0")})
        t.run("editable add . -nr", assert_error=True)
        assert "Cannot resolve python_requires 'pyreq/1.0': No remote defined" in t.out
        t.run("editable add .")
        assert "Reference 'pkg/1.0' in editable mode" in t.out


def test_editable_no_name_version_test_package():
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile(),
             "test_package/conanfile.py": GenConanfile("test_package")
             .with_class_attribute("test_type = 'explicit'")
            .with_test("self.output.info('Testing the package')")})
    tc.run("editable add . --name=foo", assert_error=True)
    assert "ERROR: Editable package recipe should declare its name and version" in tc.out

    tc.run("editable add . --version=1.0", assert_error=True)
    assert "ERROR: Editable package recipe should declare its name and version" in tc.out

    tc.run("editable add .", assert_error=True)
    assert "ERROR: Editable package recipe should declare its name and version" in tc.out

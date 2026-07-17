import json
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

PLUGIN_CONTENT = textwrap.dedent("""
    import os
    from conan.internal.util.files import save  # Only for testing purposes

    def sign(ref, artifacts_folder, signature_folder, **kwargs):
        save(os.path.join(signature_folder, "signature.sig"), "signed-content")
        return [{
            "method": "dummy-method",
            "provider": "dummy-provider",
            "sign_artifacts": {"signature": "signature.sig"}
        }]

    def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
        pass
""")


def test_pkg_sign_no_plugin():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("cache sign *", assert_error=True)
    assert "ERROR: The sign() function in the package sign plugin is not defined." in c.out
    c.run("cache verify *", assert_error=True)
    assert "ERROR: The verify() function in the package sign plugin is not defined." in c.out


def test_pkg_sign_no_plugin_functions():
    c = TestClient()
    c.save_home({"extensions/plugins/sign/sign.py": ""})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("cache sign *", assert_error=True)
    assert "ERROR: The sign() function in the package sign plugin is not defined." in c.out
    c.run("cache verify *", assert_error=True)
    assert "ERROR: The verify() function in the package sign plugin is not defined." in c.out


def test_pkg_sign_verify_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.save_home({"extensions/plugins/sign/sign.py": PLUGIN_CONTENT})
    c.run("create .")
    c.run("cache sign *")
    assert textwrap.dedent("""\
        [Package sign] Results:

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e

        [Package sign] Summary: OK=2, FAILED=0""") in c.out
    c.run("cache sign * -f json")
    conanfile_dict = json.loads(c.stdout)["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]
    package_dict = conanfile_dict["packages"]["da39a3ee5e6b4b0d3255bfef95601890afd80709"] \
                                 ["revisions"]["0ba8627bd47edc3a501e8f0eb9a79e5e"]
    assert list(conanfile_dict["files"].keys()) == ["conanfile.py", "conanmanifest.txt"]
    assert list(package_dict["files"].keys()) == ["conan_package.tgz", "conaninfo.txt",
                                                  "conanmanifest.txt"]
    c.run("cache verify *")
    assert textwrap.dedent("""
        [Package sign] Results:

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e

        [Package sign] Summary: OK=2, FAILED=0""") in c.out
    c.run("cache verify * -f json")
    conanfile_dict = json.loads(c.stdout)["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]
    package_dict = conanfile_dict["packages"]["da39a3ee5e6b4b0d3255bfef95601890afd80709"] \
                                 ["revisions"]["0ba8627bd47edc3a501e8f0eb9a79e5e"]
    assert list(conanfile_dict["files"].keys()) == ["conanfile.py", "conanmanifest.txt"]
    assert list(package_dict["files"].keys()) == ["conan_package.tgz", "conaninfo.txt",
                                                  "conanmanifest.txt"]


def test_pkg_sign_no_packages():
    c = TestClient()
    c.save_home({"extensions/plugins/sign/sign.py": PLUGIN_CONTENT})
    c.run("cache sign other-pkg/*", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out
    c.run("cache verify other-pkg/*", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out


def test_pkg_sign_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        import os
        from conan.errors import ConanException
        from conan.tools.files import save

        def sign(ref, artifacts_folder, signature_folder, **kwargs):
            if "lib" in ref.repr_notime():
                raise ConanException("Error signing package")
            save(None, os.path.join(signature_folder, "signature.sig"), "signed-content")
            return [{
                "method": "dummy-method",
                "provider": "dummy-provider",
                "sign_artifacts": {"signature": "signature.sig"}
            }]
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("package", "0.1")})
    c.run("export .")
    c.run("cache sign *", assert_error=True)
    assert textwrap.dedent("""\
        [Package sign] Results:

        lib/0.1
          revisions
            dbe307e08b1a344fef76f60c85c0c4e8
              ERROR: Error signing package
        package/0.1
          revisions
            1fd0e5bcc411dcd3ff5b16024e2d7c04
        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164

        [Package sign] Summary: OK=2, FAILED=1""") in c.out
    # test json output
    c.run("cache sign * -f json", assert_error=True)
    assert "ERROR: There were some errors in the package signing process. " \
           "Please check the output." in c.out
    results = json.loads(c.stdout)
    assert results["lib/0.1"]["revisions"]["dbe307e08b1a344fef76f60c85c0c4e8"]["pkgsign_error"] == \
           "Error signing package"


def test_pkg_verify_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        import os
        from conan.internal.util.files import save  # Only for testing purposes
        from conan.errors import ConanException


        def sign(ref, artifacts_folder, signature_folder, **kwargs):
            save(os.path.join(signature_folder, "signature.sig"), "signed-content")
            return [{
                "method": "dummy-method",
                "provider": "dummy-provider",
                "sign_artifacts": {"signature": "signature.sig"}
            }]

        def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
            if "lib" in ref.repr_notime():
                raise ConanException("Wrong signature")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("package", "0.1")})
    c.run("export .")
    c.run("cache sign" " *")  # First sign all packages to generate manifests
    c.run("cache verify *", assert_error=True)
    assert textwrap.dedent("""\
        [Package sign] Results:

        lib/0.1
          revisions
            dbe307e08b1a344fef76f60c85c0c4e8
              ERROR: Wrong signature
        package/0.1
          revisions
            1fd0e5bcc411dcd3ff5b16024e2d7c04
        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164

        [Package sign] Summary: OK=2, FAILED=1""") in c.out
    # test json output
    c.run("cache verify * -f json", assert_error=True)
    assert "ERROR: There were some errors in the package signing process. " \
           "Please check the output." in c.out
    results = json.loads(c.stdout)
    assert results["lib/0.1"]["revisions"]["dbe307e08b1a344fef76f60c85c0c4e8"]["pkgsign_error"] == \
           "Wrong signature"


def test_pkg_sign_verify_pkglist():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.save_home({"extensions/plugins/sign/sign.py": PLUGIN_CONTENT})
    c.run("create .")
    # test empty package list
    c.run("list no-exist/* -f json", redirect_stdout="pkglist.json")
    c.run("cache sign -l pkglist.json", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out
    c.run("cache verify -l pkglist.json", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out

    # test incomplete package list
    c.run("list */* -f json", redirect_stdout="pkglist.json")
    c.run("cache sign -l pkglist.json", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out
    c.run("cache verify -l pkglist.json", assert_error=True)
    assert "ERROR: No packages to process in the package list provided" in c.out

    # test recipe latest package list
    c.run("list */*#latest -f json", redirect_stdout="pkglist.json")
    c.run("cache sign -l pkglist.json")
    expected = textwrap.dedent("""\
        [Package sign] Results:

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164

        [Package sign] Summary: OK=1, FAILED=0""")
    assert expected in c.out
    c.run("cache verify -l pkglist.json")
    assert expected in c.out

    # test packages without prev package list
    c.run("list */*:* -f json", redirect_stdout="pkglist.json")
    # FIXME: list command is returning packages without package revision, so packages are not signed
    c.run("cache sign -l pkglist.json")
    expected = textwrap.dedent("""\
        [Package sign] Results:

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709

        [Package sign] Summary: OK=1, FAILED=0""")
    assert expected in c.out
    c.run("cache verify -l pkglist.json")
    assert expected in c.out

    # test packages with prev package list
    c.run("list */*:*#latest -f json", redirect_stdout="pkglist.json")
    c.run("cache sign -l pkglist.json")
    expected = textwrap.dedent("""\
        [Package sign] Results:

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e

        [Package sign] Summary: OK=2, FAILED=0""")
    assert expected in c.out
    c.run("cache verify -l pkglist.json")
    assert expected in c.out

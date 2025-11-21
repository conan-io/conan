import json
import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_pkg_sign_no_plugin():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("cache sign *", assert_error=True)
    assert "ERROR: [Package sign] Plugin not configured" in c.out
    c.run("cache verify *", assert_error=True)
    assert "ERROR: [Package sign] Plugin not configured" in c.out


def test_pkg_sign_no_plugin_functions():
    c = TestClient()
    c.save_home({"extensions/plugins/sign/sign.py": ""})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("cache sign *", assert_error=True)
    assert "ERROR: [Package sign] sign() function not found" in c.out
    c.run("cache verify *", assert_error=True)
    assert "ERROR: [Package sign] verify() function not found" in c.out


def test_pkg_sign_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def sign(ref, artifacts_folder, signature_folder):
            if ":" in str(ref):
                return "ok"
            return
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache sign *")
    assert textwrap.dedent("""\
        [Package sign] Signing packages in local cache...

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: ok
              package sign: Created

        [Package sign] Summary: OK=2, WARN=0, FAILED=0""") in c.out


def test_pkg_verify_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def verify(ref, artifacts_folder, signature_folder, files):
            if ":" in str(ref):
                return "ok"
            return
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache verify *")
    assert textwrap.dedent("""
        [Package sign] Verifying signature of packages in local cache...

        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: ok
              package sign: Verified

        [Package sign] Summary: OK=2, WARN=0, FAILED=0""") in c.out


def test_pkg_sign_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def sign(ref, artifacts_folder, signature_folder):
            if "lib" in ref.repr_notime():
                raise ConanException("Error signing package")
            elif "pkg" in ref.repr_notime():
                return
            else:
                return "Success"
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
        [Package sign] Signing packages in local cache...

        lib/0.1
          revisions
            dbe307e08b1a344fef76f60c85c0c4e8
              packages
              package sign: Failed: Error signing package
        package/0.1
          revisions
            1fd0e5bcc411dcd3ff5b16024e2d7c04
              packages
              package sign: Success
        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
              package sign: Created

        [Package sign] Summary: OK=2, WARN=0, FAILED=1""") in c.out
    # test json output
    c.run("cache sign * -f json", assert_error=True)
    assert "ERROR: There were some errors in the signing process. " \
           "Please check the output." in c.out
    results = json.loads(c.stdout)
    assert results["lib/0.1"]["revisions"]["dbe307e08b1a344fef76f60c85c0c4e8"]["package sign"] == \
           "Failed: Error signing package"
    assert results["package/0.1"]["revisions"]["1fd0e5bcc411dcd3ff5b16024e2d7c04"]["package sign"]\
           == "Success"
    assert results["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]["package sign"] == \
           "Created"


def test_pkg_verify_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def verify(ref, artifacts_folder, signature_folder, files):
            if "lib" in ref.repr_notime():
                raise ConanException("Wrong signature")
            elif "pkg" in ref.repr_notime():
                return "Warning: message"
            return "Success"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("package", "0.1")})
    c.run("export .")
    c.run("cache verify *", assert_error=True)
    assert textwrap.dedent("""\
        [Package sign] Verifying signature of packages in local cache...

        lib/0.1
          revisions
            dbe307e08b1a344fef76f60c85c0c4e8
              packages
              package sign: Failed: Wrong signature
        package/0.1
          revisions
            1fd0e5bcc411dcd3ff5b16024e2d7c04
              packages
              package sign: Success
        pkg/0.1
          revisions
            485dad6cb11e2fa99d9afbe44a57a164
              packages
              package sign: Warning: message

        [Package sign] Summary: OK=1, WARN=1, FAILED=1""") in c.out
    # test json output
    c.run("cache verify * -f json", assert_error=True)
    assert "ERROR: There were some errors in the signature verification process. " \
           "Please check the output." in c.out
    results = json.loads(c.stdout)
    assert results["lib/0.1"]["revisions"]["dbe307e08b1a344fef76f60c85c0c4e8"]["package sign"] == \
           "Failed: Wrong signature"
    assert results["package/0.1"]["revisions"]["1fd0e5bcc411dcd3ff5b16024e2d7c04"]["package sign"]\
           == "Success"
    assert results["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]["package sign"] == \
           "Warning: message"

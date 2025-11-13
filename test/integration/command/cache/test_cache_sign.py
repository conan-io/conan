import json
import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_pkg_sign_no_plugin():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run("cache sign *", assert_error=True)
    assert "ERROR: [Package Signing Plugin] sign() function not found" in c.out
    c.run("cache verify *", assert_error=True)
    assert "ERROR: [Package Signing Plugin] verify() function not found" in c.out


def test_pkg_sign_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
            output.info(f"Signing package")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache sign *")
    assert textwrap.dedent("""\
        [Package signing plugin]
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
            :: Signing package""") in c.out
    assert textwrap.dedent("""\
        [Package signing plugin]
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e
            :: Signing package""") in c.out
    assert textwrap.dedent("""
    [Package signing plugin] Signing results:
      pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
        :: Signed
      pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e
        :: Signed""") in c.out


def test_pkg_verify_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            output.info(f"Verifying package")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache verify *")
    assert textwrap.dedent("""\
        [Package signing plugin]
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
            :: Verifying package""") in c.out
    assert textwrap.dedent("""\
        [Package signing plugin]
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e
            :: Verifying package""") in c.out
    assert textwrap.dedent("""
    [Package signing plugin] Verification results:
      pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
        :: Signature verified
      pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e
        :: Signature verified""") in c.out

def test_pkg_sign_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
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
    c.run("cache sign *")
    assert textwrap.dedent("""\
        [Package signing plugin] Signing results:
          lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8
            :: Failed: Error signing package
          package/0.1#1fd0e5bcc411dcd3ff5b16024e2d7c04
            :: Success
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
            :: Signed""") in c.out
    # test json output
    c.run("cache sign * -f json")
    data = json.loads(c.stdout)
    assert data["action"] == "sign"
    assert data["results"]["lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8"] == \
           "Failed: Error signing package"
    assert data["results"]["package/0.1#1fd0e5bcc411dcd3ff5b16024e2d7c04"] == "Success"
    assert data["results"]["pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164"] is None


def test_pkg_verify_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            if "lib" in ref.repr_notime():
                raise ConanException("Wrong signature")
            elif "pkg" in ref.repr_notime():
                return
            return "Success"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("export .")
    c.save({"conanfile.py": GenConanfile("package", "0.1")})
    c.run("export .")
    c.run("cache verify *")
    assert textwrap.dedent("""\
        [Package signing plugin] Verification results:
          lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8
            :: Failed: Wrong signature
          package/0.1#1fd0e5bcc411dcd3ff5b16024e2d7c04
            :: Success
          pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164
            :: Signature verified""") in c.out
    # test json output
    c.run("cache verify * -f json")
    data = json.loads(c.stdout)
    assert data["action"] == "verify"
    assert data["results"]["lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8"] == \
           "Failed: Wrong signature"
    assert data["results"]["package/0.1#1fd0e5bcc411dcd3ff5b16024e2d7c04"] == "Success"
    assert data["results"]["pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164"] is None

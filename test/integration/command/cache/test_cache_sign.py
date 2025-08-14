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
    c.run("cache sign *")
    assert "ERROR: [Package signing plugin] sign() function not found" in c.out
    c.run("cache verify *")
    assert "ERROR: [Package signing plugin] verify() function not found" in c.out


def test_pkg_sign_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
            output.info(f"Signing package {ref.repr_notime()}")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache sign *")
    assert "Signing package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" in c.out
    assert "Signing package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" \
           ":da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e" in c.out


def test_pkg_verify_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            output.info(f"Verifying package {ref.repr_notime()}")
            return "success"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache verify *")
    assert "Verifying package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" in c.out
    assert "Verifying package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" \
           ":da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e" in c.out


def test_pkg_sign_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
            output.info(f"Signing package {ref.repr_notime()}")
            if "lib" in ref.repr_notime():
                raise ConanException("error signing package")
            return "success"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("create .")
    c.run("cache sign *")
    assert "Signing package lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8" in c.out
    assert "Signing package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" in c.out
    assert "[Package signing plugin] Signing results:" in c.out
    assert "- lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8\n" \
           "      Failed: error signing package" in c.out
    assert "- pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164\n" \
           "      success" in c.out
    # test json output
    c.run("cache sign * -f json")
    data = json.loads(c.stdout)
    assert data["action"] == "sign"
    assert data["results"]["lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8"] == \
           "Failed: error signing package"
    assert data["results"]["pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164"] == "success"


def test_pkg_verify_exception():
    c = TestClient()
    signer = textwrap.dedent(r"""
        from conan.errors import ConanException

        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            output.info(f"Verifying package {ref.repr_notime()}")
            if "lib" in ref.repr_notime():
                raise ConanException("bad signature verification")
            return "success"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.save({"conanfile.py": GenConanfile("lib", "0.1")})
    c.run("create .")
    c.run("cache verify *")
    assert "Verifying package lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8" in c.out
    assert "Verifying package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" in c.out
    assert "[Package signing plugin] Verification results:" in c.out
    assert "- lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8\n" \
           "      Failed: bad signature verification" in c.out
    assert "- pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164\n" \
           "      success" in c.out
    # test json output
    c.run("cache verify * -f json")
    data = json.loads(c.stdout)
    assert data["action"] == "verify"
    assert data["results"]["lib/0.1#dbe307e08b1a344fef76f60c85c0c4e8"] == \
           "Failed: bad signature verification"
    assert data["results"]["pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164"] == "success"

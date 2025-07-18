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
    assert "ERROR: Package signing plugin: sign function not found" in c.out
    c.run("cache verify *")
    assert "ERROR: Package signing plugin: verify function not found" in c.out


def test_pkg_sign_basic():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def sign(ref, artifacts_folder, signature_folder):
            print(f"Signing package {ref.repr_notime()}")
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
        def verify(ref, artifacts_folder, signature_folder, files):
            print(f"Verifying package {ref.repr_notime()}")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache verify *")
    assert "Verifying package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" in c.out
    assert "Verifying package pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164" \
           ":da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e" in c.out

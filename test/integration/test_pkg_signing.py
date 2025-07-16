import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_pkg_sign():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os

        def sign(ref, artifacts_folder, signature_folder, **kwargs):
            print("Signing ref: ", ref)
            print("Signing folder: ", artifacts_folder)
            files = []
            for f in sorted(os.listdir(artifacts_folder)):
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    files.append(f)
            print("Signing files: ", sorted(files))
            signature = os.path.join(signature_folder, "signature.asc")
            open(signature, "w").write("\n".join(files))

        def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
            print("Verifying ref: ", ref)
            print("Verifying folder: ", artifacts_folder)
            signature = os.path.join(signature_folder, "signature.asc")
            contents = open(signature).read()
            print("verifying contents", contents)
            for f in files:
                print("VERIFYING ", f)
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    assert f in contents
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("upload * -r=default -c")
    assert "Signing ref:  pkg/0.1" in c.out
    assert "Signing ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    # Make sure it is signing the sources too
    assert "Signing files:  ['conan_export.tgz', 'conan_sources.tgz', " \
           "'conanfile.py', 'conanmanifest.txt']" in c.out
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    assert "VERIFYING  conanfile.py" in c.out
    assert "VERIFYING  conan_sources.tgz" not in c.out  # Sources not retrieved now
    # Lets force the retrieval of the sources
    c.run("install --requires=pkg/0.1 --build=*")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "VERIFYING  conanfile.py" not in c.out  # It doesn't re-verify previous contents
    assert "VERIFYING  conan_sources.tgz" in c.out


def test_pkg_sign_assert_error():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
            assert False, "verify assertion error"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("upload * -r=default -c --dry-run")
    c.run("cache check-integrity *", assert_error=True)
    assert "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#0ba8627bd47edc3a501e8f0eb9a79e5e [Package-signing plugin]: ERROR: " \
           "Error verifying package signature" in c.out
    assert "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#0ba8627bd47edc3a501e8f0eb9a79e5e [Package-signing plugin]: ERROR: " \
           "verify assertion error" in c.out
    assert "ERROR: There are artifacts with invalid signature. Check the error logs." in c.out


def test_pkg_sign_no_verify_function():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        def sign(ref, artifacts_folder, signature_folder, output):
            output.info("Signing reference")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("upload pkg/0.1 -r default -c --dry-run")
    assert "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164 [Package-signing plugin]: " \
           "Package signature creation: ok" in c.out
    c.run("cache check-integrity pkg/0.1")
    assert "Package signature verification: ok" not in c.out
    assert "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164: Integrity check: ok" in c.out


def test_pkg_sign_no_sign_function():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    signer = textwrap.dedent(r"""
        import os
        from conan.api.model.refs import PkgReference
        from conan.errors import ConanException

        def verify(ref, artifacts_folder, signature_folder, files, output):
            output.info("Verifying reference")
            output.info(f"Verifying folder: {artifacts_folder}")
            signature = os.path.join(signature_folder, "signature.asc")

            # This is to check if the package was signed or not
            if isinstance(ref, PkgReference):
                download_file_path = os.path.join(artifacts_folder, "conan_package.tgz")
            else:
                download_file_path = os.path.join(artifacts_folder, "conanfile.py")

            if not os.path.isfile(download_file_path) and not os.path.isfile(signature):
                output.warning("Could not verify unsigned package")
                return

            if not os.path.isfile(signature):
                raise ConanException("Missing signature file!")

            contents = open(signature).read()
            output.info(f"Verifying contents: {contents}")
            for f in files:
                output.info(f"Verifying file: {f}")
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    if f not in contents:
                        raise ConanException(f"File {f} not found in signature contents")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("upload pkg/0.1 -r default -c --dry-run")
    assert "Package signature creation: ok" not in c.out
    c.run("cache check-integrity pkg/0.1", assert_error=True)
    assert "Missing signature file!" in c.out
    assert "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164: Integrity check: ok" in c.out


def test_pkg_sign_check_integrity():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os
        from conan.api.model.refs import PkgReference
        from conan.errors import ConanException


        def sign(ref, artifacts_folder, signature_folder, output):
            output.info("Signing reference")
            output.info(f"Signing folder: {artifacts_folder}")
            files = []
            for f in sorted(os.listdir(artifacts_folder)):
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    files.append(f)
            output.info(f"Signing files: {sorted(files)}")
            signature = os.path.join(signature_folder, "signature.asc")
            open(signature, "w").write("\n".join(files))

        def verify(ref, artifacts_folder, signature_folder, files, output):
            output.info("Verifying reference")
            output.info(f"Verifying folder: {artifacts_folder}")
            signature = os.path.join(signature_folder, "signature.asc")

            # This is to check if the package was signed or not
            if isinstance(ref, PkgReference):
                download_file_path = os.path.join(artifacts_folder, "conan_package.tgz")
            else:
                download_file_path = os.path.join(artifacts_folder, "conanfile.py")

            if not os.path.isfile(download_file_path) and not os.path.isfile(signature):
                output.warning("Could not verify unsigned package")
                return

            if not os.path.isfile(signature):
                raise ConanException("Missing signature file!")

            contents = open(signature).read()
            output.info(f"Verifying contents: {contents}")
            for f in files:
                output.info(f"Verifying file: {f}")
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    if f not in contents:
                        raise ConanException(f"File {f} not found in signature contents")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")

    # Package is still not signed
    c.run("cache check-integrity pkg/0.1")
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a [Package-signing plugin]: WARN: " \
           "Could not verify unsigned package" in c.out
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#d950d0cd76f6bba62c8add9c68d1aeb3 [Package-signing plugin]: WARN: " \
           "Could not verify unsigned package" in c.out

    # prepare for upload, sign the packages and integrity check
    c.run("upload pkg/0.1 -r=default -c --dry-run --force --check")
    # Check order: integrity check, prepare (sign), verify, upload summary
    subtitle_lines = [line for line in c.out.splitlines() if "--------" in line]
    assert "Checking integrity of cache packages" in subtitle_lines[0]
    assert "Checking server existing packages" in subtitle_lines[1]
    assert "Preparing artifacts for upload" in subtitle_lines[2]
    assert "[Package-signing plugin] Verifying packages" in subtitle_lines[3]
    assert "Upload summary" in subtitle_lines[4]
    # Check package was signed
    assert "Signing ref" in c.out
    # Verify packages with check-integrity command
    c.run("cache check-integrity pkg/0.1")
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a [Package-signing plugin]: " \
           "Package signature verification: ok" in c.out
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#d950d0cd76f6bba62c8add9c68d1aeb3 [Package-signing plugin]: " \
           "Package signature verification: ok" in c.out

    # Remove signature file to force error
    c.run("cache path pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    signature_path = os.path.join(os.path.dirname(c.out), "d", "metadata", "sign", "signature.asc")
    os.unlink(signature_path)
    c.run("cache check-integrity pkg/0.1", assert_error=True)
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a [Package-signing plugin]: " \
           "Package signature verification: ok" in c.out
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#d950d0cd76f6bba62c8add9c68d1aeb3 [Package-signing plugin]: ERROR: " \
           "Missing signature file!" in c.out

    # Sign the package again and remove file from signature file to force error
    c.run("upload pkg/0.1 -r=default -c --dry-run --force")
    assert "Signing ref" in c.out
    c.run("cache path pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    signature_path = os.path.join(os.path.dirname(c.out), "d", "metadata", "sign", "signature.asc")
    signature_content = c.load(signature_path)
    signature_content = signature_content.replace("conan_package.tgz", "")
    c.save({signature_path: signature_content})
    c.run("cache check-integrity pkg/0.1", assert_error=True)
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a [Package-signing plugin]: " \
           "Package signature verification: ok" in c.out
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#d950d0cd76f6bba62c8add9c68d1aeb3 [Package-signing plugin]: ERROR: " \
           "File conan_package.tgz not found in signature contents" in c.out

    # Build the package again (the download folder contents are cleared)
    c.run("install --requires pkg/0.1 --build pkg/0.1")
    c.run("cache check-integrity pkg/0.1")
    # Recipe is still signed as it was not modified
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a [Package-signing plugin]: " \
           "Package signature verification: ok" in c.out
    # But the new built package has not been signed
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
           "#d950d0cd76f6bba62c8add9c68d1aeb3 [Package-signing plugin]: WARN: " \
           "Could not verify unsigned package" in c.out

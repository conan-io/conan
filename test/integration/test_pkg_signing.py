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
            return [{
                "method": "dummy-method",
                "provider": "dummy-provider",
                "sign_artifacts": {"signature": "signature.asc"}
                }]

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


def test_pkg_sign_manifest_signatures():
    """Test that the sign function generates the manifest and signatures files
    and the verify function can access them"""
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os
        from conan.tools.files import load, save
        from conan.tools.pkg_signing.plugin import (load_manifest, load_signatures, signature_dict,
                                                    verify_files_checksums)

        def sign(ref, artifacts_folder, signature_folder, **kwargs):
            save(None, os.path.join(signature_folder, "pkgsign-manifest.json.sig"), "")
            print(f"Creating signature pkgsign-manifest.json.sig for {ref}")
            # Return the pkgsign-signatures.json's content
            return [{"method": "openssl-dgst",
                    "provider": "conan-client",
                    "sign_artifacts": {"signature": "pkgsign-manifest.json.sig"}}]

        def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
            print(f"Manifest content:\n {load_manifest(signature_folder)}")
            verify_files_checksums(signature_folder, files)
            signatures_content = load_signatures(signature_folder)
            signatures = signatures_content["signatures"]
            for signature in signatures_content["signatures"]:
                provider = signature.get("provider")
                method = signature.get("method")
                signature = signature.get("sign_artifacts", {}).get("signature")
                print(f"Provider: {provider}, Method: {method}, Signature: {signature}")
                # Verify signature here
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache sign *")
    assert "Creating signature pkgsign-manifest.json.sig for pkg/0.1" in c.out
    c.run("cache verify *")
    assert "Manifest content:\n {'files': [{'file': 'conan_export.tgz'" in c.out
    assert "Checksum verified for file conanfile.py" in c.out
    assert "Provider: conan-client, Method: openssl-dgst, Signature: pkgsign-manifest.json.sig"
    assert "Manifest content:\n {'files': [{'file': 'conan_package.tgz'" in c.out
    assert "Checksum verified for file conan_package.tgz" in c.out


def test_pkg_sign_canonical():
    c = TestClient(default_server_user=True)
    c.save({"conanfile1.py": GenConanfile("lib1ok", "0.1")
                .with_exports_sources("*.txt").with_package_file("package.txt", "kk"),
            "conanfile2.py": GenConanfile("lib2fail", "0.1"),  # will fail when installed
            "conanfile3.py": GenConanfile("lib3fail", "0.1"),  # should always fail
            "sources.txt": "kk"})
    c.run("create conanfile1.py")
    c.run("create conanfile2.py")
    c.run("create conanfile3.py")
    signer = textwrap.dedent(r"""
        import os
        from conan.errors import ConanException
        from conan.api.output import ConanOutput
        from conan.tools.files import save
        from conan.tools.pkg_signing.plugin import (get_signatures_filepath, load_signatures,
            verify_files_checksums)

        def sign(ref, artifacts_folder, signature_folder, **kwargs):
            ConanOutput().info(f"Signing reference {ref}")
            ConanOutput().info(f"Signing folder: {artifacts_folder}")

            if "lib3fail" in str(ref):
                raise ConanException("sign failed")
            elif "lib2fail" in str(ref):
                provider = "this will fail to verify"
            else:
                provider = "conan-client"
            # Simulate signing the package
            save(None, os.path.join(signature_folder, "pkgsign-manifest.json.sig"), "")
            ConanOutput().info(f"Signature ok for {ref}")
            return [{"method": "dummy-method",
                     "provider": provider,
                     "sign_artifacts": {"signature": "pkgsign-manifest.json.sig"}
            }]

        def verify(ref, artifacts_folder, signature_folder, files, **kwargs):
            ConanOutput().info(f"Verifying reference {ref}")
            signatures_file_path = get_signatures_filepath(signature_folder)
            if not os.path.isfile(signatures_file_path):
                raise ConanException("Package is not signed")

            if "lib3fail" in str(ref):
                raise ConanException(f"verify failed for {ref}")
            # Simulate verification
            signatures = load_signatures(signature_folder)
            provider = signatures["signatures"][0]["provider"]
            if provider != "conan-client":
                raise ConanException(f"Failed to verify the package {ref}")
            verify_files_checksums(signature_folder, files)
            signature = signatures["signatures"][0]["sign_artifacts"]["signature"]
            ConanOutput().info(f"Verification ok for {ref} with signature {signature}")
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})

    # Cache verify command fails and reports if package is not signed
    c.run("cache verify *", assert_error=True)
    assert textwrap.dedent("""
     [Package sign] Results:

     lib1ok/0.1
       revisions
         a6a4e799bb673d6e5ca4f904118d672e
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 76285bcb59a81071122cba04b2269b52
                   ERROR: Package is not signed
           ERROR: Package is not signed
     lib2fail/0.1
       revisions
         70a185be5a95af3dde25b74ae800b2f2
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   ERROR: Package is not signed
           ERROR: Package is not signed
     lib3fail/0.1
       revisions
         09ccc766ddd11c96aa78307b3f166fd6
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   ERROR: Package is not signed
           ERROR: Package is not signed

     [Package sign] Summary: OK=0, FAILED=6""") in c.out

    # Cache sign command fails if a package fails to sign and reports it
    c.run("cache sign *", assert_error=True)
    assert textwrap.dedent("""
        [Package sign] Results:

        lib1ok/0.1
          revisions
            a6a4e799bb673d6e5ca4f904118d672e
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    76285bcb59a81071122cba04b2269b52
        lib2fail/0.1
          revisions
            70a185be5a95af3dde25b74ae800b2f2
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
        lib3fail/0.1
          revisions
            09ccc766ddd11c96aa78307b3f166fd6
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      ERROR: sign failed
              ERROR: sign failed

        [Package sign] Summary: OK=4, FAILED=2
        """) in c.out

    # Upload sign fails if package signing fails
    c.run("upload * -c -r default", assert_error=True)
    assert "ERROR: sign failed" in c.out

    # If upload sign failed, no packages should be uploaded
    c.run("list * -r default")
    assert "WARN: There are no matching recipe references" in c.out

    # Upload packages individually to avoid previous failure
    c.run("upload lib1ok* -c -r default")
    c.run("upload lib2fail* -c -r default")
    c.run("remove * -c")

    # Install verify command should fail if package sign verification fails
    c.run("install --requires lib1ok/0.1 --requires lib2fail/0.1 -r default",
          assert_error=True)
    assert "ERROR: Package 'lib2fail/0.1' not resolved: Failed to verify " \
           "the package lib2fail/0.1" in c.out

    # If packages fail to verify signature, they should not be installed
    c.run("list *")
    assert "lib1ok" in c.out
    assert "lib2fail" not in c.out
    c.run("cache verify *")
    assert textwrap.dedent("""\
        [Package sign] Results:

        lib1ok/0.1
          revisions
            a6a4e799bb673d6e5ca4f904118d672e

        [Package sign] Summary: OK=1, FAILED=0
    """) in c.out

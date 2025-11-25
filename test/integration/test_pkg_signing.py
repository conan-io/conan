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


def test_pkg_sign_canonical():
    c = TestClient(default_server_user=True)
    c.save({"conanfile1.py": GenConanfile("lib1ok", "0.1").with_exports_sources("*.txt").with_package_file("package.txt", "kk"),
            "conanfile2.py": GenConanfile("lib2fail", "0.1"),  # This pkg fails when installed
            "conanfile3.py": GenConanfile("lib3fail", "0.1"),  # This pkg should always fail
            "sources.txt": "kk"})
    c.run("create conanfile1.py")
    c.run("create conanfile2.py")
    c.run("create conanfile3.py")
    signer = textwrap.dedent(r"""
        import os
        from conan.errors import ConanException
        from conan.api.output import ConanOutput
        from conan.tools.files import save
        from conan.tools.pkg_signing.plugin import (create_summary_content, get_summary_file_path,
            load_summary, save_summary)

        def sign(ref, artifacts_folder, signature_folder):
            ConanOutput().info(f"Signing reference {ref}")
            ConanOutput().info(f"Signing folder: {artifacts_folder}")
            c = create_summary_content(artifacts_folder)
            c["method"] = "sigstore"

            if "lib3fail" in str(ref):
                raise ConanException("sign failed")
            elif "lib2fail" in str(ref):
                c["provider"] = "this will fail to verify"
            else:
                c["provider"] = "conan-client"
            save_summary(signature_folder, c)
            # Simulate signing the package
            sfp = get_summary_file_path(signature_folder)
            save(None, f"{sfp}.sig", "")
            ConanOutput().info(f"Signature ok for {ref}")

        def verify(ref, artifacts_folder, signature_folder, files):
            ConanOutput().info(f"Verifying reference {ref}")
            sfp = get_summary_file_path(signature_folder)
            signature_file_path = f"{sfp}.sig"
            if not os.path.isfile(signature_file_path):
                raise ConanException("Package is not signed")

            if "lib3fail" in str(ref):
                raise ConanException(f"verify failed for {ref}")
            summary = load_summary(signature_folder)
            # Simulate verification
            if summary.get("provider") != "conan-client":
                raise ConanException(f"Failed to verify the package {ref}")
            ConanOutput().info(f"Verification ok for {ref}")
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
                   package sign: Failed: Package is not signed
           package sign: Failed: Package is not signed
     lib2fail/0.1
       revisions
         70a185be5a95af3dde25b74ae800b2f2
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   package sign: Failed: Package is not signed
           package sign: Failed: Package is not signed
     lib3fail/0.1
       revisions
         09ccc766ddd11c96aa78307b3f166fd6
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   package sign: Failed: Package is not signed
           package sign: Failed: Package is not signed

     [Package sign] Summary: OK=0, WARN=0, FAILED=6""") in c.out

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
                      package sign: Signed
              package sign: Signed
        lib2fail/0.1
          revisions
            70a185be5a95af3dde25b74ae800b2f2
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: Signed
              package sign: Signed
        lib3fail/0.1
          revisions
            09ccc766ddd11c96aa78307b3f166fd6
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: Failed: sign failed
              package sign: Failed: sign failed

        [Package sign] Summary: OK=4, WARN=0, FAILED=2
        """) in c.out

    # Upload sign fails if package signing fails
    c.run("upload * -c -r default", assert_error=True)
    assert "ERROR: [Package sign] sign failed" in c.out

    # If upload sign failed, no packages should be uploaded
    c.run("list * -r default")
    assert "WARN: There are no matching recipe references" in c.out

    # Upload packages individually to avoid previous failure
    c.run("upload lib1ok* -c -r default")
    c.run("upload lib2fail* -c -r default")
    c.run("remove * -c")

    # Install verify command should fail if package sign verification fails
    c.run("install --requires lib1ok/0.1 --requires lib2fail/0.1 -r default", assert_error=True)
    assert "ERROR: Package 'lib2fail/0.1' not resolved: [Package sign] Failed to verify " \
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
              packages
              package sign: Verified

        [Package sign] Summary: OK=1, WARN=0, FAILED=0
    """) in c.out

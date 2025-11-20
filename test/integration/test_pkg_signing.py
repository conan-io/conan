import re
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
        from conan.tools.pkg_signing.plugin import (create_summary_content, is_pkg_signed,
            load_summary, save_summary)

        def sign(ref, artifacts_folder, signature_folder):
            ConanOutput().info("Signing reference")
            ConanOutput().info(f"Signing folder: {artifacts_folder}")
            if is_pkg_signed(signature_folder):
                summary = load_summary(signature_folder)
                if summary.get("provider") != "conan-client":
                    return "Warn: Package already signed by another provider"
                return "Package already signed by the same provider"

            c = create_summary_content(artifacts_folder)
            c["method"] = "sigstore"

            if "lib3fail" in str(ref):
                raise ConanException("sign failed")
            elif "lib2fail" in str(ref):
                c["provider"] = "this will fail to verify"
            else:
                c["provider"] = "conan-client"
            save_summary(signature_folder, c)
            return "Signature ok"

        def verify(ref, artifacts_folder, signature_folder, files):
            ConanOutput().info(f"Verifying reference")
            if not is_pkg_signed(signature_folder):
                raise ConanException("Package is not signed")

            if "lib3fail" in str(ref):
                raise ConanException(f"verify failed for {ref}")
            summary = load_summary(signature_folder)
            assert summary.get("provider") == "conan-client", "wrong provider"
            return f"Verification ok"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})

    # Cache verify command fails and reports if package is not signed
    c.run("cache verify *", assert_error=True)
    c_out = re.sub(r"\s*timestamp\s*\n.*\n", "\n", c.out)
    assert textwrap.dedent("""
     [Package sign] Verifying signature of packages in local cache...

     lib1ok/0.1
       revisions
         a6a4e799bb673d6e5ca4f904118d672e
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 76285bcb59a81071122cba04b2269b52
                   package sign: Failed: Package is not signed
               info
           package sign: Failed: Package is not signed
     lib2fail/0.1
       revisions
         70a185be5a95af3dde25b74ae800b2f2
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   package sign: Failed: Package is not signed
               info
           package sign: Failed: Package is not signed
     lib3fail/0.1
       revisions
         09ccc766ddd11c96aa78307b3f166fd6
           packages
             da39a3ee5e6b4b0d3255bfef95601890afd80709
               revisions
                 0ba8627bd47edc3a501e8f0eb9a79e5e
                   package sign: Failed: Package is not signed
               info
           package sign: Failed: Package is not signed

     [Package sign] Summary: OK=0, WARN=0, FAILED=6""") in c_out

    # Cache sign command fails if a package fails to sign and reports it
    c.run("cache sign *", assert_error=True)
    c_out = re.sub(r"\s*timestamp\s*\n.*\n", "\n", c.out)
    assert textwrap.dedent("""
        [Package sign] Signing packages in local cache...

        lib1ok/0.1
          revisions
            a6a4e799bb673d6e5ca4f904118d672e
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    76285bcb59a81071122cba04b2269b52
                      package sign: Signature ok
                  info
              package sign: Signature ok
        lib2fail/0.1
          revisions
            70a185be5a95af3dde25b74ae800b2f2
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: Signature ok
                  info
              package sign: Signature ok
        lib3fail/0.1
          revisions
            09ccc766ddd11c96aa78307b3f166fd6
              packages
                da39a3ee5e6b4b0d3255bfef95601890afd80709
                  revisions
                    0ba8627bd47edc3a501e8f0eb9a79e5e
                      package sign: Failed: sign failed
                  info
              package sign: Failed: sign failed

        [Package sign] Summary: OK=4, WARN=0, FAILED=2
        """) in c_out

    # Upload sign fails if package signing fails
    c.run("upload * -c -r default", assert_error=True)
    assert "ERROR: There were some errors in the signature verification process. Please check the output." in c.out
    assert textwrap.dedent("""
        default
          lib1ok/0.1
            revisions
              a6a4e799bb673d6e5ca4f904118d672e (Not uploaded)
                packages
                  da39a3ee5e6b4b0d3255bfef95601890afd80709
                    revisions
                      76285bcb59a81071122cba04b2269b52 (Not uploaded)
                        package sign: Package already signed by the same provider
                package sign: Package already signed by the same provider
          lib2fail/0.1
            revisions
              70a185be5a95af3dde25b74ae800b2f2 (Not uploaded)
                packages
                  da39a3ee5e6b4b0d3255bfef95601890afd80709
                    revisions
                      0ba8627bd47edc3a501e8f0eb9a79e5e (Not uploaded)
                        package sign: Warn: Package already signed by another provider
                package sign: Warn: Package already signed by another provider
          lib3fail/0.1
            revisions
              09ccc766ddd11c96aa78307b3f166fd6 (Not uploaded)
                packages
                  da39a3ee5e6b4b0d3255bfef95601890afd80709
                    revisions
                      0ba8627bd47edc3a501e8f0eb9a79e5e (Not uploaded)
                package sign: Failed: sign failed""") in c.out

    # If upload sign failed, no packages should be uploaded
    c.run("list * -r default")
    assert "WARN: There are no matching recipe references" in c.out

    # Upload packages individually to avoid previous failure
    c.run("upload lib1ok* -c -r default")
    c.run("upload lib2fail* -c -r default")
    c.run("remove * -c")

    # Install verify command should fail if package is signed by another provider
    c.run("install --requires lib1ok/0.1 --build lib1ok/0.1 -r default -f json", assert_error=False)  # --requires lib2fail/0.1
    print(c.out)
    assert "ERROR: Package 'lib2fail/0.1' not resolved: [Package sign] Failed: wrong provider" in c.out
    assert textwrap.dedent("""\
        [Package sign] Verification results:
        lib1ok/0.1
          revisions
            a6a4e799bb673d6e5ca4f904118d672e
              package sign: Verification ok
        """) in re.sub(r"\s*timestamp\s*\n.*\n", "\n", c.out)

    # Packages that failed in install verification should not appear as installed
    c.run("list *")
    assert "lib1ok" in c.out
    assert "lib2fail" not in c.out
    c.run("cache verify *")
    assert  textwrap.dedent("""\
        [Package sign] Verifying signature of packages in local cache...

        lib1ok/0.1
          revisions
            a6a4e799bb673d6e5ca4f904118d672e
              packages
              package sign: Verification ok

        [Package sign] Summary: OK=1, WARN=0, FAILED=0
    """) in re.sub(r"\s*timestamp\s*\n.*\n", "\n", c.out)

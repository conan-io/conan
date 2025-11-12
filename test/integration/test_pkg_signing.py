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
    c.save({"conanfile1.py": GenConanfile("lib1ok", "0.1"),
            "conanfile2.py": GenConanfile("lib2fail", "0.1"),  # This pkg fails when installed
            "conanfile3.py": GenConanfile("lib3fail", "0.1")})  # This pkg should always fail
    c.run("create conanfile1.py")
    c.run("create conanfile2.py")
    c.run("create conanfile3.py")
    signer = textwrap.dedent(r"""
        import os
        from conan.errors import ConanException

        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
            output.info("Signing reference")
            output.info(f"Signing folder: {artifacts_folder}")
            if sign_tools.is_pkg_signed():
                summary = sign_tools.load_summary()
                if summary.get("provider") != "conan-client":
                    return "Warn: Package already signed by another provider"
                return "Package already signed by the same provider"

            c = sign_tools.create_summary_content()
            c["method"] = "sigstore"

            if "lib3fail" in str(ref):
                raise ConanException("sign failed")
            elif "lib2fail" in str(ref):
                c["provider"] = "this will fail to verify"
            else:
                c["provider"] = "conan-client"
            sign_tools.save_summary(c)
            return "Signature ok"

        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            output.info(f"Verifying reference")
            if not sign_tools.is_pkg_signed():
                raise ConanException("Package is not signed")

            if "lib3fail" in str(ref):
                raise ConanException(f"verify failed for {ref}")
            summary = sign_tools.load_summary()
            assert summary.get("provider") == "conan-client", "wrong provider"
            return f"Verification ok"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})

    # Cache verify command does not fail if package is not signed
    c.run("cache verify *")
    assert "lib1ok/0.1#a5e2af5522a1edcab963447eec649700\n    :: Failed: Package is not signed" in c.out
    assert "lib2fail/0.1#70a185be5a95af3dde25b74ae800b2f2\n    :: Failed: Package is not signed" in c.out
    assert "lib3fail/0.1#09ccc766ddd11c96aa78307b3f166fd6\n    :: Failed: Package is not signed" in c.out

    # Cache sign command does not fail if a package fails to sign, but it reports it
    c.run("cache sign *")
    assert "lib1ok/0.1#a5e2af5522a1edcab963447eec649700\n    :: Signature ok" in c.out
    assert "lib2fail/0.1#70a185be5a95af3dde25b74ae800b2f2\n    :: Signature ok" in c.out
    assert "lib3fail/0.1#09ccc766ddd11c96aa78307b3f166fd6\n    :: Failed: sign failed" in c.out

    # Upload sign fails if package signing fails
    c.run("upload * -c -r default", assert_error=True)
    assert "lib1ok/0.1#a5e2af5522a1edcab963447eec649700\n\t:: Package already signed by the same provider" in c.out
    assert "lib2fail/0.1#70a185be5a95af3dde25b74ae800b2f2\n\t:: Warn: Package already signed by another provider" in c.out
    assert "ERROR: \n[Package signing plugin]\n  lib3fail/0.1#09ccc766ddd11c96aa78307b3f166fd6\n\t:: sign failed" in c.out

    # If upload sign failed, no packages should be uploaded
    c.run("list * -r default")
    assert "WARN: There are no matching recipe references" in c.out

    # Upload packages individually to avoid previous failure
    c.run("upload lib1ok* -c -r default")
    c.run("upload lib2fail* -c -r default")
    c.run("remove * -c")

    # Install verify command should fail if package is signed by another provider
    c.run("install --requires lib1ok/0.1 --requires lib2fail/0.1 -r default", assert_error=True)
    assert "lib1ok/0.1#a5e2af5522a1edcab963447eec649700\n\t:: Verification ok" in c.out
    assert "ERROR: Package 'lib2fail/0.1' not resolved: \n[Package signing plugin]\n  " \
           "lib2fail/0.1#70a185be5a95af3dde25b74ae800b2f2\n\t:: wrong provider" in c.out

    # Packages that failed in install verification should not appear as installed
    c.run("list *")
    assert "lib1ok" in c.out
    assert "lib2fail" not in c.out
    c.run("cache verify *")
    assert "lib1ok/0.1#a5e2af5522a1edcab963447eec649700\n    :: Verification ok" in c.out

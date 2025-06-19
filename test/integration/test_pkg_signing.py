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

        def sign(ref, artifacts_folder, signature_folder):
            print("Signing ref: ", ref)
            print("Signing folder: ", artifacts_folder)
            files = []
            for f in sorted(os.listdir(artifacts_folder)):
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    files.append(f)
            print("Signing files: ", sorted(files))
            signature = os.path.join(signature_folder, "signature.asc")
            open(signature, "w").write("\n".join(files))

        def verify(ref, artifacts_folder, signature_folder, files):
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
    print("INSTALL: ", c.out)
    # Lets force the retrieval of the sources
    c.run("install --requires=pkg/0.1 --build=*")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "VERIFYING  conanfile.py" not in c.out  # It doesn't re-verify previous contents
    assert "VERIFYING  conan_sources.tgz" in c.out
    print("INSTALL-BUILD: ", c.out)
    #c.run("remove * -r=default -c")
    #c.run("upload * -r=default --dry-run -c --force")
    print(c.out)
    c.run("cache check-integrity *")
    print(c.out)


def test_pkg_sign_verify_integrity():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os

        def sign(ref, artifacts_folder, signature_folder):
            print("Signing ref: ", ref)
            print("Signing folder: ", artifacts_folder)
            files = []
            for f in sorted(os.listdir(artifacts_folder)):
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    files.append(f)
            print("Signing files: ", sorted(files))
            signature = os.path.join(signature_folder, "signature.asc")
            open(signature, "w").write("\n".join(files))

        def verify(ref, artifacts_folder, signature_folder, files):
            print("FILES: ", files)
            is_package = ":" in str(ref)
            print("Verifying ref: ", ref)
            print("Verifying folder: ", artifacts_folder)
            signature = os.path.join(signature_folder, "signature.asc")
            build_dir = os.path.join(os.path.dirname(artifacts_folder), "b")
            build_dir_exists = os.path.exists(build_dir)
            if is_package and build_dir_exists and not os.path.exists(signature):
                print("WARN: Could not verify built package ", ref)
                return
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
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    assert "VERIFYING  conan_package.tgz" in c.out
    c.run("cache check-integrity *")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    assert "VERIFYING  conan_package.tgz" in c.out
    c.run("install --requires=pkg/0.1 --build=*")
    c.run("cache check-integrity *")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    assert "WARN: Could not verify built package" in c.out
    c.run("upload * -r=default --dry-run -c --force")
    c.run("cache check-integrity *")
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    assert "VERIFYING  conan_package.tgz" in c.out

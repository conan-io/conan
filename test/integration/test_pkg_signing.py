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


def test_pkg_sign_with_tools():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os

        def sign(ref, artifacts_folder, signature_folder, output, sign_tools):
            output.info("Signing reference")
            output.info(f"Signing folder: {artifacts_folder}")
            files = []
            c = sign_tools.create_summary_content()
            c["provider"] = "the provider"
            c["method"] = "the method"
            sign_tools.save_summary(c)
            signature = sign_tools.get_summary_file_path() + ".asc"
            files = []
            for f in sorted(os.listdir(artifacts_folder)):
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    files.append(f)
            open(signature, "w").write("\n".join(files))
            contents = open(signature).read()
            output.info(f"Sign contents: {contents}")

        def verify(ref, artifacts_folder, signature_folder, files, output, sign_tools):
            if not sign_tools.is_pkg_signed():
                output.warning("Package not signed, skipping verification")
                return "not signed"
            output.info("Verifying reference")
            output.info(f"Verifying folder {artifacts_folder}")
            summary = sign_tools.load_summary()
            output.info(f"Verifying sign provider: {summary.get('provider')}")
            output.info(f"Verifying sign method: {summary.get('method')}")
            signature = sign_tools.get_summary_file_path() + ".asc"
            contents = open(signature).read()
            output.info(f"Verifying contents: {contents}")
            for f in files:
                output.info(f"Verifying file {f}")
                if os.path.isfile(os.path.join(artifacts_folder, f)):
                    assert f in contents
            return "ok"
        """)
    c.save_home({"extensions/plugins/sign/sign.py": signer})
    c.run("create .")
    c.run("cache verify *")
    assert "WARN: Package not signed, skipping verification" in c.out
    c.run("upload * -r=default -c")
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a: Signing reference" in c.out
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "Verifying sign method: the method" in c.out
    assert "Verifying sign provider: the provider" in c.out
    assert "pkg/0.1#5e2d444a24c6bdf96fc141053eb3bb7a: Verifying reference" in c.out
    assert "Verifying file conanfile.py" in c.out
    assert "Verifying file conan_sources.tgz" not in c.out  # Sources not retrieved now
    assert "Verifying file conan_package.tgz" in c.out
    # Lets force the retrieval of the sources
    c.run("install --requires=pkg/0.1 --build=*")
    assert "Verifying file conanfile.py" not in c.out  # It doesn't re-verify previous contents
    assert "Verifying file conan_sources.tgz" in c.out

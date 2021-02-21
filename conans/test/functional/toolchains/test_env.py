import os
import platform
import textwrap

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_complete():
    cmake = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            def package(self):
                with chdir(self.package_folder):
                    save("mycmake.bat", "@echo off\necho MYCMAKE!!")
                    save("mycmake.sh", "@echo off\necho MYCMAKE!!")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                self.buildenv_info.prepend_path("PATH", self.package_folder)
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            def package(self):
                with chdir(self.package_folder):
                    save("mygtest.bat", "@echo off\necho MYGTEST!!")
                    save("mygtest.sh", "@echo off\necho MYGTEST!!")
                    os.chmod("mygtest.sh", 0o777)

            def package_info(self):
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.runenv_info.define("MYGTESTVAR", "MyGTestValue")
            """)
    client = TestClient()
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest})
    client.run("create cmake mycmake/0.1@")
    client.run("create gtest mygtest/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            generators = "VirtualEnv"
            build_requires = "mycmake/0.1"

            def build_requirements(self):
                self.build_requires("mygtest/0.1", force_host_context=True)
        """)

    # Some scripts in a random system folders, path adding to the profile [env]
    tmp_folder = temp_folder()
    save(os.path.join(tmp_folder, "mycompiler.bat"), "@echo off\n"
                                                     "echo MYCOMPILER!!\n"
                                                     "echo MYPATH=%PATH%")
    save(os.path.join(tmp_folder, "mycompiler.sh"), "echo MYCOMPILER!!\n"
                                                    "echo MYPATH=$PATH")
    os.chmod(os.path.join(tmp_folder, "mycompiler.sh"), 0o777)
    tmp_folder2 = temp_folder()
    save(os.path.join(tmp_folder2, "mycompiler.bat"), "@echo off\n"
                                                      "echo MYCOMPILER2!!\n"
                                                      "echo MYPATH2=%PATH%")
    save(os.path.join(tmp_folder2, "mycompiler.sh"), "echo MYCOMPILER2!!\n"
                                                     "echo MYPATH2=$PATH")
    os.chmod(os.path.join(tmp_folder2, "mycompiler.sh"), 0o777)

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"

    myprofile = textwrap.dedent("""
        [buildenv]
        PATH+=(path){}
        mypkg*:PATH=!
        mypkg*:PATH+=(path){}
        """.format(tmp_folder, tmp_folder2))
    client.save({"conanfile.py": conanfile,
                 "myprofile": myprofile,
                 "myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)

    client.run("install . -pr=myprofile")
    # Run the BUILD environment
    if platform.system() == "Windows":
        client.run_command("buildenv.bat && mycmake.bat && mygtest.bat && mycompiler.bat")
    else:
        client.run_command('bash -c "source buildenv.sh && mycmake.sh && '
                           'mygtest.sh && mycompiler.sh"')
    assert "MYCMAKE!!" in client.out
    assert "MYCOMPILER!!" in client.out
    assert "MYGTEST!!" in client.out

    # Run the RUN environment
    if platform.system() == "Windows":
        client.run_command("runenv.bat && myrunner.bat")
    else:
        client.run_command('bash -c "source runenv.sh && ./myrunner.sh"')
    assert "MYGTESTVAR=MyGTestValue!!" in client.out

    # Now with pkg-specific env-var
    client.run("install . mypkg/0.1@ -pr=myprofile")
    if platform.system() == "Windows":
        client.run_command('buildenv.bat && mycompiler.bat')
    else:
        client.run_command('bash -c "source buildenv.sh && mycompiler.sh"')
    assert "MYCOMPILER2!!" in client.out
    assert "MYPATH2=" in client.out

import os
import stat
import textwrap

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.files import load

base_conanfile = textwrap.dedent('''
        from conans import ConanFile

        class TestSystemReqs(ConanFile):
            name = "Test"
            version = "0.1"
            options = {"myopt": [True, False]}
            default_options = "myopt=True"

            def system_requirements(self):
                self.output.info("*+Running system requirements+*")
                %GLOBAL%
                return "Installed my stuff"
        ''')


@pytest.mark.xfail(reason="cache2.0: check this for 2.0, nre chache will recreate sys_reqs"
                          "every time")
def test_force_system_reqs_rerun():
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    client.run("install Test/0.1@user/channel")
    assert "*+Running system requirements+*" not in client.out
    ref = ConanFileReference.loads("Test/0.1@user/channel")
    reqs_file = client.get_latest_pkg_layout(ref).system_reqs_package()
    os.unlink(reqs_file)
    client.run("install Test/0.1@user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(reqs_file)


def test_local_system_requirements():
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    client.run("install .")
    assert "*+Running system requirements+*" in client.out

    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "self.run('fake command!')")}
    client.save(files)
    with pytest.raises(Exception) as exc:
        client.run("install .")
    assert "ERROR: while executing system_requirements(): " \
           "Error 127 while executing fake command!" in client.out
    assert "ERROR: Error in system requirements" in client.out


@pytest.mark.xfail(reason="cache2.0: check this for 2.0, new chache will recreate sys_reqs"
                          "every time")
def test_per_package():
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    client.run("export . user/testing")
    client.run("install Test/0.1@user/testing --build missing")
    assert "*+Running system requirements+*" in client.out
    ref = ConanFileReference.loads("Test/0.1@user/testing")
    assert not os.path.exists(client.get_latest_pkg_layout(ref).system_reqs_package())
    pref = PackageReference(ref, "f0ba3ca2c218df4a877080ba99b65834b9413798")
    load_file = load(client.get_latest_pkg_layout(pref).system_reqs_package())
    assert "Installed my stuff" in load_file

    # Run again
    client.run("install Test/0.1@user/testing --build missing")
    assert "*+Running system requirements+*" not in client.out
    assert not os.path.exists(client.get_latest_pkg_layout(ref).system_reqs_package())
    load_file = load(client.get_latest_pkg_layout(pref).system_reqs_package())
    assert "Installed my stuff" in load_file

    # Run with different option
    client.run("install Test/0.1@user/testing -o myopt=False --build missing")
    assert "*+Running system requirements+*" in client.out
    assert not os.path.exists(client.get_latest_pkg_layout(ref).system_reqs_package())
    pref2 = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
    load_file = load(client.get_latest_pkg_layout(pref2).system_reqs_package())
    assert "Installed my stuff" in load_file

    # remove packages
    client.run("remove Test* -f -p 544")
    layout1 = client.get_latest_pkg_layout(pref)
    layout2 = client.get_latest_pkg_layout(pref2)
    assert os.path.exists(layout1.system_reqs_package())
    client.run("remove Test* -f -p f0ba3ca2c218df4a877080ba99b65834b9413798")
    assert not os.path.exists(layout1.system_reqs_package())
    assert os.path.exists(layout2.system_reqs_package())
    client.run("remove Test* -f -p %s" % NO_SETTINGS_PACKAGE_ID)
    assert not os.path.exists(layout1.system_reqs_package())
    assert not os.path.exists(layout2.system_reqs_package())


@pytest.mark.xfail(reason="cache2.0: check this for 2.0, new chache will recreate sys_reqs"
                          "every time")
def test_global():
    client = TestClient()
    files = {
        'conanfile.py': base_conanfile.replace("%GLOBAL%",
                                               "self.global_system_requirements=True")
    }
    client.save(files)
    client.run("export . user/testing")
    client.run("install Test/0.1@user/testing --build missing")
    assert "*+Running system requirements+*" in client.out
    ref = ConanFileReference.loads("Test/0.1@user/testing")
    pref = PackageReference(ref, "a527106fd9f2e3738a55b02087c20c0a63afce9d")
    assert not os.path.exists(client.get_latest_pkg_layout(pref).system_reqs_package())
    load_file = load(client.get_latest_pkg_layout(ref).system_reqs_package())
    assert "Installed my stuff" in load_file

    # Run again
    client.run("install Test/0.1@user/testing --build missing")
    assert "*+Running system requirements+*" not in client.out
    assert not os.path.exists(client.get_latest_pkg_layout(pref).system_reqs_package())
    load_file = load(client.get_latest_pkg_layout(ref).system_reqs_package())
    assert "Installed my stuff" in load_file

    # Run with different option
    client.run("install Test/0.1@user/testing -o myopt=False --build missing")
    assert "*+Running system requirements+*" not in client.out
    pref2 = PackageReference(ref, "54c9626b48cefa3b819e64316b49d3b1e1a78c26")
    assert not os.path.exists(client.get_latest_pkg_layout(pref).system_reqs_package())
    assert not os.path.exists(client.get_latest_pkg_layout(pref2).system_reqs_package())
    load_file = load(client.get_latest_pkg_layout(ref).system_reqs_package())
    assert "Installed my stuff" in load_file

    # remove packages
    client.run("remove Test* -f -p")
    assert not os.path.exists(client.get_latest_pkg_layout(pref).system_reqs_package())
    assert not os.path.exists(client.get_latest_pkg_layout(pref2).system_reqs_package())
    assert not os.path.exists(client.get_latest_pkg_layout(ref).system_reqs_package())


def test_wrong_output():
    client = TestClient()
    files = {
        'conanfile.py':
            base_conanfile.replace("%GLOBAL%", "").replace('"Installed my stuff"', 'None')
    }
    client.save(files)
    client.run("export . user/testing")
    client.run("install Test/0.1@user/testing --build missing")
    assert "*+Running system requirements+*" in client.out
    ref = ConanFileReference.loads("Test/0.1@user/testing")
    pkg_layout = client.get_latest_pkg_layout(ref)
    assert not os.path.exists(pkg_layout.system_reqs())
    load_file = load(pkg_layout.system_reqs_package())
    assert '' == load_file


@pytest.mark.xfail(reason="cache2.0: will this be maintained with the new cache?")
def test_remove_system_reqs():
    ref = ConanFileReference.loads("Test/0.1@user/channel")
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(ref).system_reqs_package())

    # create package to populate system_reqs folder
    assert not os.path.exists(system_reqs_path)
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(system_reqs_path)

    # a new build must not remove or re-run
    client.run("create . user/channel")
    assert "*+Running system requirements+*" not in client.out
    assert os.path.exists(system_reqs_path)

    # remove system_reqs global
    client.run("remove --system-reqs Test/0.1@user/channel")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" in client.out
    assert not os.path.exists(system_reqs_path)

    # re-create system_reqs folder
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(system_reqs_path)

    # Wildcard system_reqs removal
    ref_other = ConanFileReference.loads("Test/0.1@user/channel_other")
    system_reqs_path_other = os.path.dirname(client.get_latest_pkg_layout(ref_other).system_reqs())

    client.run("create . user/channel_other")
    client.run("remove --system-reqs '*'")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" in client.out
    assert "Cache system_reqs from Test/0.1@user/channel_other has been removed" in client.out
    assert not os.path.exists(system_reqs_path)
    assert not os.path.exists(system_reqs_path_other)

    # Check that wildcard isn't triggered randomly
    client.run("create . user/channel_other")
    client.run("remove --system-reqs Test/0.1@user/channel")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" in client.out
    assert "Cache system_reqs from Test/0.1@user/channel_other has been removed" not in client.out
    assert not os.path.exists(system_reqs_path)
    assert os.path.exists(system_reqs_path_other)

    # Check partial wildcard
    client.run("create . user/channel")
    client.run("remove --system-reqs Test/0.1@user/channel_*")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" not in client.out
    assert "Cache system_reqs from Test/0.1@user/channel_other has been removed" in client.out
    assert os.path.exists(system_reqs_path)
    assert not os.path.exists(system_reqs_path_other)


@pytest.mark.parametrize("command, exc_output_expected", [
    ("remove --system-reqs",
     "ERROR: Please specify a valid pattern or reference to be cleaned"),
    # wrong file reference should be treated as error
    ("remove --system-reqs foo/version@bar/testing",
     "ERROR: Unable to remove system_reqs: foo/version@bar/testing does not exist"),
    # package is not supported with system_reqs
    ("remove --system-reqs foo/bar@foo/bar -p f0ba3ca2c218df4a877080ba99b65834b9413798",
     "ERROR: '-t' and '-p' parameters can't be used at the same time")
])
@pytest.mark.xfail(reason="cache2.0: will this be maintained with the new cache?")
def test_invalid_remove_reqs(command, exc_output_expected):
    client = TestClient()

    with pytest.raises(Exception):
        client.run(command)
    assert exc_output_expected in client.out


@pytest.mark.xfail(reason="cache2.0: is remote --system-reqs maintained in 2.0?")
def test_permission_denied_remove_system_reqs():
    ref = ConanFileReference.loads("Test/0.1@user/channel")
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(ref).system_reqs_package())

    # create package to populate system_reqs folder
    assert not os.path.exists(system_reqs_path)
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(system_reqs_path)

    # remove write permission
    current = stat.S_IMODE(os.lstat(system_reqs_path).st_mode)
    os.chmod(system_reqs_path, current & ~stat.S_IWRITE)

    # friendly message for permission error
    with pytest.raises(Exception) as exc:
        client.run("remove --system-reqs Test/0.1@user/channel")
    assert "ERROR: Unable to remove system_reqs:" in client.out

    assert os.path.exists(system_reqs_path)

    # restore write permission so the temporal folder can be deleted later
    os.chmod(system_reqs_path, current | stat.S_IWRITE)


@pytest.mark.xfail(reason="cache2.0: this does not make sense any more. We always create the "
                          "package in a new folder")
def test_duplicate_remove_system_reqs():
    ref = ConanFileReference.loads("Test/0.1@user/channel")
    client = TestClient()
    files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
    client.save(files)
    system_reqs_path = os.path.dirname(client.get_latest_pkg_layout(ref).system_reqs_package())

    # create package to populate system_reqs folder
    assert not os.path.exists(system_reqs_path)
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(system_reqs_path)

    # a new build must not remove or re-run
    client.run("create . user/channel")
    assert "*+Running system requirements+*" not in client.out
    assert os.path.exists(system_reqs_path)

    # remove system_reqs global
    client.run("remove --system-reqs Test/0.1@user/channel")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" in client.out
    assert not os.path.exists(system_reqs_path)

    # try to remove system_reqs global again
    client.run("remove --system-reqs Test/0.1@user/channel")
    assert "Cache system_reqs from Test/0.1@user/channel has been removed" in client.out
    assert not os.path.exists(system_reqs_path)

    # re-create system_reqs folder
    client.run("create . user/channel")
    assert "*+Running system requirements+*" in client.out
    assert os.path.exists(system_reqs_path)

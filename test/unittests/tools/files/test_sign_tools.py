import os

import pytest

from conan.internal.rest.pkg_sign import PkgSignaturesTools
from conan.test.utils.tools import temp_folder, save_files


@pytest.fixture
def pkg_sign_tools():
    main_folder = temp_folder()
    artifacts_folder = os.path.join(main_folder, "af")
    os.mkdir(artifacts_folder)
    signature_folder = os.path.join(main_folder, "sf")
    os.mkdir(signature_folder)
    save_files(artifacts_folder, {"conan_package.tgz": "", "conanmanifest.txt": ""})
    return PkgSignaturesTools(artifacts_folder, signature_folder)


def test_get_summary_file_path(pkg_sign_tools):
    sfp = pkg_sign_tools.get_summary_file_path()
    assert f"sf{os.path.sep}sign-summary.json" in sfp


def test_create_summary_content(pkg_sign_tools):
    c = pkg_sign_tools.create_summary_content()
    assert c.get("method") is None
    assert c.get("provider") is None
    assert c.get("files").get("conan_package.tgz")
    assert c.get("files").get("conanmanifest.txt")


def test_save_load_summary(pkg_sign_tools):
    c = pkg_sign_tools.create_summary_content()
    c["provider"] = "conan"
    c["method"] = "sigstore"
    pkg_sign_tools.save_summary(c)
    assert os.path.exists(os.path.join(pkg_sign_tools._signature_folder, "sign-summary.json"))
    summary = pkg_sign_tools.load_summary()
    assert summary.get("provider") == "conan"
    assert summary.get("method") == "sigstore"
    assert list(summary.get("files").keys()) == ["conan_package.tgz", "conanmanifest.txt"]


def test_is_pkg_signed(pkg_sign_tools):
    assert not pkg_sign_tools.is_pkg_signed()
    c = pkg_sign_tools.create_summary_content()
    pkg_sign_tools.save_summary(c)
    assert pkg_sign_tools.is_pkg_signed()

import os

import pytest

from conan.test.utils.tools import temp_folder, save_files

from conan.tools.pkg_signing.plugin import (create_summary_content, get_summary_file_path,
                                            load_summary, save_summary)

@pytest.fixture
def pkg_sign_tools():
    main_folder = temp_folder()
    artifacts_folder = os.path.join(main_folder, "af")
    os.mkdir(artifacts_folder)
    signature_folder = os.path.join(main_folder, "sf")
    os.mkdir(signature_folder)
    save_files(artifacts_folder, {"conan_package.tgz": "", "conanmanifest.txt": ""})
    return artifacts_folder, signature_folder


def test_get_summary_file_path(pkg_sign_tools):
    _, signature_folder = pkg_sign_tools
    sfp = get_summary_file_path(signature_folder)
    assert f"sf{os.path.sep}sign-summary.json" in sfp


def test_create_summary_content(pkg_sign_tools):
    artifacts_folder, _ = pkg_sign_tools
    c = create_summary_content(artifacts_folder)
    assert c.get("method") is None
    assert c.get("provider") is None
    assert c.get("files").get("conan_package.tgz")
    assert c.get("files").get("conanmanifest.txt")


def test_save_load_summary(pkg_sign_tools):
    artifacts_folder, signature_folder = pkg_sign_tools
    c = create_summary_content(artifacts_folder)
    c["provider"] = "conan"
    c["method"] = "sigstore"
    save_summary(signature_folder, c)
    assert os.path.exists(os.path.join(signature_folder, "sign-summary.json"))
    summary = load_summary(signature_folder)
    assert summary.get("provider") == "conan"
    assert summary.get("method") == "sigstore"
    assert list(summary.get("files").keys()) == ["conan_package.tgz", "conanmanifest.txt"]

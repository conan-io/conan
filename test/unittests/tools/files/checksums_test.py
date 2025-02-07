import os

from conan.tools.files import check_md5, check_sha1, check_sha256
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


def test_checksums():
    tmp = temp_folder()
    file_path = os.path.join(tmp, "foo.txt")
    save(os.path.join(tmp, "foo.txt"), "contents")

    check_md5(None, file_path, "98bf7d8c15784f0a3d63204441e1e2aa")
    check_sha1(None, file_path, "4a756ca07e9487f482465a99e8286abc86ba4dc7")
    check_sha256(None, file_path, "d1b2a59fbea7e20077af9f91b27e95e865061b270be03ff539ab3b73587882e8")


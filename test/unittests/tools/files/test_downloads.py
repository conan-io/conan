import os
import shutil

import pytest

from conan.tools.files import ftp_download, download, get
from conans.errors import ConanException, AuthenticationException
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output, TestRequester
from conans.util.files import save, load, chdir, mkdir


@pytest.mark.skip(reason="This causes more troubles than benefits, external ftp download is testing "
                         "very little conan code, mostly python")
class TestFTP:

    def test_ftp_auth(self):
        filename = "/pub/example/readme.txt"
        conanfile = ConanFileMock()
        ftp_download(conanfile, "test.rebex.net", filename, "demo", "password")
        assert os.path.exists(os.path.basename(filename))

    def test_ftp_invalid_path(self):
        with pytest.raises(ConanException) as exc:
            conanfile = ConanFileMock()
            ftp_download(conanfile, "test.rebex.net", "invalid-file", "demo", "password")
        assert "550 The system cannot find the file specified." in str(exc.value)
        assert not os.path.exists("invalid-file")

    def test_ftp_invalid_auth(self):
        with pytest.raises(ConanException) as exc:
            conanfile = ConanFileMock()
            ftp_download(conanfile, "test.rebex.net", "readme.txt", "demo", "invalid")
        assert "530 User cannot log in." in str(exc.value)
        assert not os.path.exists("readme.txt")


class TestDownload:
    @pytest.fixture()
    def _manual(self):
        file_server = TestFileServer()
        save(os.path.join(file_server.store, "manual.html"), "this is some content")
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({"file_server": file_server})
        return conanfile, file_server

    def test_download(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        download(conanfile, file_server.fake_url + "/manual.html", dest, retry=3, retry_wait=0)
        content = load(dest)
        assert content == "this is some content"

        # Can re-download
        download(conanfile, file_server.fake_url + "/manual.html", dest, retry=3, retry_wait=0)
        content = load(dest)
        assert content == "this is some content"

    def test_download_iterate_url(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        output = RedirectedTestOutput()
        with redirect_output(output):
            download(conanfile, ["invalid", file_server.fake_url + "/manual.html"], dest,
                     retry=3, retry_wait=0)
        content = load(dest)
        assert content == "this is some content"
        assert "Trying another mirror." in str(output)

    def test_download_forbidden(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        # Not authorized
        with pytest.raises(AuthenticationException) as exc:
            download(conanfile, file_server.fake_url + "/forbidden", dest)
        assert "403 Forbidden" in str(exc.value)

    def test_download_unauthorized_no_credentials(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        # Not authorized without credentials
        with pytest.raises(AuthenticationException) as exc:
            download(conanfile, file_server.fake_url + "/basic-auth/manual.html", dest)
        assert "401 Unauthorized" in str(exc.value)
        assert "Not authorized" in str(exc.value)

    def test_download_unauthorized_literal_none_credentials(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        # os.getenv('SOME_UNSET_VARIABLE') causes source_credentials.json to contain
        # "None" as a string literal, causing auth to be ("None", "None") or with
        # a "None" token.
        auth = ("None", "None")
        with pytest.raises(AuthenticationException) as exc:
            download(conanfile, file_server.fake_url + "/basic-auth/manual.html", dest, auth=auth)
        assert "401 Unauthorized" in str(exc.value)
        assert "Bad credentials" in str(exc.value)

    def test_download_authorized(self, _manual):
        conanfile, file_server = _manual
        dest = os.path.join(temp_folder(), "manual.html")
        with pytest.raises(AuthenticationException):
            download(conanfile, file_server.fake_url + "/basic-auth/manual.html",
                     dest, auth=("user", "wrong"), retry=0, retry_wait=0)

        # Authorized
        download(conanfile, file_server.fake_url + "/basic-auth/manual.html", dest,
                 auth=("user", "password"), retry=0, retry_wait=0)

        # Authorized using headers
        download(conanfile, file_server.fake_url + "/basic-auth/manual.html", dest,
                 headers={"Authorization": "Bearer password"}, retry=0, retry_wait=0)

    def test_download_retries_errors(self):
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({})

        with pytest.raises(ConanException):
            output = RedirectedTestOutput()
            with redirect_output(output):
                download(conanfile, "http://fakesomething", "path", retry=2, retry_wait=0.1)
        assert str(output).count("Waiting 0.1 seconds to retry...") == 2

    def test_download_retries_500_errors(self, _manual):
        conanfile, file_server = _manual
        with pytest.raises(ConanException):
            output = RedirectedTestOutput()
            with redirect_output(output):
                download(conanfile, file_server.fake_url + "/internal_error", "path",
                         retry=2, retry_wait=0.1)
        assert str(output).count("Waiting 0.1 seconds to retry...") == 2

    def test_download_no_retries_errors(self):
        # Not found error will not retry
        file_server = TestFileServer()
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({"file_server": file_server})
        file_path = os.path.join(temp_folder(), "file.txt")
        with pytest.raises(ConanException):
            download(conanfile, file_server.fake_url + "/manual.html", file_path,
                     retry=2, retry_wait=0)
        assert "Waiting" not in str(conanfile.output)
        assert "retry" not in str(conanfile.output)

    def test_download_localfile(self):
        conanfile = ConanFileMock()

        file_location = os.path.join(temp_folder(), "file.txt")
        save(file_location, "this is some content")

        file_url = f"file:///{file_location}"
        file_md5 = "736db904ad222bf88ee6b8d103fceb8e"

        dest = os.path.join(temp_folder(), "downloaded_file.txt")
        download(conanfile, file_url, dest, md5=file_md5)
        content = load(dest)
        assert "this is some content" == content

    def test_download_localfile_notfound(self):
        conanfile = ConanFileMock()

        file_url = "file:///path/to/missing/file.txt"
        dest = os.path.join(temp_folder(), "file.txt")

        with pytest.raises(FileNotFoundError) as exc:
            download(conanfile, file_url, dest)

        assert "No such file" in str(exc.value)


class TestGet:

    @pytest.fixture()
    def _my_zip(self):
        tmp_folder = temp_folder()
        file_path = os.path.join(tmp_folder, "sample.tar.gz")
        test_folder = os.path.join(tmp_folder, "test_folder")
        zipped_file = os.path.join(test_folder, "myfile.txt")
        save(zipped_file, "myfile contents!")
        import tarfile
        tar_file = tarfile.open(file_path, "w:gz")
        tar_file.add(test_folder, "test_folder")
        tar_file.add(zipped_file, "test_folder/myfile.txt")
        tar_file.close()
        assert (os.path.exists(file_path))

        file_server = TestFileServer()
        shutil.copy2(file_path, file_server.store)
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({"file_server": file_server})

        return conanfile, file_server

    def test_get_tgz(self, _my_zip):
        conanfile, file_server = _my_zip
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, file_server.fake_url + "/sample.tar.gz", retry=0, retry_wait=0)
            assert load("test_folder/myfile.txt") == "myfile contents!"

    def test_get_tgz_strip_root(self, _my_zip):
        conanfile, file_server = _my_zip
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, file_server.fake_url + "/sample.tar.gz", retry=0, retry_wait=0,
                strip_root=True)
            assert load("myfile.txt") == "myfile contents!"


class TestGetGz:
    @pytest.fixture()
    def _my_gz(self):
        tmp = temp_folder()
        filepath = os.path.join(tmp, "test.txt.gz")
        import gzip
        with gzip.open(filepath, "wb") as f:
            f.write(b"hello world zipped!")

        file_server = TestFileServer()
        folder = os.path.join(file_server.store, "gz")
        mkdir(folder)
        shutil.copy2(filepath, folder)
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({"file_server": file_server})
        return conanfile, file_server

    def test_get_gunzip(self, _my_gz):
        conanfile, file_server = _my_gz
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, file_server.fake_url + "/gz/test.txt.gz", retry=0, retry_wait=0)
            assert load("test.txt") == "hello world zipped!"

    def test_get_gunzip_destination(self, _my_gz):
        conanfile, file_server = _my_gz
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, file_server.fake_url + "/gz/test.txt.gz", destination="myfile.doc",
                retry=0, retry_wait=0)
            assert load("myfile.doc") == "hello world zipped!"

    def test_get_gunzip_destination_subfolder(self, _my_gz):
        conanfile, file_server = _my_gz
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, file_server.fake_url + "/gz/test.txt.gz",
                destination="sub/myfile.doc", retry=0, retry_wait=0)
            assert load("sub/myfile.doc") == "hello world zipped!"

    def test_get_filename_error(self):
        # Test: File name cannot be deduced from '?file=1'
        file_server = TestFileServer()
        conanfile = ConanFileMock()
        conanfile._conan_helpers.requester = TestRequester({"file_server": file_server})

        with pytest.raises(ConanException) as error:
            get(conanfile, file_server.fake_url + "?file=1")
        assert "Cannot deduce file name from the url" in str(error.value)

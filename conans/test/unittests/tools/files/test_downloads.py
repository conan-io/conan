import os
import platform

import pytest
import requests
from bottle import HTTPError, auth_basic, static_file

from conan.tools.files import ftp_download, download, get
from conans.client.tools import chdir
from conans.errors import ConanException, AuthenticationException
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import StoppableThreadBottle
from conans.util.files import save, load


@pytest.mark.skip(msg="This causes more troubles than benefits, external ftp download is testing "
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


@pytest.fixture()
def bottle_server():
    http_server = StoppableThreadBottle()

    @http_server.server.get('/forbidden')
    def get_forbidden():
        return HTTPError(403, "Access denied.")

    folder = temp_folder()
    manual_file = os.path.join(folder, "manual.html")
    save(manual_file, "this is some content")

    @http_server.server.get("/manual.html")
    def get_manual():
        return static_file(os.path.basename(manual_file), os.path.dirname(manual_file))

    def check_auth(user, password):
        # Check user/password here
        return user == "user" and password == "passwd"

    @http_server.server.get('/basic-auth/<user>/<password>')
    @auth_basic(check_auth)
    def get_manual_auth(user, password):
        return static_file(os.path.basename(manual_file), os.path.dirname(manual_file))

    @http_server.server.get("/error_url")
    def error_url():
        from bottle import response
        response.status = 500
        return 'This always fail'

    http_server.run_server()
    yield http_server
    http_server.stop()


@pytest.mark.slow
class TestDownload:

    def test_download(self, bottle_server):
        dest = os.path.join(temp_folder(), "manual.html")
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        download(conanfile, "http://localhost:%s/manual.html" % bottle_server.port, dest, retry=3,
                 retry_wait=0)
        content = load(dest)
        assert content == "this is some content"

        # Can re-download
        download(conanfile, "http://localhost:%s/manual.html" % bottle_server.port, dest, retry=3,
                 retry_wait=0)

    def test_download_iterate_url(self, bottle_server):
        dest = os.path.join(temp_folder(), "manual.html")
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        download(conanfile, ["invalid",
                             "http://localhost:%s/manual.html" % bottle_server.port], dest, retry=3,
                 retry_wait=0)
        content = load(dest)
        assert content == "this is some content"
        assert "Trying another mirror." in str(conanfile.output)

    def test_download_forbidden(self, bottle_server):
        dest = os.path.join(temp_folder(), "manual.html")
        # Not authorized
        with pytest.raises(AuthenticationException) as exc:
            conanfile = ConanFileMock()
            conanfile._conan_requester = requests
            download(conanfile, "http://localhost:%s/forbidden" % bottle_server.port, dest)
        assert "403: Forbidden" in str(exc.value)

    def test_download_authorized(self, bottle_server):
        # Not authorized
        dest = os.path.join(temp_folder(), "manual.html")
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        with pytest.raises(AuthenticationException):
            download(conanfile, "http://localhost:%s/basic-auth/user/passwd" % bottle_server.port,
                     dest, retry=0, retry_wait=0)

        # Authorized
        download(conanfile, "http://localhost:%s/basic-auth/user/passwd" % bottle_server.port, dest,
                 auth=("user", "passwd"), retry=0, retry_wait=0)

        # Authorized using headers
        download(conanfile, "http://localhost:%s/basic-auth/user/passwd" % bottle_server.port, dest,
                 headers={"Authorization": "Basic dXNlcjpwYXNzd2Q="}, retry=0, retry_wait=0)

    def test_download_retries_errors(self):
        # unreachable server will retry
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        file_path = os.path.join(temp_folder(), "file.txt")
        with pytest.raises(ConanException):
            download(conanfile, "http://fakeurl3.es/nonexists", file_path, retry=2, retry_wait=1)
        assert str(conanfile.output).count("Waiting 1 seconds to retry...") == 2

    def test_download_retries_500_errors(self, bottle_server):
        # 500 internal also retries
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        file_path = os.path.join(temp_folder(), "file.txt")
        with pytest.raises(ConanException):
            download(conanfile, "http://localhost:%s/error_url" % bottle_server.port,
                     file_path, retry=1, retry_wait=0)
        assert str(conanfile.output).count("Waiting 0 seconds to retry...") == 1

    def test_download_no_retries_errors(self, bottle_server):
        # Not found error will not retry
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        file_path = os.path.join(temp_folder(), "file.txt")
        with pytest.raises(ConanException):
            download(conanfile, "http://localhost:%s/notexisting" % bottle_server.port, file_path,
                     retry=2, retry_wait=0)
        assert "Waiting" not in str(conanfile.output)
        assert "retry" not in str(conanfile.output)

    def test_download_localfile(self):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests

        file_location =  os.path.join(temp_folder(), "file.txt")
        save(file_location, "this is some content")

        file_url = f"file:///{file_location}"
        file_md5 = "736db904ad222bf88ee6b8d103fceb8e"

        dest = os.path.join(temp_folder(), "downloaded_file.txt")
        download(conanfile, file_url, dest, md5=file_md5)
        content = load(dest)
        assert "this is some content" == content

    def test_download_localfile_notfound(self):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests

        file_url = "file:///path/to/missing/file.txt"
        dest = os.path.join(temp_folder(), "file.txt")

        with pytest.raises(FileNotFoundError) as exc:
            download(conanfile, file_url, dest)

        assert "No such file" in str(exc.value)

@pytest.fixture()
def bottle_server_zip():
    http_server = StoppableThreadBottle()

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

    @http_server.server.get("/this_is_not_the_file_name")
    def get_file():
        return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

    @http_server.server.get("/")
    def get_file2():
        return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

    @http_server.server.get("/sample.tgz")
    def get_file3():
        return static_file(os.path.basename(file_path), root=os.path.dirname(file_path))

    tmp = temp_folder()
    filepath = os.path.join(tmp, "test.txt.gz")
    import gzip
    with gzip.open(filepath, "wb") as f:
        f.write(b"hello world zipped!")

    @http_server.server.get("/test.txt.gz")
    def get_file():
        return static_file(os.path.basename(filepath), root=os.path.dirname(filepath),
                           mimetype="application/octet-stream")

    http_server.run_server()
    yield http_server
    http_server.stop()


class TestGet:

    def test_get_tgz(self, bottle_server_zip):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, "http://localhost:%s/sample.tgz" % bottle_server_zip.port,
                retry=0, retry_wait=0)
            assert load("test_folder/myfile.txt") == "myfile contents!"

    def test_get_tgz_strip_root(self, bottle_server_zip):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, "http://localhost:%s/sample.tgz" % bottle_server_zip.port,
                retry=0, retry_wait=0, strip_root=True)
            assert load("myfile.txt") == "myfile contents!"

    def test_get_gunzip(self, bottle_server_zip):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, "http://localhost:%s/test.txt.gz" % bottle_server_zip.port,
                retry=0, retry_wait=0)
            assert load("test.txt") == "hello world zipped!"

    def test_get_gunzip_destination(self, bottle_server_zip):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, "http://localhost:%s/test.txt.gz" % bottle_server_zip.port,
                destination="myfile.doc", retry=0, retry_wait=0)
            assert load("myfile.doc") == "hello world zipped!"

    def test_get_gunzip_destination_subfolder(self, bottle_server_zip):
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            get(conanfile, "http://localhost:%s/test.txt.gz" % bottle_server_zip.port,
                destination="sub/myfile.doc", retry=0, retry_wait=0)
            assert load("sub/myfile.doc") == "hello world zipped!"

    def test_get_filename_error(self, bottle_server_zip):
        # Test: File name cannot be deduced from '?file=1'
        conanfile = ConanFileMock()
        conanfile._conan_requester = requests
        with pytest.raises(ConanException) as error:
            get(conanfile, "http://localhost:%s/?file=1" % bottle_server_zip.port)
        assert "Cannot deduce file name from the url" in str(error.value)

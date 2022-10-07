import os
import shutil

from urllib.parse import urlparse, urlsplit
from contextlib import contextmanager

from conan.api.output import ConanOutput
from conans.client.downloaders.file_downloader import FileDownloader
from conans.errors import ConanException
from conans.util.files import mkdir, rmdir, remove, unzip, chdir
from conans.util.runners import detect_runner


def _hide_password(resource):
    """
    Hide password from url/file path

    :param resource: string with url or file path
    :return: resource with hidden password if present
    """
    password = urlparse(resource).password
    return resource.replace(password, "<hidden>") if password else resource


@contextmanager
def tmp_config_install_folder(cache):
    tmp_folder = os.path.join(cache.cache_folder, "tmp_config_install")
    # necessary for Mac OSX, where the temp folders in /var/ are symlinks to /private/var/
    tmp_folder = os.path.realpath(tmp_folder)
    rmdir(tmp_folder)
    mkdir(tmp_folder)
    try:
        yield tmp_folder
    finally:
        rmdir(tmp_folder)


def _process_git_repo(config, cache):
    output = ConanOutput()
    output.info("Trying to clone repo: %s" % config.uri)
    with tmp_config_install_folder(cache) as tmp_folder:
        with chdir(tmp_folder):
            args = config.args or ""
            ret, out = detect_runner('git clone "{}" . {}'.format(config.uri, args))
            if ret != 0:
                raise ConanException("Can't clone repo: {}".format(out))
            output.info("Repo cloned!")
        _process_folder(config, tmp_folder, cache)


def _process_zip_file(config, zippath, cache, tmp_folder, first_remove=False):
    unzip(zippath, tmp_folder)
    if first_remove:
        os.unlink(zippath)
    _process_folder(config, tmp_folder, cache)


def _filecopy(src, filename, dst):
    # https://github.com/conan-io/conan/issues/6556
    # This is just a local convenience for "conan config install", using copyfile to avoid
    # copying with permissions that later cause bugs
    src = os.path.join(src, filename)
    dst = os.path.join(dst, filename)
    # Clear the destination file
    if os.path.exists(dst):
        if os.path.isdir(dst):  # dst was a directory and now src is a file
            rmdir(dst)
        else:
            remove(dst)
    shutil.copyfile(src, dst)


def _process_file(directory, filename, config, cache, folder):
    output = ConanOutput()
    if filename == "settings.yml":
        output.info("Installing settings.yml")
        _filecopy(directory, filename, cache.cache_folder)
    elif filename == "remotes.json":
        output.info("Defining remotes from remotes.json")
        _filecopy(directory, filename, cache.cache_folder)
    else:
        relpath = os.path.relpath(directory, folder)
        if config.target_folder:
            target_folder = os.path.join(cache.cache_folder, config.target_folder, relpath)
        else:
            target_folder = os.path.join(cache.cache_folder, relpath)

        if os.path.exists(target_folder):
            if os.path.isfile(target_folder):  # Existed as a file and now should be a folder
                remove(target_folder)

        mkdir(target_folder)
        output.info("Copying file %s to %s" % (filename, target_folder))
        _filecopy(directory, filename, target_folder)


def _process_folder(config, folder, cache):
    if not os.path.isdir(folder):
        raise ConanException("No such directory: '%s'" % str(folder))
    if config.source_folder:
        folder = os.path.join(folder, config.source_folder)
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            _process_file(root, f, config, cache, folder)


def _process_download(config, cache, requester):
    output = ConanOutput()
    with tmp_config_install_folder(cache) as tmp_folder:
        output.info("Trying to download  %s" % _hide_password(config.uri))
        path = urlsplit(config.uri).path
        filename = os.path.basename(path)
        zippath = os.path.join(tmp_folder, filename)
        try:
            downloader = FileDownloader(requester=requester)
            downloader.download(url=config.uri, file_path=zippath, verify_ssl=config.verify_ssl,
                                retry=1)
            _process_zip_file(config, zippath, cache, tmp_folder, first_remove=True)
        except Exception as e:
            raise ConanException("Error while installing config from %s\n%s" % (config.uri, str(e)))


class _ConfigOrigin(object):
    def __init__(self, data):
        self.type = data.get("type")
        self.uri = data.get("uri")
        self.verify_ssl = data.get("verify_ssl")
        self.args = data.get("args")
        self.source_folder = data.get("source_folder")
        self.target_folder = data.get("target_folder")

    def __eq__(self, other):
        return (self.type == other.type and self.uri == other.uri and
                self.args == other.args and self.source_folder == other.source_folder
                and self.target_folder == other.target_folder)

    def json(self):
        return {"type": self.type,
                "uri": self.uri,
                "verify_ssl": self.verify_ssl,
                "args": self.args,
                "source_folder": self.source_folder,
                "target_folder": self.target_folder}

    @staticmethod
    def from_item(uri, config_type, verify_ssl, args, source_folder, target_folder):
        config = _ConfigOrigin({})
        if config_type:
            config.type = config_type
        else:
            if uri.endswith(".git"):
                config.type = "git"
            elif os.path.isdir(uri):
                config.type = "dir"
            elif os.path.isfile(uri):
                config.type = "file"
            elif uri.startswith("http"):
                config.type = "url"
            else:
                raise ConanException("Unable to deduce type config install: %s" % uri)
        config.source_folder = source_folder
        config.target_folder = target_folder
        config.args = args
        config.verify_ssl = verify_ssl
        if os.path.exists(uri):
            uri = os.path.abspath(uri)
        config.uri = uri
        return config


def _is_compressed_file(filename):
    open(filename, "r")  # Check if the file exist and can be opened
    import zipfile
    if zipfile.is_zipfile(filename):
        return True
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar") or filename.endswith(".gz") or
            filename.endswith(".tar.xz") or filename.endswith(".txz")):
        return True
    return False


def _process_config(config, cache, requester):
    try:
        if config.type == "git":
            _process_git_repo(config, cache)
        elif config.type == "dir":
            _process_folder(config, config.uri, cache)
        elif config.type == "file":
            if _is_compressed_file(config.uri):
                with tmp_config_install_folder(cache) as tmp_folder:
                    _process_zip_file(config, config.uri, cache, tmp_folder)
            else:
                dirname, filename = os.path.split(config.uri)
                _process_file(dirname, filename, config, cache, dirname)
        elif config.type == "url":
            _process_download(config, cache, requester=requester)
        else:
            raise ConanException("Unable to process config install: %s" % config.uri)
    except Exception as e:
        raise ConanException("Failed conan config install: %s" % str(e))


def configuration_install(app, uri, verify_ssl, config_type=None,
                          args=None, source_folder=None, target_folder=None):
    cache, requester = app.cache, app.requester

    # Execute and store the new one
    config = _ConfigOrigin.from_item(uri, config_type, verify_ssl, args,
                                     source_folder, target_folder)
    _process_config(config, cache, requester)

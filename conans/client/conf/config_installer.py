import os
import shutil
from six.moves.urllib.parse import urlparse

from conans.tools import unzip
from conans.util.files import rmdir, mkdir, walk
from conans.client.remote_registry import RemoteRegistry
from conans import tools
from conans.errors import ConanException
import subprocess


def _hide_password(resource):
    """
    Hide password from url/file path

    :param resource: string with url or file path
    :return: resource with hidden password if present
    """
    password = urlparse(resource).password
    return resource.replace(password, "<hidden>") if password else resource


def _handle_remotes(registry_path, remote_file, output):
    registry = RemoteRegistry(registry_path, output)
    new_registry = RemoteRegistry(remote_file, output)
    registry.define_remotes(new_registry.remotes)


def _handle_profiles(source_folder, target_folder, output):
    mkdir(target_folder)
    for root, _, files in walk(source_folder):
        relative_path = os.path.relpath(root, source_folder)
        if relative_path == ".":
            relative_path = ""
        for f in files:
            profile = os.path.join(relative_path, f)
            output.info("    Installing profile %s" % profile)
            shutil.copy(os.path.join(root, f), os.path.join(target_folder, profile))


def _process_git_repo(repo_url, client_cache, output, tmp_folder, verify_ssl, args=None):
    output.info("Trying to clone repo  %s" % repo_url)

    with tools.chdir(tmp_folder):
        try:
            args = args or ""
            subprocess.check_output('git -c http.sslVerify=%s %s clone "%s" config' % (verify_ssl, args, repo_url),
                                    shell=True)
            output.info("Repo cloned")
        except Exception as e:
            raise ConanException("config install error. Can't clone repo: %s" % str(e))

    tmp_folder = os.path.join(tmp_folder, "config")
    _process_folder(tmp_folder, client_cache, output)


def _process_zip_file(zippath, client_cache, output, tmp_folder, remove=False):
    unzip(zippath, tmp_folder)
    if remove:
        os.unlink(zippath)
    _process_folder(tmp_folder, client_cache, output)


def _handle_conan_conf(current_conan_conf, new_conan_conf_path):
    current_conan_conf.read(new_conan_conf_path)
    with open(current_conan_conf.filename, "w") as f:
        current_conan_conf.write(f)


def _process_folder(folder, client_cache, output):
    for root, dirs, files in walk(folder):
        for f in files:
            if f == "settings.yml":
                output.info("Installing settings.yml")
                settings_path = client_cache.settings_path
                shutil.copy(os.path.join(root, f), settings_path)
            elif f == "conan.conf":
                output.info("Processing conan.conf")
                conan_conf = client_cache.conan_config
                _handle_conan_conf(conan_conf, os.path.join(root, f))
            elif f == "remotes.txt":
                output.info("Defining remotes")
                registry_path = client_cache.registry
                _handle_remotes(registry_path, os.path.join(root, f), output)
            else:
                relpath = os.path.relpath(root, folder)
                target_folder = os.path.join(client_cache.conan_folder, relpath)
                mkdir(target_folder)
                output.info("Copying file %s to %s" % (f, target_folder))
                shutil.copy(os.path.join(root, f), target_folder)
        for d in dirs:
            if d == "profiles":
                output.info("Installing profiles")
                profiles_path = client_cache.profiles_path
                _handle_profiles(os.path.join(root, d), profiles_path, output)
                break
        dirs[:] = [d for d in dirs if d not in ("profiles", ".git")]


def _process_download(item, client_cache, output, tmp_folder, verify_ssl):
    output.info("Trying to download  %s" % _hide_password(item))
    zippath = os.path.join(tmp_folder, "config.zip")
    try:
        tools.download(item, zippath, out=output, verify=verify_ssl)
        _process_zip_file(zippath, client_cache, output, tmp_folder, remove=True)
    except Exception as e:
        raise ConanException("Error while installing config from %s\n%s" % (item, str(e)))


def configuration_install(item, client_cache, output, verify_ssl, config_type=None, args=None):
    tmp_folder = os.path.join(client_cache.conan_folder, "tmp_config_install")
    # necessary for Mac OSX, where the temp folders in /var/ are symlinks to /private/var/
    tmp_folder = os.path.realpath(tmp_folder)
    mkdir(tmp_folder)
    try:
        if item is None:
            try:
                item = client_cache.conan_config.get_item("general.config_install")
            except ConanException:
                raise ConanException("Called config install without arguments and "
                                     "'general.config_install' not defined in conan.conf")

        if item.endswith(".git") or config_type == "git":
            _process_git_repo(item, client_cache, output, tmp_folder, verify_ssl, args)
        elif os.path.isdir(item):
            _process_folder(item, client_cache, output)
        elif os.path.isfile(item):
            _process_zip_file(item, client_cache, output, tmp_folder)
        elif item.startswith("http"):
            _process_download(item, client_cache, output, tmp_folder, verify_ssl)
        else:
            raise ConanException("I don't know how to process %s" % item)
    finally:
        if item:
            client_cache.conan_config.set_item("general.config_install", item)
        rmdir(tmp_folder)

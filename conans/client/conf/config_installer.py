import os
import shutil

from six.moves.urllib.parse import urlparse

from conans import load
from conans.client import tools
from conans.client.remote_registry import load_registry_txt
from conans.client.tools import Git
from conans.client.tools.files import unzip
from conans.errors import ConanException
from conans.util.files import mkdir, rmdir, walk


def _hide_password(resource):
    """
    Hide password from url/file path

    :param resource: string with url or file path
    :return: resource with hidden password if present
    """
    password = urlparse(resource).password
    return resource.replace(password, "<hidden>") if password else resource


def _handle_remotes(client_cache, remote_file):
    # FIXME: Should we encourage to pass the remotes in json?
    remotes, _ = load_registry_txt(load(remote_file))
    registry = client_cache.registry
    registry.remotes.define(remotes)


def _handle_profiles(source_folder, target_folder, output):
    mkdir(target_folder)
    for root, _, files in walk(source_folder):
        relative_path = os.path.relpath(root, source_folder)
        if relative_path == ".":
            relative_path = ""
        for f in files:
            profile = os.path.join(relative_path, f)
            output.info("  - %s" % profile)
            shutil.copy(os.path.join(root, f), os.path.join(target_folder, profile))


def _process_git_repo(repo_url, client_cache, output, tmp_folder, verify_ssl, args=None):
    output.info("Trying to clone repo: %s" % repo_url)

    with tools.chdir(tmp_folder):
        try:
            args = args or ""
            git = Git(verify_ssl=verify_ssl, output=output)
            git.clone(repo_url, args=args)
            output.info("Repo cloned!")
        except Exception as e:
            raise ConanException("Can't clone repo: %s" % str(e))
    _process_folder(tmp_folder, client_cache, output)


def _process_zip_file(zippath, client_cache, output, tmp_folder, remove=False):
    unzip(zippath, tmp_folder, output=output)
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
                output.info("Defining remotes from remotes.txt")
                _handle_remotes(client_cache, os.path.join(root, f))
            else:
                relpath = os.path.relpath(root, folder)
                target_folder = os.path.join(client_cache.conan_folder, relpath)
                mkdir(target_folder)
                output.info("Copying file %s to %s" % (f, target_folder))
                shutil.copy(os.path.join(root, f), target_folder)
        for d in dirs:
            if d == "profiles":
                output.info("Installing profiles:")
                profiles_path = client_cache.profiles_path
                _handle_profiles(os.path.join(root, d), profiles_path, output)
            elif d == "hooks" and ".git" not in root:  # Avoid git hooks
                output.info("Installing hooks:")
                src_hooks_path = os.path.join(root, d)
                dst_hooks_path = client_cache.hooks_path
                _handle_hooks(src_hooks_path, dst_hooks_path, output)
        dirs[:] = [d for d in dirs if d not in ("profiles", ".git", "hooks")]


def _process_download(item, client_cache, output, tmp_folder, verify_ssl, requester):
    output.info("Trying to download  %s" % _hide_password(item))
    zippath = os.path.join(tmp_folder, "config.zip")
    try:
        tools.download(item, zippath, out=output, verify=verify_ssl, requester=requester)
        _process_zip_file(zippath, client_cache, output, tmp_folder, remove=True)
    except Exception as e:
        raise ConanException("Error while installing config from %s\n%s" % (item, str(e)))


def configuration_install(path_or_url, client_cache, output, verify_ssl, requester,
                          config_type=None, args=None):
    if path_or_url is None:
        try:
            item = client_cache.conan_config.get_item("general.config_install")
            _config_type, path_or_url, _verify_ssl, _args = _process_config_install_item(item)
        except ConanException:
            raise ConanException("Called config install without arguments and "
                                 "'general.config_install' not defined in conan.conf")
    else:
        _config_type, path_or_url, _verify_ssl, _args = _process_config_install_item(path_or_url)

    config_type = config_type or _config_type
    verify_ssl = verify_ssl or _verify_ssl
    args = args or _args

    if os.path.exists(path_or_url):
        path_or_url = os.path.abspath(path_or_url)

    tmp_folder = os.path.join(client_cache.conan_folder, "tmp_config_install")
    # necessary for Mac OSX, where the temp folders in /var/ are symlinks to /private/var/
    tmp_folder = os.path.realpath(tmp_folder)
    mkdir(tmp_folder)
    try:

        if config_type == "git":
            _process_git_repo(path_or_url, client_cache, output, tmp_folder, verify_ssl, args)
        elif config_type == "dir":
            args = None
            _process_folder(path_or_url, client_cache, output)
        elif config_type == "file":
            args = None
            _process_zip_file(path_or_url, client_cache, output, tmp_folder)
        elif config_type == "url":
            args = None
            _process_download(path_or_url, client_cache, output, tmp_folder, verify_ssl,
                              requester=requester)
        else:
            raise ConanException("Unable to process config install: %s" % path_or_url)
    finally:
        if config_type is not None and path_or_url is not None:
            value = "%s, %s, %s, %s" % (config_type, path_or_url, verify_ssl, args)
            client_cache.conan_config.set_item("general.config_install", value)
        rmdir(tmp_folder)


def _process_config_install_item(item):
    """
    Processes a config_install item and outputs a tuple with the configuration type, the path/url
    and additional args

    :param item: config_install item value from conan.conf with a simple path/url or a string
    following this pattern: "<config_type>:[<path_or_url>, <args>]"
    :return: configuration source type (git, url, dir or file), path to file/dir or git/http url and
    additional arguments
    """
    config_type, path_or_url, verify_ssl, args = None, None, None, None
    if not item.startswith(("git,", "dir,", "url,", "file,")):
        path_or_url = item
        if path_or_url.endswith(".git"):
            config_type = "git"
        elif os.path.isdir(path_or_url):
            config_type = "dir"
        elif os.path.isfile(path_or_url):
            config_type = "file"
        elif path_or_url.startswith("http"):
            config_type = "url"
        else:
            raise ConanException("Unable to process config install: %s" % path_or_url)
    else:
        config_type, path_or_url, verify_ssl, args = [r.strip() for r in item.split(",")]
        verify_ssl = "true" in verify_ssl.lower()
        args = None if "none" in args.lower() else args
    return config_type, path_or_url, verify_ssl, args


def _handle_hooks(src_hooks_path, dst_hooks_path, output):
    """
    Copies files to the hooks folder overwriting the files that are in the same path
    (shutil.copytree fails on doing this), skips git related files (.git, .gitmodule...) and outputs
    the copied files

    :param src_hooks_path: Folder where the hooks come from
    :param dst_hooks_path:  Folder where the hooks should finally go
    :param output: Output to indicate the files copied
    """
    hooks_dirs = []
    for root, dirs, files in walk(src_hooks_path):
        if root == src_hooks_path:
            hooks_dirs = dirs
        else:
            copied_files = False
            relpath = os.path.relpath(root, src_hooks_path)
            for f in files:
                if ".git" not in f:
                    dst = os.path.join(dst_hooks_path, relpath)
                    mkdir(dst)
                    shutil.copy(os.path.join(root, f), dst)
                    copied_files = True
            if copied_files and relpath in hooks_dirs:
                output.info(" - %s" % relpath)

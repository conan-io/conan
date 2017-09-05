import os
import tempfile
from conans.tools import unzip
import shutil
from conans.util.files import rmdir, load
from conans.client.remote_registry import RemoteRegistry, Remote
from conans import tools


def _handle_remotes(registry_path, remote_file, output):
    registry = RemoteRegistry(registry_path, output)

    # Parse the remotes info
    new_remotes = []
    lines = [line.strip() for line in load(remote_file).splitlines() if line.strip()]
    for line in lines:
        name, url, ssl = line.split()
        output.info("    Defining remote %s" % name)
        new_remotes.append(Remote(name, url, ssl))

    registry.define_remotes(new_remotes)


def _handle_profiles(source_folder, target_folder, output):
    for root, _, files in os.walk(source_folder):
        relative_path = os.path.relpath(root, source_folder)
        if relative_path == ".":
            relative_path = ""
        for f in files:
            profile = os.path.join(relative_path, f)
            output.info("    Installing profile %s" % profile)
            shutil.copy(os.path.join(root, f), os.path.join(target_folder, profile))


def _process_zip_file(zippath, client_cache, output):
    t = tempfile.mkdtemp()
    # necessary for Mac OSX, where the temp folders in /var/ are symlinks to /private/var/
    t = os.path.realpath(t)
    unzip(zippath, t)
    for root, dirs, files in os.walk(t):
        for f in files:
            if f == "settings.yml":
                output.info("Installing settings.yml")
                settings_path = client_cache.settings_path
                shutil.copy(os.path.join(root, f), settings_path)
            elif f == "remotes.txt":
                output.info("Defining remotes")
                registry_path = client_cache.registry
                _handle_remotes(registry_path, os.path.join(root, f), output)
        for d in dirs:
            if d == "profiles":
                output.info("Installing profiles")
                profiles_path = client_cache.profiles_path
                _handle_profiles(os.path.join(root, d), profiles_path, output)
                dirs.remove("profiles")

    rmdir(t)


def _process_download(item, client_cache, output):
    output.info("Trying to download  %s" % item)
    t = tempfile.mkdtemp()
    zippath = os.path.join(t, "config.zip")
    tools.download(item, zippath, out=output)
    _process_zip_file(zippath, client_cache, output)
    rmdir(t)


def configuration_install(item, client_cache, output):
    if os.path.exists(item):
        # is a local file
        _process_zip_file(item, client_cache, output)
        return

    if item.startswith("http"):
        _process_download(item, client_cache, output)

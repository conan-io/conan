import copy
import json
import os
import time
from os.path import isdir

import fasteners

from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import md5sum, sha1sum
from conans.util.log import logger


# FIXME: Conan 2.0 the traces should have all the revisions information also.

TRACER_ACTIONS = ["UPLOADED_RECIPE", "UPLOADED_PACKAGE",
                  "DOWNLOADED_RECIPE", "DOWNLOADED_RECIPE_SOURCES", "DOWNLOADED_PACKAGE",
                  "PACKAGE_BUILT_FROM_SOURCES",
                  "GOT_RECIPE_FROM_LOCAL_CACHE", "GOT_PACKAGE_FROM_LOCAL_CACHE",
                  "REST_API_CALL", "COMMAND",
                  "EXCEPTION",
                  "DOWNLOAD",
                  "UNZIP", "ZIP"]

MASKED_FIELD = "**********"


def _validate_action(action_name):
    if action_name not in TRACER_ACTIONS:
        raise ConanException("Unknown action %s" % action_name)


def _get_tracer_file():
    """
    If CONAN_TRACE_FILE is a file in an existing dir will log to it creating the file if needed
    Otherwise won't log anything
    """
    trace_path = os.environ.get("CONAN_TRACE_FILE", None)
    if trace_path is not None:
        if not os.path.isabs(trace_path):
            raise ConanException("Bad CONAN_TRACE_FILE value. The specified "
                                 "path has to be an absolute path to a file.")
        if not os.path.exists(os.path.dirname(trace_path)):
            raise ConanException("Bad CONAN_TRACE_FILE value. The specified "
                                 "path doesn't exist: '%s'" % os.path.dirname(trace_path))
        if isdir(trace_path):
            raise ConanException("CONAN_TRACE_FILE is a directory. Please, specify a file path")
    return trace_path


def _append_to_log(obj):
    """Add a new line to the log file locking the file to protect concurrent access"""
    if _get_tracer_file():
        filepath = _get_tracer_file()
        with fasteners.InterProcessLock(filepath + ".lock", logger=logger):
            with open(filepath, "a") as logfile:
                logfile.write(json.dumps(obj, sort_keys=True) + "\n")


def _append_action(action_name, props):
    """Validate the action_name and append to logs"""
    _validate_action(action_name)
    props["_action"] = action_name
    props["time"] = time.time()
    _append_to_log(props)


# ############## LOG METHODS ######################

def _file_document(name, path):
    return {"name": name, "path": path, "md5": md5sum(path), "sha1": sha1sum(path)}


def log_recipe_upload(ref, duration, files_uploaded, remote_name):
    files_uploaded = files_uploaded or {}
    files_uploaded = [_file_document(name, path) for name, path in files_uploaded.items()]
    _append_action("UPLOADED_RECIPE", {"_id": repr(ref.copy_clear_rev()),
                                       "duration": duration,
                                       "files": files_uploaded,
                                       "remote": remote_name})


def log_package_upload(pref, duration, files_uploaded, remote):
    """files_uploaded is a dict with relative path as keys and abs path as values"""
    files_uploaded = files_uploaded or {}
    files_uploaded = [_file_document(name, path) for name, path in files_uploaded.items()]
    _append_action("UPLOADED_PACKAGE", {"_id": repr(pref.copy_clear_revs()),
                                        "duration": duration,
                                        "files": files_uploaded,
                                        "remote": remote.name})


def log_recipe_download(ref, duration, remote_name, files_downloaded):
    assert(isinstance(ref, ConanFileReference))
    files_downloaded = files_downloaded or {}
    files_downloaded = [_file_document(name, path) for name, path in files_downloaded.items()]
    _append_action("DOWNLOADED_RECIPE", {"_id": repr(ref.copy_clear_rev()),
                                         "duration": duration,
                                         "remote": remote_name,
                                         "files": files_downloaded})


def log_recipe_sources_download(ref, duration, remote_name, files_downloaded):
    assert(isinstance(ref, ConanFileReference))
    files_downloaded = files_downloaded or {}
    files_downloaded = [_file_document(name, path) for name, path in files_downloaded.items()]
    _append_action("DOWNLOADED_RECIPE_SOURCES", {"_id": repr(ref.copy_clear_rev()),
                                                 "duration": duration,
                                                 "remote": remote_name,
                                                 "files": files_downloaded})


def log_package_download(pref, duration, remote, files_downloaded):
    files_downloaded = files_downloaded or {}
    files_downloaded = [_file_document(name, path) for name, path in files_downloaded.items()]
    _append_action("DOWNLOADED_PACKAGE", {"_id": repr(pref.copy_clear_revs()),
                                          "duration": duration,
                                          "remote": remote.name,
                                          "files": files_downloaded})


def log_recipe_got_from_local_cache(ref):
    assert(isinstance(ref, ConanFileReference))
    _append_action("GOT_RECIPE_FROM_LOCAL_CACHE", {"_id": repr(ref.copy_clear_rev())})


def log_package_got_from_local_cache(pref):
    assert(isinstance(pref, PackageReference))
    _append_action("GOT_PACKAGE_FROM_LOCAL_CACHE", {"_id": repr(pref.copy_clear_revs())})


def log_package_built(pref, duration, log_run=None):
    assert(isinstance(pref, PackageReference))
    _append_action("PACKAGE_BUILT_FROM_SOURCES",
                   {"_id": repr(pref.copy_clear_revs()), "duration": duration, "log": log_run})


def log_client_rest_api_call(url, method, duration, headers):
    headers = copy.copy(headers)
    if "Authorization" in headers:
        headers["Authorization"] = MASKED_FIELD
    if "X-Client-Anonymous-Id" in headers:
        headers["X-Client-Anonymous-Id"] = MASKED_FIELD
    if "signature=" in url:
        url = url.split("signature=")[0] + "signature=%s" % MASKED_FIELD
    _append_action("REST_API_CALL", {"method": method, "url": url,
                                     "duration": duration, "headers": headers})


def log_command(name, parameters):
    if name == "authenticate" and "password" in parameters:
        parameters = copy.copy(parameters)  # Ensure we don't alter any app object like args
        parameters["password"] = MASKED_FIELD
    _append_action("COMMAND", {"name": name, "parameters": parameters})
    logger.debug("CONAN_API: %s(%s)" % (name, ",".join("%s=%s" % (k, v)
                                                       for k, v in parameters.items())))


def log_exception(exc, message):
    _append_action("EXCEPTION", {"class": str(exc.__class__.__name__), "message": message})


def log_download(url, duration):
    _append_action("DOWNLOAD", {"url": url, "duration": duration})


def log_uncompressed_file(src_path, duration, dest_folder):
    _append_action("UNZIP", {"src": src_path, "dst": dest_folder, "duration": duration})


def log_compressed_files(files, duration, tgz_path):
    files = files or {}
    files_compressed = [_file_document(name, path) for name, path in files.items()]
    _append_action("ZIP", {"src": files_compressed, "dst": tgz_path, "duration": duration})

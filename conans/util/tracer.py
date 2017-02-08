import os
from conans.errors import ConanException
import fasteners
from conans.util.log import logger
import json
from conans.model.ref import PackageReference, ConanFileReference
import time
from os.path import isdir
import copy

TRACER_ACTIONS = ["UPLOADED_RECIPE", "UPLOADED_PACKAGE",
                  "DOWNLOADED_RECIPE", "DOWNLOADED_RECIPE_SOURCES", "DOWNLOADED_PACKAGE",
                  "PACKAGE_BUILT_FROM_SOURCES",
                  "GOT_RECIPE_FROM_LOCAL_CACHE", "GOT_PACKAGE_FROM_LOCAL_CACHE",
                  "REST_API_CALL", "COMMAND",
                  "EXCEPTION",
                  "DOWNLOAD"]

MASKED_FIELD = "**********"


def _validate_action(action_name):
    if action_name not in TRACER_ACTIONS:
        raise ConanException("Unknown action %s" % action_name)

tracer_file = None


def _get_tracer_file():
    '''
    If CONAN_TRACE_FILE is a file in an existing dir will log to it creating the file if needed
    Otherwise won't log anything
    '''
    global tracer_file
    if tracer_file is None:
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
            tracer_file = trace_path
    return tracer_file


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

def log_recipe_upload(conan_reference, duration, files_uploaded):
    assert(isinstance(conan_reference, ConanFileReference))
    _append_action("UPLOADED_RECIPE", {"_id": str(conan_reference),
                                       "duration": duration,
                                       "files": files_uploaded})


def log_package_upload(package_ref, duration, files_uploaded):
    '''files_uploaded is a dict with relative path as keys and abs path as values'''
    assert(isinstance(package_ref, PackageReference))
    _append_action("UPLOADED_PACKAGE", {"_id": str(package_ref),
                                        "duration": duration,
                                        "files": files_uploaded})


def log_recipe_download(conan_reference, duration, remote, files_downloaded):
    assert(isinstance(conan_reference, ConanFileReference))
    _append_action("DOWNLOADED_RECIPE", {"_id": str(conan_reference),
                                         "duration": duration,
                                         "remote": remote.name,
                                         "files": files_downloaded})


def log_recipe_sources_download(conan_reference, duration, remote, files_downloaded):
    assert(isinstance(conan_reference, ConanFileReference))
    _append_action("DOWNLOADED_RECIPE_SOURCES", {"_id": str(conan_reference),
                                                 "duration": duration,
                                                 "remote": remote.name,
                                                 "files": files_downloaded})


def log_package_download(package_ref, duration, remote, files_downloaded):
    assert(isinstance(package_ref, PackageReference))
    _append_action("DOWNLOADED_PACKAGE", {"_id": str(package_ref),
                                          "duration": duration,
                                          "remote": remote.name,
                                          "files": files_downloaded})


def log_recipe_got_from_local_cache(conan_reference):
    assert(isinstance(conan_reference, ConanFileReference))
    _append_action("GOT_RECIPE_FROM_LOCAL_CACHE", {"_id": str(conan_reference)})


def log_package_got_from_local_cache(package_ref):
    assert(isinstance(package_ref, PackageReference))
    _append_action("GOT_PACKAGE_FROM_LOCAL_CACHE", {"_id": str(package_ref)})


def log_package_built(package_ref, duration, log_run=None):
    assert(isinstance(package_ref, PackageReference))
    _append_action("PACKAGE_BUILT_FROM_SOURCES", {"_id": str(package_ref), "duration": duration, "log": log_run})


def log_client_rest_api_call(url, method, duration, headers):
    headers = copy.copy(headers)
    headers["Authorization"] = MASKED_FIELD
    headers["X-Client-Anonymous-Id"] = MASKED_FIELD
    _append_action("REST_API_CALL", {"method": method, "url": url,
                                     "duration": duration, "headers": headers})


def log_command(name, parameters):
    if name == "user" and "password" in parameters:
        parameters = copy.copy(parameters)  # Ensure we don't alter any app object like args
        parameters["password"] = MASKED_FIELD
    _append_action("COMMAND", {"name": name, "parameters": parameters})


def log_exception(exc, message):
    _append_action("EXCEPTION", {"class": str(exc.__class__.__name__), "message": message})


def log_download(url, duration):
    _append_action("DOWNLOAD", {"url": url, "duration": duration})

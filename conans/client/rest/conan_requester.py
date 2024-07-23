import fnmatch
import json
import logging
import os
import platform

import requests
import urllib3
from jinja2 import Template
from requests.adapters import HTTPAdapter

from conans import __version__ as client_version
from conans.errors import ConanException

# Capture SSL warnings as pointed out here:
# https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning
# TODO: Fix this security warning
from conans.util.files import load

logging.captureWarnings(True)


DEFAULT_TIMEOUT = (30, 60)  # connect, read timeouts
INFINITE_TIMEOUT = -1


class _SourceURLCredentials:
    """
    Only for sources download (get(), download(), conan config install
    """
    def __init__(self, cache_folder):
        self._urls = {}
        if not cache_folder:
            return
        creds_path = os.path.join(cache_folder, "source_credentials.json")
        if not os.path.exists(creds_path):
            return

        def _get_auth(credentials):
            result = {}
            has_auth = False
            if "token" in credentials:
                result["token"] = credentials["token"]
                has_auth = True
            if "user" in credentials and "password" in credentials:
                result["user"] = credentials["user"]
                result["password"] = credentials["password"]
                has_auth = True
            if has_auth:
                return result
            else:
                raise ConanException(f"Unknown credentials method for '{credentials['url']}'")

        try:
            template = Template(load(creds_path))
            content = template.render({"platform": platform, "os": os})
            content = json.loads(content)
            self._urls = {credentials["url"]: _get_auth(credentials)
                          for credentials in content["credentials"]}
        except Exception as e:
            raise ConanException(f"Error loading 'source_credentials.json' {creds_path}: {repr(e)}")

    def add_auth(self, url, kwargs):
        for u, creds in self._urls.items():
            if url.startswith(u):
                token = creds.get("token")
                if token:
                    kwargs["headers"]["Authorization"] = f"Bearer {token}"
                user = creds.get("user")
                password = creds.get("password")
                if user and password:
                    kwargs["auth"] = (user, password)
                break


class ConanRequester:

    def __init__(self, config, cache_folder=None):
        # TODO: Make all this lazy, to avoid fully configuring Requester, for every api call
        #  even if it doesn't use it
        # FIXME: Trick for testing when requests is mocked
        if hasattr(requests, "Session"):
            self._http_requester = requests.Session()
            adapter = HTTPAdapter(max_retries=self._get_retries(config))
            self._http_requester.mount("http://", adapter)
            self._http_requester.mount("https://", adapter)
        else:
            self._http_requester = requests

        self._url_creds = _SourceURLCredentials(cache_folder)
        self._timeout = config.get("core.net.http:timeout", default=DEFAULT_TIMEOUT)
        self._no_proxy_match = config.get("core.net.http:no_proxy_match", check_type=list)
        self._proxies = config.get("core.net.http:proxies")
        self._cacert_path = config.get("core.net.http:cacert_path", check_type=str)
        self._client_certificates = config.get("core.net.http:client_cert")
        self._clean_system_proxy = config.get("core.net.http:clean_system_proxy", default=False,
                                              check_type=bool)
        platform_info = "; ".join([" ".join([platform.system(), platform.release()]),
                                   "Python " + platform.python_version(),
                                   platform.machine()])
        self._user_agent = "Conan/%s (%s)" % (client_version, platform_info)

    @staticmethod
    def _get_retries(config):
        retry = config.get("core.net.http:max_retries", default=2, check_type=int)
        if retry == 0:
            return 0
        retry_status_code_set = {
            requests.codes.internal_server_error,
            requests.codes.bad_gateway,
            requests.codes.service_unavailable,
            requests.codes.gateway_timeout,
            requests.codes.variant_also_negotiates,
            requests.codes.insufficient_storage,
            requests.codes.bandwidth_limit_exceeded
        }
        return urllib3.Retry(
            total=retry,
            backoff_factor=0.05,
            status_forcelist=retry_status_code_set
        )

    def _should_skip_proxy(self, url):
        if self._no_proxy_match:
            for entry in self._no_proxy_match:
                if fnmatch.fnmatch(url, entry):
                    return True
        return False

    def _add_kwargs(self, url, kwargs):
        # verify is the kwargs that comes from caller, RestAPI, it is defined in
        # Conan remote "verify_ssl"
        source_credentials = kwargs.pop("source_credentials", None)
        if kwargs.get("verify", None) is not False:  # False means de-activate
            if self._cacert_path is not None:
                kwargs["verify"] = self._cacert_path
        kwargs["cert"] = self._client_certificates
        if self._proxies:
            if not self._should_skip_proxy(url):
                kwargs["proxies"] = self._proxies
        if self._timeout and self._timeout != INFINITE_TIMEOUT:
            kwargs["timeout"] = self._timeout
        if not kwargs.get("headers"):
            kwargs["headers"] = {}

        if source_credentials:
            self._url_creds.add_auth(url, kwargs)

        # Only set User-Agent if none was provided
        if not kwargs["headers"].get("User-Agent"):
            kwargs["headers"]["User-Agent"] = self._user_agent

        return kwargs

    def get(self, url, **kwargs):
        return self._call_method("get", url, **kwargs)

    def head(self, url, **kwargs):
        return self._call_method("head", url, **kwargs)

    def put(self, url, **kwargs):
        return self._call_method("put", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._call_method("delete", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call_method("post", url, **kwargs)

    def _call_method(self, method, url, **kwargs):
        popped = False
        if self._clean_system_proxy:
            old_env = dict(os.environ)
            # Clean the proxies from the environ and use the conan specified proxies
            for var_name in ("http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy"):
                popped = True if os.environ.pop(var_name, None) else popped
                popped = True if os.environ.pop(var_name.upper(), None) else popped
        try:
            all_kwargs = self._add_kwargs(url, kwargs)
            tmp = getattr(self._http_requester, method)(url, **all_kwargs)
            return tmp
        finally:
            if popped:
                os.environ.clear()
                os.environ.update(old_env)

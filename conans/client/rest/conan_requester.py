import fnmatch
import logging
import os
import platform
import time

import urllib3
import requests
from requests.adapters import HTTPAdapter

from conans import __version__ as client_version
from conans.errors import ConanException
from conans.util.tracer import log_client_rest_api_call

# Capture SSL warnings as pointed out here:
# https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning
# TODO: Fix this security warning
logging.captureWarnings(True)


DEFAULT_TIMEOUT = (30, 60)  # connect, read timeouts


class ConanRequester(object):

    def __init__(self, config):
        # TODO: Make all this lazy, to avoid fully configuring Requester, for every api call
        #  even if it doesn't use it
        # FIXME: Trick for testing when requests is mocked
        if hasattr(requests, "Session"):
            self._http_requester = requests.Session()
            adapter = HTTPAdapter(max_retries=self._get_retries(config["core.requests:max_retries"]))

            self._http_requester.mount("http://", adapter)
            self._http_requester.mount("https://", adapter)

        to = config["core.requests:timeout"]
        try:
            self._timeout_seconds = eval(to) if to is not None else DEFAULT_TIMEOUT
        except Exception as e:
            raise ConanException(f"Incorrect core.requests:timeout='{to}' value")
        self.proxies = config["core.network:proxies"] or {}  # FIXME: Broken as config dont do {}
        self._cacert_path = config["core.network:cacert_path"]
        self._client_cert_path = config["core.network:client_cert_path"]
        self._client_cert_key_path = config["core.network:client_cert_key_path"]

        self._no_proxy_match = [el.strip() for el in
                                self.proxies.pop("no_proxy_match", "").split(",") if el]

        if self._client_cert_path is None:
            self._client_certificates = None
        else:
            if self._client_cert_key_path is not None:
                # Requests can accept a tuple with cert and key, or just an string with a
                # file having both
                self._client_certificates = (self._client_cert_path,
                                             self._client_cert_key_path)
            else:
                self._client_certificates = self._client_cert_path

    def _get_retries(self, retry):
        retry = retry if retry is not None else 2
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
        for entry in self._no_proxy_match:
            if fnmatch.fnmatch(url, entry):
                return True

        return False

    def _add_kwargs(self, url, kwargs):
        if kwargs.get("verify", None) is True:
            kwargs["verify"] = self._cacert_path
        else:
            kwargs["verify"] = False
        kwargs["cert"] = self._client_certificates
        if self.proxies:
            if not self._should_skip_proxy(url):
                kwargs["proxies"] = self.proxies
        if self._timeout_seconds:
            kwargs["timeout"] = self._timeout_seconds
        if not kwargs.get("headers"):
            kwargs["headers"] = {}

        # Only set User-Agent if none was provided
        if not kwargs["headers"].get("User-Agent"):
            platform_info = "; ".join([
                " ".join([platform.system(), platform.release()]),
                "Python "+platform.python_version(),
                platform.machine()])
            user_agent = "Conan/%s (%s)" % (client_version, platform_info)
            kwargs["headers"]["User-Agent"] = user_agent

        return kwargs

    def get(self, url, **kwargs):
        return self._call_method("get", url, **kwargs)

    def put(self, url, **kwargs):
        return self._call_method("put", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._call_method("delete", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call_method("post", url, **kwargs)

    def _call_method(self, method, url, **kwargs):
        popped = False
        if self.proxies or self._no_proxy_match:
            old_env = dict(os.environ)
            # Clean the proxies from the environ and use the conan specified proxies
            for var_name in ("http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy"):
                popped = True if os.environ.pop(var_name, None) else popped
                popped = True if os.environ.pop(var_name.upper(), None) else popped
        try:
            t1 = time.time()
            all_kwargs = self._add_kwargs(url, kwargs)
            tmp = getattr(requests, method)(url, **all_kwargs)
            duration = time.time() - t1
            log_client_rest_api_call(url, method.upper(), duration, all_kwargs.get("headers"))
            return tmp
        finally:
            if popped:
                os.environ.clear()
                os.environ.update(old_env)

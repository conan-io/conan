import fnmatch
import os
import requests
import platform

import time

from conans.util.files import save
from conans import __version__ as client_version
from conans.util.tracer import log_client_rest_api_call


class ConanRequester(object):

    def __init__(self, requester, client_cache, timeout):
        self.proxies = client_cache.conan_config.proxies or {}
        self._no_proxy_match = [el.strip() for el in
                                self.proxies.pop("no_proxy_match", "").split(",") if el]
        self._timeout_seconds = timeout

        # Retrocompatibility with deprecated no_proxy
        # Account for the requests NO_PROXY env variable, not defined as a proxy like http=
        no_proxy = self.proxies.pop("no_proxy", None)
        if no_proxy:
            os.environ["NO_PROXY"] = no_proxy

        self._requester = requester
        self._client_cache = client_cache

        if not os.path.exists(self._client_cache.cacert_path):
            from conans.client.rest.cacert import cacert
            save(self._client_cache.cacert_path, cacert)

        if not os.path.exists(client_cache.client_cert_path):
            self._client_certificates = None
        else:
            if os.path.exists(client_cache.client_cert_key_path):
                # Requests can accept a tuple with cert and key, or just an string with a
                # file having both
                self._client_certificates = (client_cache.client_cert_path,
                                             client_cache.client_cert_key_path)
            else:
                self._client_certificates = client_cache.client_cert_path

    def _should_skip_proxy(self, url):

        for entry in self._no_proxy_match:
            if fnmatch.fnmatch(url, entry):
                return True

        return False

    def _add_kwargs(self, url, kwargs):
        if kwargs.get("verify", None) is True:
            kwargs["verify"] = self._client_cache.cacert_path
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
        kwargs["headers"]["User-Agent"] = "Conan/%s (Python %s) %s" % (client_version,
                                                                       platform.python_version(),
                                                                       requests.utils.default_user_agent())
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
            for var_name in ("http_proxy", "https_proxy", "no_proxy"):
                popped = popped or os.environ.pop(var_name, None)
                popped = popped or os.environ.pop(var_name.upper(), None)
        try:
            t1 = time.time()
            all_kwargs = self._add_kwargs(url, kwargs)
            tmp = getattr(self._requester, method)(url, **all_kwargs)
            duration = time.time() - t1
            log_client_rest_api_call(url, method.upper(), duration, all_kwargs.get("headers"))
            return tmp
        finally:
            if popped:
                os.environ.clear()
                os.environ.update(old_env)

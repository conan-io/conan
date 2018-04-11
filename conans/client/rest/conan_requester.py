import fnmatch
import os

from conans.util.files import save


class ConanRequester(object):

    def __init__(self, requester, client_cache, timeout):
        self.proxies = client_cache.conan_config.proxies or {}
        self._no_proxy_match = [el.strip() for el in
                                self.proxies.pop("no_proxy_match", "").split(",")]
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
        return kwargs

    def get(self, url, **kwargs):
        return self._requester.get(url, **self._add_kwargs(url, kwargs))

    def put(self, url, **kwargs):
        return self._requester.put(url, **self._add_kwargs(url, kwargs))

    def delete(self, url, **kwargs):
        return self._requester.delete(url, **self._add_kwargs(url, kwargs))

    def post(self, url, **kwargs):
        return self._requester.post(url, **self._add_kwargs(url, kwargs))


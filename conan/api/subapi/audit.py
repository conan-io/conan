import json
import os

from conan.internal.api.audit.providers import ConanProxyProvider, PrivateProvider
from conan.errors import ConanException
from conan.internal.model.recipe_ref import RecipeReference
from conans.util.files import save, load

CONAN_CENTER_CATALOG_NAME = "conan-center-catalog"


class AuditAPI:
    """
    This class provides the functionality to scan references for vulnerabilities.
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self._home_folder = conan_api.home_folder
        self._providers_path = os.path.join(self._home_folder, "audit_providers.json")
        self._provider_cls = {
            # TODO: Temp names, find better ones (specially, no mention of catalog)
            "conan-center-proxy": ConanProxyProvider,
            "private": PrivateProvider
        }

    def scan(self, deps_graph, provider):
        """
        Scan a given recipe for vulnerabilities in its dependencies.
        """
        refs = list(set(f"{node.ref.name}/{node.ref.version}" for node in deps_graph.nodes[1:]))
        return provider.get_cves(refs)

    def list(self, reference, provider):
        """
        List the vulnerabilities of the given reference.
        """
        ref = RecipeReference.loads(reference)
        ref.validate_ref()
        return provider.get_cves([reference])

    def get_provider(self, provider_name):
        """
        Get the provider by name.
        """
        # TODO: More work remains to be done here, hardcoded for now for testing
        providers = _load_providers(self._providers_path)
        if provider_name not in providers:
            raise ConanException(f"Provider '{provider_name}' not found")

        provider_data = providers[provider_name]
        provider_cls = self._provider_cls.get(provider_data["type"])

        return provider_cls(provider_name, provider_data)

    def list_providers(self):
        """
        Get all available providers.
        """
        providers = _load_providers(self._providers_path)
        result = []
        for name, provider_data in providers.items():
            provider_cls = self._provider_cls.get(provider_data["type"])
            result.append(provider_cls(name, provider_data))
        return result

    # TODO: See if token should be optional
    def add_provider(self, name, url, provider_type, token=None):
        """
        Add a provider.
        """
        providers = _load_providers(self._providers_path)
        if name in providers:
            raise ConanException(f"Provider '{name}' already exists")

        if provider_type not in self._provider_cls:
            raise ConanException(f"Provider type '{provider_type}' not found")

        # TODO: Validate data
        providers[name] = {
            "name": name,
            "url": url,
            "type": provider_type
        }
        if token:
            # TODO: Store the token in a different file/place
            providers[name]["token"] = token
        _save_providers(self._providers_path, providers)

    # TODO: Should this be a provider, or just its name?
    #   Do we want users to call get_provider beforehand or should we handle it here?
    def auth_provider(self, provider, token):
        """
        Authenticate a provider.
        """
        # TODO: Store the token in a different file/place
        if not provider:
            raise ConanException("Provider not found")

        providers = _load_providers(self._providers_path)

        assert provider.name in providers
        # TODO: Store this somewhere else
        providers[provider.name]["token"] = token
        _save_providers(self._providers_path, providers)


def _load_providers(providers_path):
    if not os.path.exists(providers_path):
        default_providers = {
            CONAN_CENTER_CATALOG_NAME: {
                "url": "https://conancenter-stg-api.jfrog.team/api/v1/query",
                "type": "conan-center-proxy"
            }
        }
        save(providers_path, json.dumps(default_providers, indent=4))
    return json.loads(load(providers_path))

def _save_providers(providers_path, providers):
    save(providers_path, json.dumps(providers, indent=4))

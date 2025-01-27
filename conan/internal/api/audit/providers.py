import textwrap

import requests

from conan.api.output import ConanOutput
from conan.errors import ConanException


# TODO: Think if providers are classes that implement get_cves,
#  or just a function and the discrimination is done in the AuditAPI
class ConanProxyProvider:
    def __init__(self, name, provider_data):
        self.name = name
        self.url = provider_data["url"]
        self.token = provider_data.get("token")
        self._session = requests.Session()

    def get_cves(self, refs):
        if not self.token:
            raise ConanException(textwrap.dedent(f"""
                You dont have a token for the service, go register here https://conancenter-stg-api.jfrog.team/, and once you have, run:

                conan audit auth-provider conan-center-catalog –-token=<mytoken>

                And rerun this command
            """))

        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}

        result = {"data": {}}

        for ref in refs:
            ConanOutput().info(f"Requesting vulnerability info for: {ref}")
            response = self._session.post(
                self.url,
                headers=headers,
                json={
                    "reference": str(ref),
                },
            )
            if response.status_code == 200:
                result["data"].update(response.json()["data"])
            elif response.status_code == 403:
                # TODO: How to report auth error to the user
                ConanOutput().error(f"Authentication error: {response.status_code}")
                break
            elif response.status_code == 429:

                msg = "Rate limit exceeded. Results may be incomplete."
                ConanOutput().warning(msg)
                break
            elif response.status_code == 500:
                # TODO: How to report internal server error to the user
                ConanOutput().error(f"Internal server error: {response.status_code}")
                break
            else:
                ConanOutput().error(f"Failed to get vulnerabilities for {ref}: {response.status_code}")
                ConanOutput().error(response.text)
                break
        return result

class PrivateProvider:
    def __init__(self, name, provider_data):
        self.name = name
        self.url = provider_data["url"]
        self.data = provider_data
        self._session = requests.Session()

    def get_cves(self, refs):
        result = {"data": {}}
        for ref in refs:
            response = self._get(ref)
            # TODO: Better error handling
            if "error" in response:
                result["error"] = response["error"]
                break
            result["data"].update(response["data"])
        return result

    @staticmethod
    def _build_query(ref):
        name, version = ref.name, ref.version
        full_query = f"""query packageVersionDetails {{
            {name}: packageVersion(name: "{name}", type: "conan", version: "{version}") {{
                version
                vulnerabilities(first: 100) {{
                    totalCount
                    edges {{
                        node {{
                            name
                            description
                            severity
                            cvss {{
                                preferredBaseScore
                            }}
                            aliases
                            advisories {{
                                name
                                ...on JfrogAdvisory {{
                                          name
                                          shortDescription
                                          fullDescription
                                          url
                                          severity
                                     }}
                                }}
                            references
                        }}
                    }}
                }}
            }}
        }}"""
        return full_query

    @staticmethod
    def _parse_error(errors, ref):
        """This function removes the errors array that comes from the catalog and returns a more user-friendly message
        if we know how to parse it, or a generic one if we don't find such one"""

        def _replace_message(message):
            if "not found" in message:
                return f"{ref} was not found in the catalog"
            return None

        error_msgs = filter(bool, [_replace_message(error["message"]) for error in errors])
        return {"details": next(error_msgs, "Unknown error")}

    def _get(self, ref):
        full_query = self._build_query(ref)
        try:
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
            if self.data.get("token"):
                headers["Authorization"] = f"Bearer {self.data['token']}"
            elif self.data.get("user") and self.data.get("password"):
                headers["Authorization"] = f"Basic {self.data['user']}:{self.data['password']}"

            response = self._session.post(
                self.url,
                headers=headers,
                json={
                    "query": textwrap.dedent(full_query)
                }
            )
            # Raises if some HTTP error was found
            response.raise_for_status()
        except:
            return {"error": {"details": "Something went wrong"}}

        response_json = response.json()
        # filter the extensions key with graphql data
        response_json.pop('extensions', None)

        if "errors" in response_json:
            return {"error": self._parse_error(response_json["errors"], ref)}
        return response_json

class OSVProvider:
    def __init__(self, name, provider_data):
        self.name = name
        self.url = provider_data["url"]
        self.data = provider_data
        self._session = requests.Session()

    def get_cves(self, refs):
        result = {"data": {}}
        for ref in refs:
            response = self._get(ref)
            if "error" in response or "vulns" not in response:
                result["error"] = response.get("error", {"details": "Something went wrong"})
                break
            for vuln in response["vulns"]:
                ref_vulns = result["data"].setdefault(str(ref.name), {})
                edges = ref_vulns.setdefault('vulnerabilities', {}).setdefault('edges', [])
                ref_vulns['version'] = str(ref.version)
                edges.append({"node": {
                    "name": vuln["id"],
                    "description": vuln.get("summary") or vuln.get("details"),
                    "references": [
                        [reference["url"]] for reference in vuln["references"]
                    ]
                }})
        return result

    def _get(self, ref):
        try:
            data = {
                "version": str(ref.version),
                "package": {
                    "name": ref.name,
                }
            }
            response = self._session.post(self.url, json=data)
            response.raise_for_status()
        except Exception as e:
            return {"error": {"details": "Something went wrong"}}

        response_json = response.json()
        if "error" in response_json:
            return {"error": response_json["error"]}

        return response_json

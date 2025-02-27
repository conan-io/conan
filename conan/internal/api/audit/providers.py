import textwrap

from conan.api.output import Color, ConanOutput
from conan.errors import ConanException


class ConanCenterProvider:
    def __init__(self, conan_api, name, provider_data):
        self.name = name
        self.url = provider_data["url"]
        self.type = provider_data["type"]
        self.token = provider_data.get("token")
        self._session = conan_api.remotes.requester

    def get_cves(self, refs):
        if not self.token:
            from conan.api.subapi.audit import CONAN_CENTER_AUDIT_PROVIDER_NAME
            if self.name == CONAN_CENTER_AUDIT_PROVIDER_NAME:
                output = ConanOutput()

                output.write("\n")
                output.write("Authentication required for the CVE provider: ", fg=Color.BRIGHT_RED, newline=False)
                output.write(f"'{self.name}'\n", fg=Color.BRIGHT_WHITE)

                output.write("\nTo resolve, please:\n")
                output.write("  1. Visit: ", fg=Color.BRIGHT_WHITE, newline=False)
                output.write("https://audit.conan.io/register\n", fg=Color.BRIGHT_BLUE)
                output.write("  2. Register to obtain the access token and activate it.\n", fg=Color.BRIGHT_WHITE)
                output.write("  3. Use the command below to authenticate:\n", fg=Color.BRIGHT_WHITE)

                output.write(f"\n     conan audit provider auth --name={self.name} --token=<your_token>", fg=Color.BRIGHT_GREEN, newline=True)

                output.write("\nOnce authenticated, re-run the command.\n\n")

            raise ConanException("Missing authentication token. Please authenticate and retry.")


        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "Authorization": f"Bearer {self.token}"}

        result = {"data": {}}
        errors_in_response = False
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
            elif response.status_code == 400:
                ConanOutput().error(f"Package '{ref}' not found.\n"
                                    f"Only libraries available in Conan Center can be queried for vulnerabilities.\n"
                                    f"Please ensure the package exists in the official repository: https://conan.io/center\n"
                                    f"If the package exists in the repository, please report it to conan@jfrog.com.\n")
                errors_in_response = True
                break

            elif response.status_code == 403:
                # TODO: How to report auth error to the user
                ConanOutput().error(f"Authentication error ({response.status_code}).\n"
                                    f"Your token may be invalid or not yet validated. If you recently registered, please check your email to validate your token.\n"
                                    f" - Set a valid token using: 'conan audit provider auth --name={self.name} --token=<your_token>'\n"
                                    f" - If you don’t have a token, register at: https://audit.conan.io/register")

                errors_in_response = True
                break
            elif response.status_code == 429:
                reset_seconds = int(response.headers.get("x-ratelimit-reset", 0))
                reset_in_hours = reset_seconds // 3600
                reset_in_minutes = (reset_seconds % 3600) // 60

                output = ConanOutput()
                output.write("\n")
                output.warning("Rate Limit Exceeded!\n")

                if reset_in_hours > 0:
                    output.write(
                        f"You have exceeded the number of allowed requests. "
                        f"The limit will reset in {reset_in_hours} "
                        f"hour{'s' if reset_in_hours > 1 else ''} and {reset_in_minutes} "
                        f"minute{'s' if reset_in_minutes > 1 else ''}.\n",
                        fg=Color.BRIGHT_WHITE,
                    )
                else:
                    output.write(
                        f"You have exceeded the number of allowed requests. "
                        f"The limit will reset in {reset_in_minutes} "
                        f"minute{'s'if reset_in_minutes > 1 else ''}.\n",
                        fg=Color.BRIGHT_WHITE,
                    )

                # FIXME: add some help here
                #output.write("For more information, visit: ", fg=Color.BRIGHT_WHITE, newline=False)
                #output.write("https://some-url-in-the-future", newline=True, fg=Color.BRIGHT_BLUE)
                output.write("\n")
                ConanOutput().error("Rate limit exceeded.\n")
                errors_in_response = True
                break
            elif response.status_code == 500:
                # TODO: How to report internal server error to the user
                ConanOutput().error(f"Internal server error ({response.status_code})")
                errors_in_response = True
                break
            else:
                ConanOutput().error(f"Error ({response.status_code}). {response.json()['details']}")
                errors_in_response = True
                break
        return result, errors_in_response

class PrivateProvider:
    def __init__(self, conan_api, name, provider_data):
        self.name = name
        self.url = provider_data["url"]
        self.type = provider_data["type"]
        self.data = provider_data
        self._session = conan_api.remotes.requester

    def get_cves(self, refs):
        result = {"data": {}}
        for ref in refs:
            response = self._get(ref)
            # TODO: Better error handling
            if "error" in response:
                result["error"] = response["error"]
                return result, True
            result["data"].update(response["data"])
        return result, False

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

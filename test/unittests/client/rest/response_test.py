from collections import namedtuple
from conan.internal import rest


class TestRestString:

    def _get_html_response(self):
        headers = {"content-type": "text/html;charset=utf-8",}
        return namedtuple("Response", "status_code headers reason content")(
            404,
            headers,
            "Not Found",
            b'\n<!doctype html>\n<!--[if IE 9]><html class="lt-ie10" lang="en" >\n</html>\n')

    def _get_json_response(self):
        headers = {"content-type": "application/json"}
        return namedtuple("Response", "status_code headers reason content")(
            404,
            headers,
            "Not Found",
            b'Could not find the artifact')

    def test_html_error(self):
        response = self._get_html_response()
        result = rest.response_to_str(response)
        assert "404: Not Found" == result

    def test_json_error(self):
        response = self._get_json_response()
        result = rest.response_to_str(response)
        assert "Could not find the artifact" == result

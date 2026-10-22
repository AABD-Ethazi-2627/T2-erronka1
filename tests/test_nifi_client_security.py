"""Security checks for the local NiFi API client's credential boundary."""

import os
import unittest
from io import BytesIO
from unittest.mock import patch

from scripts.nifi_client import private_token, request
from scripts.private_files import private_text_file


class NiFiClientSecurityTests(unittest.TestCase):
    def test_private_token(self):
        with (
            private_text_file("lab-token\n") as token_file,
            patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(token_file)}),
        ):
            self.assertEqual(private_token(), "lab-token")

    def test_token_requires_absolute_path(self):
        for configured in ("", "relative-token"):
            with (
                patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": configured}, clear=True),
                self.assertRaisesRegex(ValueError, "absolute"),
            ):
                private_token()

    def test_empty_multiline_and_oversized_tokens_are_rejected(self):
        for content in ("", " \n", "first\nsecond", "first\rsecond", "x" * 8193):
            with (
                private_text_file(content) as token_file,
                patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(token_file)}),
                self.assertRaisesRegex(ValueError, "malformed"),
            ):
                private_token()

    def test_request_requires_trusted_ca_before_network(self):
        with private_text_file("lab-token") as token_file:
            with (
                patch.dict(
                    os.environ, {"CNC_NIFI_TOKEN_FILE": str(token_file)}, clear=True
                ),
                patch("scripts.nifi_client.urllib.request.urlopen") as network,
                self.assertRaisesRegex(ValueError, "CNC_NIFI_CA_FILE"),
            ):
                request("GET", "/flow/about")
            network.assert_not_called()

    def test_request_uses_verified_context_and_local_endpoint(self):
        with private_text_file("lab-token") as token_file:
            response = BytesIO(b"ok")
            response.headers = {"Content-Type": "text/plain"}
            with (
                patch.dict(
                    os.environ,
                    {
                        "CNC_NIFI_TOKEN_FILE": str(token_file),
                        "CNC_NIFI_CA_FILE": "/trusted/ca.pem",
                    },
                    clear=True,
                ),
                patch("scripts.nifi_client.ssl.create_default_context") as context,
                patch(
                    "scripts.nifi_client.urllib.request.urlopen", return_value=response
                ) as network,
            ):
                self.assertEqual(request("GET", "/flow/about"), "ok")
            context.assert_called_once_with(cafile="/trusted/ca.pem")
            self.assertEqual(
                network.call_args.args[0].full_url,
                "https://localhost:18080/nifi-api/flow/about",
            )
            self.assertIs(network.call_args.kwargs["context"], context.return_value)


if __name__ == "__main__":
    unittest.main()

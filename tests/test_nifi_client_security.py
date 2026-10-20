"""Security checks for the local NiFi API client's credential boundary."""

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from scripts.nifi_client import private_token, request


class NiFiClientSecurityTests(unittest.TestCase):
    def test_private_token_and_rejects_unsafe_files(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "token"
            token_file.write_text("lab-token\n")
            token_file.chmod(0o600)
            with patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(token_file)}):
                self.assertEqual(private_token(), "lab-token")
                token_file.chmod(0o644)
                with self.assertRaises(ValueError):
                    private_token()
                token_file.chmod(0o600)
                link = Path(directory) / "link"
                link.symlink_to(token_file)
                with (
                    patch.dict(os.environ, {"CNC_NIFI_TOKEN_FILE": str(link)}),
                    self.assertRaises(OSError),
                ):
                    private_token()

    def test_request_requires_trusted_ca_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "token"
            token_file.write_text("lab-token")
            token_file.chmod(0o600)
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
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "token"
            token_file.write_text("lab-token")
            token_file.chmod(0o600)
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

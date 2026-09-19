"""Offline regression tests for the API boundary and its action callers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((ROOT / "action.yaml").read_text())
TOKEN = "test-token-not-a-secret"
ACCOUNT = "a" * 32
ZONE = "b" * 32
LIST = "c" * 32


class CloudflareTests(unittest.TestCase):
    def run_shell(self, script, body, status=200, curl_exit=0, extra_env=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            response = root / "response"
            response.write_text((body if isinstance(body, str) else json.dumps(body)) + f"\n{status}")
            env_file = root / "env"
            env_file.touch()
            env = {
                **os.environ,
                "CF_API_TOKEN": TOKEN,
                "CF_ACCOUNT_ID": ACCOUNT,
                "CF_ZONE_ID": ZONE,
                "ACTION_PATH": str(ROOT),
                "FIXTURE": str(response),
                "CURL_EXIT": str(curl_exit),
                "GITHUB_ENV": str(env_file),
                "GITHUB_OUTPUT": str(root / "output"),
                **(extra_env or {}),
            }
            prefix = '''
source "$ACTION_PATH/scripts/cloudflare.sh"
curl() { cat "$FIXTURE"; return "$CURL_EXIT"; }
'''
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", prefix + script],
                env=env, capture_output=True, text=True,
            )
            return result, env_file.read_text()

    def request(self, body, status=200, **kwargs):
        return self.run_shell(
            'cf_request GET "/accounts/$CF_ACCOUNT_ID/rules/lists" '
            "'.result | type == \"array\"'", body, status, **kwargs
        )[0]

    def test_api_failures_report_cause_not_jq_error(self):
        for status in (400, 401, 403, 429, 500, 200):
            with self.subTest(status=status):
                result = self.request({"success": False, "errors": [
                    {"code": 10000, "message": "Authentication error"}
                ], "result": None}, status)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn(f"HTTP {status}", result.stderr)
                self.assertIn("10000: Authentication error", result.stderr)
                self.assertIn("Account Filter Lists > Edit", result.stderr)
                self.assertNotIn("Cannot iterate", result.stderr)

    def test_invalid_envelopes_and_shapes(self):
        for body in ("<html>Gateway error</html>", "", "null", "[]", "{}\n{}",
                     {"success": True, "result": None}, {"result": []},
                     {"success": False, "errors": "malformed"}):
            with self.subTest(body=body):
                result = self.request(body)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::Cloudflare", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_transport_failure(self):
        result = self.request("", status=0, curl_exit=28)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("network/TLS/timeout", result.stderr)
        self.assertIn("may have reached Cloudflare", result.stderr)

    def test_successful_response_is_preserved(self):
        body = {"success": True, "errors": [], "result": []}
        result = self.request(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), body)
        self.assertEqual(result.stderr, "")

    def test_empty_token(self):
        result = self.request({}, extra_env={"CF_API_TOKEN": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cf_api_token is empty", result.stderr)

    def test_error_annotation_escaping_and_redaction(self):
        result = self.request({"success": False, "errors": [
            {"code": 1, "message": f"{TOKEN}\n::warning::injected\r100%"}
        ]}, 403)
        self.assertNotIn(TOKEN, result.stderr)
        self.assertIn("[REDACTED]%0A::warning::injected%0D100%25", result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_original_issue_at_actual_action_step(self):
        script = next(s["run"] for s in ACTION["runs"]["steps"] if s.get("id") == "check_ip_list")
        result, env = self.run_shell(script, {
            "success": False, "errors": [{"code": 9106, "message": "Authentication failed (status: 400)"}],
            "result": None,
        }, 400)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("9106", result.stderr)
        self.assertEqual(env, "")  # Never misclassify failed auth as a missing list.

    def test_list_lookup_empty_and_existing(self):
        script = next(s["run"] for s in ACTION["runs"]["steps"] if s.get("id") == "check_ip_list")
        for lists, expected in (([], "list_exists=false"), ([{
            "name": "bypass_cloudflare_for_github_action_list", "id": LIST
        }], "list_exists=true")):
            with self.subTest(lists=lists):
                result, env = self.run_shell(script, {"success": True, "result": lists})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, env)
                if lists:
                    self.assertIn(f"list_id={LIST}", env)

    def test_entrypoint_404_is_the_only_missing_resource_exception(self):
        body = {"success": False, "errors": [{"code": 10003, "message": "not found"}], "result": None}
        script = 'cf_entrypoint "/zones/$CF_ZONE_ID/rulesets/phases/http_request_firewall_custom/entrypoint"'
        result, _ = self.run_shell(script, body, 404)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"result": None})
        self.assertEqual(result.stderr, "")
        for status, response in ((403, body), (404, "<html>not found</html>")):
            result, _ = self.run_shell(script, response, status)
            self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(self.request(body, 404).returncode, 0)

    def test_invalid_inputs_fail_before_network_access(self):
        script = ACTION["runs"]["steps"][0]["run"]
        defaults = {"DISABLE_BFM": "false", "BFM_DELAY": "10"}
        for overrides, expected in (
            ({"CF_ACCOUNT_ID": ""}, "CF_ACCOUNT_ID"),
            ({"CF_ZONE_ID": "wrong"}, "CF_ZONE_ID"),
            ({"CF_API_TOKEN": ""}, "cf_api_token is empty"),
            ({"DISABLE_BFM": "yes"}, "disable_bot_fight_mode"),
            ({"BFM_DELAY": "1; echo injected"}, "bfm_propagation_delay"),
        ):
            with self.subTest(overrides=overrides):
                result, env = self.run_shell(
                    'curl() { echo NETWORK_REACHED >&2; return 99; }\n' + script,
                    {}, extra_env={**defaults, **overrides},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("NETWORK_REACHED", result.stderr)
                self.assertEqual(env, "")

    def test_bfm_missing_state_is_not_assumed_false(self):
        script = next(s["run"] for s in ACTION["runs"]["steps"] if s["name"] == "Save Bot Fight Mode State")
        result, env = self.run_shell(script, {"success": True, "result": {"fight_mode": False}})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(env, "")

    def test_cleanup_failures_do_not_announce_success(self):
        # gacts/run-and-post-run executes each logical line in a separate shell.
        # Match its backslash joining rather than testing a misleading single script.
        for step in ACTION["runs"]["steps"]:
            if "post" not in step.get("with", {}):
                continue
            with self.subTest(step=step["name"]):
                script = step["with"]["post"]
                replacements = {
                    "github.action_path": str(ROOT), "inputs.cf_zone_id": ZONE,
                    "inputs.cf_account_id": ACCOUNT, "env.list_id": LIST,
                    "env.bfm_original_fight_mode": "true", "env.bfm_original_enable_js": "false",
                }
                for expression, value in replacements.items():
                    script = script.replace("${{ " + expression + " }}", value)
                commands = script.replace("\\\n", "").strip().splitlines()
                self.assertEqual(len(commands), 1, "post must run in one shell")
                result, _ = self.run_shell(commands[0], {
                    "success": False, "errors": [{"code": 10000, "message": "Authentication error"}],
                    "result": None,
                }, 403)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("successfully", result.stdout)
                self.assertNotIn("accepted", result.stdout)
                self.assertIn("HTTP 403", result.stderr)
                result, _ = self.run_shell(commands[0], {
                    "success": True,
                    "result": {"operation_id": "operation-1", "fight_mode": True, "enable_js": False},
                })
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Strict fake curl + post-job assertions for the real Actions runner lifecycle.

No network fallback: unexpected requests fail the job. Only synthetic tokens/data
are used. CI copies this file to a temporary bin/curl before invoking the action.
"""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

A, B = "a" * 32, "b" * 32
ZA, ZB = "1" * 32, "2" * 32
LA, LB = "c" * 32, "d" * 32
LOG = Path(os.environ["LIFECYCLE_LOG"])
VARIANT = os.environ["BOT_VARIANT"]


def verify():
    records = [json.loads(line) for line in LOG.read_text().splitlines()]
    writes = [r for r in records if r["method"] == "PUT"]
    for account, list_id in ((A, LA), (B, LB)):
        path = f"/accounts/{account}/rules/lists/{list_id}/items"
        bodies = [r["body"] for r in writes if r["path"] == path]
        assert bodies == [[{"ip": "192.0.2.1", "comment": "GitHub Actions runner"}], []], bodies
    for zone in (ZA, ZB):
        bodies = [r["body"] for r in writes if r["path"] == f"/zones/{zone}/bot_management"]
        expected = [{"fight_mode": False}, {"fight_mode": True}] if zone == ZA or VARIANT == "bfm-on" else []
        assert bodies == expected, (zone, bodies, expected)
    # Every PUT must belong to the expected resources; no global-env poisoning.
    expected_count = 8 if VARIANT == "bfm-on" else 6
    assert len(writes) == expected_count, writes
    print(f"Verified real post-run lifecycle: two isolated invocations, variant={VARIANT}")


def fake_curl():
    args = sys.argv[1:]
    if "https://api64.ipify.org" in args:
        print("192.0.2.1", end="")
        return

    def option(name):
        return args[args.index(name) + 1]

    url = urlparse(option("--url"))
    assert url.scheme == "https" and url.netloc == "api.cloudflare.com", url
    assert url.path.startswith("/client/v4/"), url.path
    path = url.path.removeprefix("/client/v4")
    method = option("--request")
    body = json.loads(option("--data")) if "--data" in args else None
    headers = [args[i + 1] for i, arg in enumerate(args) if arg == "--header"]
    expected_token = "fixture-a" if A in path or ZA in path else "fixture-b"
    assert f"Authorization: Bearer {expected_token}" in headers, "wrong invocation token"
    record = {"method": method, "path": path, "body": body}
    with LOG.open("a") as output:
        output.write(json.dumps(record) + "\n")
    if method == "GET" and path == f"/accounts/{A}/rules/lists":
        result = [{"name": "bypass_cloudflare_for_github_action_list", "id": LA}]
    elif method == "GET" and path == f"/accounts/{B}/rules/lists":
        result = []  # Exercise create-step output as well as lookup-step output.
    elif method == "POST" and path == f"/accounts/{B}/rules/lists":
        result = {"id": LB}
    elif method == "GET" and path == f"/zones/{ZB}/rulesets/phases/http_request_firewall_custom/entrypoint":
        result = {"id": "e" * 32}
    elif method == "POST" and path == f"/zones/{ZB}/rulesets/{'e' * 32}/rules":
        result = {"id": "e" * 32}
    elif method == "GET" and path in (f"/zones/{ZA}/bot_management", f"/zones/{ZB}/bot_management"):
        result = {"fight_mode": True, "enable_js": True}
        if ZB in path:
            result = {
                "bfm-on": {"fight_mode": True},
                "bfm-off": {"fight_mode": False},
                "sbfm": {"sbfm_definitely_automated": "block", "enable_js": True},
                "enterprise": {"auto_update_model": True, "bm_cookie_enabled": True},
            }[VARIANT]
    elif method == "PUT" and path in (f"/zones/{ZA}/bot_management", f"/zones/{ZB}/bot_management"):
        assert set(body) == {"fight_mode"}, "must not mutate unrelated JavaScript settings"
        result = {**body, "enable_js": True}
    elif method == "PUT" and path in (f"/accounts/{A}/rules/lists/{LA}/items", f"/accounts/{B}/rules/lists/{LB}/items"):
        result = {"operation_id": "fixture-operation"}
    else:
        raise AssertionError(f"Unexpected request: {record}")
    print(json.dumps({"success": True, "errors": [], "result": result}) + "\n200", end="")


if sys.argv[1:] == ["verify"]:
    verify()
else:
    fake_curl()

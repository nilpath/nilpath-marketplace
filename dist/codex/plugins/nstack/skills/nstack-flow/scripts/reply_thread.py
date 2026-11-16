#!/usr/bin/env python3
"""Post a GitHub review reply or a top-level PR comment using current gh authentication.

Python 3.11+, standard library only. Prints one compact JSON result.
Exit 0 means a verified receipt, 1 means a classified failure. Argparse help
exits 0 and usage errors exit 2. An uncertain outcome requires inspecting the
thread before retrying. Repeated invocations can create duplicate replies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GH_TIMEOUT_SECONDS = 60
_BANNER = re.compile(
    r"\A🤖 Automated post by `nstack`(?:, model `([^`\r\n]+)`)?\."
    r"(?:\r?\n\r?\n|\r?\n?\Z)"
)
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


@dataclass(frozen=True)
class Target:
    hostname: str
    repo: str
    pr: int
    root_comment_id: int | None


class ReplyError(Exception):
    def __init__(
        self, code: str, message: str, outcome: str = "not_attempted", **diagnostics: Any,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.outcome = outcome
        self.diagnostics = diagnostics


def validate_hostname(value: str) -> str:
    host, separator, port = value.partition(":")
    if (
        not host
        or len(host) > 253
        or any(_HOST_LABEL.fullmatch(label) is None for label in host.split("."))
        or (separator and (re.fullmatch(r"[0-9]+", port) is None or not 1 <= int(port) <= 65535))
    ):
        raise ValueError("Hostname must be a DNS hostname with an optional numeric port from 1 to 65535.")
    return value


def _valid_model(model: str) -> bool:
    return bool(model.strip()) and "`" not in model and not any(
        unicodedata.category(char).startswith("C") or char in "\u2028\u2029"
        for char in model
    )


def attributed_body(text: str, model: str | None = None) -> str:
    if model is not None and not _valid_model(model):
        raise ValueError("Model must be nonblank and contain no controls, newlines or backticks.")
    while match := _BANNER.match(text):
        if match[1] is not None and not _valid_model(match[1]):
            break
        text = text[match.end():]
    if not text.strip():
        raise ValueError("Reply body must contain nonblank prose beyond its attribution banner.")
    banner = "🤖 Automated post by `nstack`"
    if model is not None:
        banner += f", model `{model}`"
    return f"{banner}.\n\n{text}"


def _diagnostic(value: bytes | str | None, body: str | None) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
    if body is not None:
        for representation in (body, json.dumps(body)[1:-1], json.dumps(body, ensure_ascii=False)[1:-1]):
            text = text.replace(representation, "[reply body omitted]")
    return text


def _gh_api(
    target: Target, endpoint: str, body: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    posting = body is not None
    outcome = "uncertain" if posting else "not_attempted"
    argv = ["gh", "api", "--hostname", target.hostname, "--method", "POST" if posting else "GET", endpoint]
    payload = None
    if posting:
        argv.extend(["--input", "-"])
        payload = json.dumps({"body": body}, ensure_ascii=False).encode("utf-8")
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.PIPE if posting else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ReplyError("gh_launch_failed", str(exc)) from exc
    with process:
        try:
            stdout, stderr = process.communicate(payload, timeout=GH_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            stdout, stderr = process.communicate()
            raise ReplyError(
                "gh_timeout", "gh api timed out.", outcome,
                returncode=process.returncode,
                stdout=_diagnostic(stdout, body), stderr=_diagnostic(stderr, body),
            ) from exc
        except OSError as exc:
            process.kill()
            process.wait()
            raise ReplyError("gh_io_failed", str(exc), outcome) from exc
    diagnostics = {
        "returncode": process.returncode,
        "stdout": _diagnostic(stdout, body),
        "stderr": _diagnostic(stderr, body),
    }
    if process.returncode != 0:
        raise ReplyError("gh_failed", "gh api exited unsuccessfully.", outcome, **diagnostics)
    try:
        response = json.loads(stdout)
    except (ValueError, UnicodeError) as exc:
        raise ReplyError("invalid_response", "gh api did not return valid JSON.", outcome, **diagnostics) from exc
    if not isinstance(response, dict):
        raise ReplyError("invalid_response", "gh api did not return a JSON object.", outcome, **diagnostics)
    return response, diagnostics


def _nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _github_reply(target: Target, body: str) -> dict[str, Any]:
    if target.root_comment_id is not None:
        comment, _ = _gh_api(target, f"repos/{target.repo}/pulls/comments/{target.root_comment_id}")
        if type(comment.get("id")) is not int or comment["id"] != target.root_comment_id:
            raise ReplyError("wrong_comment", "The comment response does not match the requested root ID.")
        if comment.get("in_reply_to_id") is not None:
            raise ReplyError("not_root", "The comment is a reply. Supply the root review-comment database ID.")
    pull, _ = _gh_api(target, f"repos/{target.repo}/pulls/{target.pr}")
    if type(pull.get("number")) is not int or pull["number"] != target.pr:
        raise ReplyError("wrong_pr", "The pull request response does not match the requested PR number.")
    if target.root_comment_id is None:
        issue_url = pull.get("issue_url")
        if not _nonblank_string(issue_url):
            raise ReplyError("wrong_pull_resource", "The pull request response lacks a canonical issue URL.")
        reply, diagnostics = _gh_api(target, f"repos/{target.repo}/issues/{target.pr}/comments", body)
        user = reply.get("user")
        if (
            type(reply.get("id")) is not int or reply["id"] <= 0
            or not _nonblank_string(reply.get("html_url"))
            or not isinstance(user, dict) or not _nonblank_string(user.get("login"))
            or reply.get("issue_url") != issue_url
            or reply.get("body") != body
        ):
            raise ReplyError(
                "invalid_receipt", "The comment receipt is missing fields or does not match the PR and exact body.",
                "uncertain", **diagnostics,
            )
        return {"id": reply["id"], "html_url": reply["html_url"], "user": {"login": user["login"]}}
    canonical_url = pull.get("url")
    if not _nonblank_string(canonical_url) or comment.get("pull_request_url") != canonical_url:
        raise ReplyError("wrong_pull_resource", "The root comment does not belong to the canonical requested PR.")
    reply, diagnostics = _gh_api(
        target, f"repos/{target.repo}/pulls/{target.pr}/comments/{target.root_comment_id}/replies", body,
    )
    user = reply.get("user")
    if (
        type(reply.get("id")) is not int or reply["id"] <= 0
        or not _nonblank_string(reply.get("html_url"))
        or not isinstance(user, dict) or not _nonblank_string(user.get("login"))
        or type(reply.get("in_reply_to_id")) is not int
        or reply["in_reply_to_id"] != target.root_comment_id
        or reply.get("pull_request_url") != canonical_url
        or reply.get("body") != body
    ):
        raise ReplyError(
            "invalid_receipt", "The reply receipt is missing fields or does not match the root, PR and exact body.",
            "uncertain", **diagnostics,
        )
    return {"id": reply["id"], "html_url": reply["html_url"], "user": {"login": user["login"]}}


def _positive_id(value: str) -> int:
    if re.fullmatch(r"[0-9]+", value) is None or int(value) <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer database ID or PR number")
    return int(value)


def _repo(value: str) -> str:
    if (
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9_.-]+", value) is None
        or value.split("/")[1] in {".", ".."}
    ):
        raise argparse.ArgumentTypeError("must be an owner/repo slug")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", help="GitHub hostname, optionally with a port. Defaults to GH_HOST, then github.com.")
    parser.add_argument("--repo", required=True, type=_repo)
    parser.add_argument("--pr", required=True, type=_positive_id)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--comment-id", type=_positive_id, help="Root review-comment database ID, not a reply ID.")
    selector.add_argument("--top-level", action="store_true", help="Post a top-level pull request comment.")
    parser.add_argument("--body-file", required=True, type=Path, help="UTF-8 prose file, never modified.")
    parser.add_argument("--model", help="Optional actually observed executing model, supplied by the caller.")
    args = parser.parse_args(argv)
    hostname = args.hostname if args.hostname is not None else os.environ.get("GH_HOST", "github.com")
    result: dict[str, Any] = {"hostname": hostname, "repo": args.repo, "pr": args.pr}
    if args.comment_id is not None:
        result["root_comment_id"] = args.comment_id
    try:
        validate_hostname(hostname)
        body = attributed_body(args.body_file.read_bytes().decode("utf-8"), args.model)
    except (OSError, UnicodeError, ValueError) as exc:
        result.update(ok=False, outcome="not_attempted", error={"code": "invalid_input", "message": str(exc)})
    else:
        target = Target(hostname, args.repo, args.pr, args.comment_id)
        try:
            receipt = _github_reply(target, body)
        except ReplyError as exc:
            error = {"code": exc.code, "message": str(exc), **exc.diagnostics}
            if exc.outcome == "uncertain":
                error["repair"] = (
                    "Inspect PR comments on the selected hostname before retrying. A comment may already exist."
                    if args.top_level
                    else "Inspect the thread on the selected hostname before retrying. A reply may already exist."
                )
            result.update(ok=False, outcome=exc.outcome, error=error)
        else:
            result.update(ok=True, outcome="posted", reply=receipt)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Observe GitHub pull requests without changing them."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import math
import re
import subprocess
import sys
import time
from typing import Callable, Literal, Never, Protocol, Sequence, TextIO, TypedDict


class PrContext(TypedDict):
    owner: str
    repo: str
    number: int | float


class Check(TypedDict):
    name: str
    description: str
    link: str
    workflow: str
    kind: Literal["passed", "skipped", "failed", "pending", "code-review-gate"]
    reportedState: str


_RollupState = Literal["ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS"] | None
_NonblockedMergeState = Literal["BEHIND", "CLEAN", "CONFLICTING", "DIRTY", "DRAFT", "HAS_HOOKS", "UNKNOWN", "UNSTABLE"]


class _MergeRefusal(TypedDict):
    kind: Literal["refused"]
    mergeStateStatus: Literal["BLOCKED"]
    headRollupState: Literal["ERROR", "FAILURE"]


class _MergeAllowedByState(TypedDict):
    kind: Literal["allowed"]
    basis: Literal["merge-state"]
    mergeStateStatus: _NonblockedMergeState
    headRollupState: _RollupState


class _MergeAllowedByRollup(TypedDict):
    kind: Literal["allowed"]
    basis: Literal["rollup"]
    mergeStateStatus: Literal["BLOCKED"]
    headRollupState: Literal["EXPECTED", "PENDING", "SUCCESS"] | None


_MergeAllowed = _MergeAllowedByState | _MergeAllowedByRollup


class _CiClean(TypedDict):
    kind: Literal["ci-clean"]
    source: Literal["gh-pr-checks", "graphql-rollup"]
    all: list[Check]
    hadPreviousPassingCi: bool
    failed: list[Never]
    pending: list[Never]
    github: _MergeAllowed


class _ReadyGate(TypedDict):
    state: Literal["OPEN"]
    reviewDecision: Literal["APPROVED", "REVIEW_REQUIRED"] | None
    draft: Literal["not-draft", "draft-allowed"]


class _ReadinessProof(TypedDict):
    mergeability: Literal["clear"]
    threads: list[Never]
    ci: _CiClean
    gate: _ReadyGate


class _ReadyPr(TypedDict):
    kind: Literal["ready-pr"]
    context: PrContext
    proof: _ReadinessProof


class _MergedPr(TypedDict):
    kind: Literal["merged-pr"]
    context: PrContext
    mergedAt: str | None


class Clock(Protocol):
    def now(self) -> float: ...
    def observed_at(self) -> str: ...
    def sleep(self, seconds: float) -> None: ...


class _RealClock:
    def now(self) -> float:
        return time.monotonic()

    def observed_at(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def sleep(self, seconds: float) -> None:
        milliseconds = seconds * 1000
        # Bun's promise timers clamp out-of-range delays and truncate fractional milliseconds.
        delay = 1 if milliseconds > 2147483647 or milliseconds < 1 else int(milliseconds)
        time.sleep(delay / 1000)


Run = Callable[[list[str]], subprocess.CompletedProcess[str]]
_UNDEFINED = object()
_JS_SPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_MERGE_STATES = ("BEHIND", "BLOCKED", "CLEAN", "CONFLICTING", "DIRTY", "DRAFT", "HAS_HOOKS", "UNKNOWN", "UNSTABLE")
_ROLLUP_STATES = ("ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS")
_REVIEW_DECISIONS = ("APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED")


REVIEW_THREADS_QUERY = """
query ReviewThreads($owner: String!, $repo: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          comments(first: 10) {
            nodes {
              body
              createdAt
              path
              line
              author { login }
            }
          }
        }
      }
    }
  }
}
"""
PR_COMMIT_STATUS_QUERY = """
query PrCommitStatuses($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      commits(last: 50) {
        nodes {
          commit {
            oid
            statusCheckRollup {
              state
            }
          }
        }
      }
    }
  }
}
"""
PR_CHECK_ROLLUP_QUERY = """
query PrCheckRollup($owner: String!, $repo: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      commits(last: 1) {
        nodes {
          commit {
            statusCheckRollup {
              contexts(first: 100, after: $after) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  __typename
                  ... on CheckRun {
                    name
                    status
                    conclusion
                    detailsUrl
                  }
                  ... on StatusContext {
                    context
                    state
                    targetUrl
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _json(value) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) in (int, float):
        return _number_text(value) if math.isfinite(value) else "null"
    if isinstance(value, dict):
        return "{" + ",".join(_json(key) + ":" + _json(item) for key, item in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_json(item) for item in value) + "]"
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    return re.sub("[\ud800-\udfff]", lambda m: "\\u%04x" % ord(m[0]), text)


def _utf16_slice(value: str, length: int) -> str:
    return value.encode("utf-16-le", "surrogatepass")[:length * 2].decode("utf-16-le", "surrogatepass")


def _first_line(value: str) -> str:
    return _utf16_slice(re.split(r"\r?\n", value.strip(_JS_SPACE), maxsplit=1)[0], 240)


def _number(value: str) -> float:
    text = value.strip(_JS_SPACE)
    if not text:
        return 0.0
    if re.fullmatch(r"0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+", text):
        try:
            return float(int(text, 0))
        except OverflowError:
            return math.inf
    if not re.fullmatch(r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)", text):
        return math.nan
    return float(text)


def _number_text(value: int | float) -> str:
    if value == 0:
        return "0"
    text = str(float(value))
    if "e" not in text:
        return text[:-2] if text.endswith(".0") else text
    mantissa, exponent = text.split("e")
    power = int(exponent)
    if -6 <= power < 21:
        sign = "-" if mantissa.startswith("-") else ""
        digits = mantissa.lstrip("-").replace(".", "")
        point = 1 + power
        if point <= 0:
            return sign + "0." + "0" * -point + digits
        if point >= len(digits):
            return sign + digits + "0" * (point - len(digits))
        return sign + digits[:point] + "." + digits[point:]
    return mantissa + "e" + ("+" if power >= 0 else "-") + str(abs(power))


def parse_pr_number(value, label: str = "PR number") -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0 or value != int(value):
        raise ValueError(f"{label} must be a positive integer")
    return value


class WatcherQueryError(Exception):
    def __init__(self, failure: dict):
        super().__init__(failure["detail"])
        self.failure = failure


class ChecksUnavailable(WatcherQueryError):
    def __init__(self, detail: str):
        super().__init__({"kind": "checks-unavailable", "retryable": True, "detail": detail})


def _missing(path: str, value=_UNDEFINED):
    failure = {"kind": "missing-key", "retryable": True}
    if value is _UNDEFINED:
        failure["detail"] = f"missing {path}"
    else:
        raw = _json(value)
        failure.update(detail=f"invalid {path}: {raw}", rawValue=raw)
    raise WatcherQueryError(failure)


def _record(value, path: str) -> dict:
    if not isinstance(value, dict):
        _missing(path, value)
    return value


def _list(value, path: str) -> list:
    if not isinstance(value, list):
        _missing(path, value)
    return value


def _at(value, path: Sequence[str]):
    current = value
    for key in path:
        obj = _record(current, ".".join(path))
        if key not in obj:
            _missing(".".join(path))
        current = obj[key]
    return current


def _get(obj: dict, key: str):
    return obj.get(key, _UNDEFINED)


def _string(value, path: str) -> str:
    if not isinstance(value, str):
        _missing(path, value)
    return value


def _optional_string(value, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _enum(value, values: Sequence[str], path: str, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or value not in values:
        _missing(path, value)
    return value


def _reject_constant(value: str):
    raise ValueError(f"Invalid JSON constant {value}")


def _parse_json(text: str, label: str):
    try:
        return json.loads(text, parse_constant=_reject_constant, parse_int=float)
    except (ValueError, RecursionError) as error:
        raise WatcherQueryError({"kind": "json-parse", "retryable": True, "detail": f"{label}: {error}"}) from error


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True)
    return subprocess.CompletedProcess(
        argv, -1 if result.returncode < 0 else result.returncode,
        result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace"),
    )


def _run_json(run: Run, argv: list[str]):
    result = run(argv)
    if result.returncode != 0:
        raise WatcherQueryError({
            "kind": "command-exit", "retryable": True, "code": result.returncode,
            "detail": _first_line(result.stderr) or f"{' '.join(argv)} exited {result.returncode}",
        })
    return _parse_json(result.stdout, " ".join(argv))


def _github_parts(value: str, *, strip_git: bool = False) -> list[str] | None:
    # WHATWG special URLs remove tabs/newlines and normalize backslashes and dot segments.
    text = value.strip("".join(chr(i) for i in range(33)))
    text = re.sub(r"[\t\r\n]", "", text).replace("\\", "/")
    match = re.fullmatch(r"(?i:https):/*([^/?#]+)([^?#]*)(?:\?([^#]*))?(?:#(.*))?", text)
    if not match or match[3] or match[4]:
        return None
    authority = match[1]
    if "@" in authority:
        credentials, authority = authority.rsplit("@", 1)
        if credentials not in ("", ":"):
            return None
    host, sep, port = authority.partition(":")
    encoded_host = bytearray()
    try:
        for part in re.split(r"(%[0-9a-fA-F]{2})", host):
            if re.fullmatch(r"%[0-9a-fA-F]{2}", part):
                encoded_host.append(int(part[1:], 16))
            else:
                encoded_host.extend(part.encode("utf-8"))
        host = encoded_host.decode("utf-8")
        if any(ord(char) <= 32 or ord(char) == 127 or char in "#%/:<>?@[\\]^|" for char in host):
            raise ValueError(f'"{value}" cannot be parsed as a URL.')
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError(f'"{value}" cannot be parsed as a URL.') from None
    if host.lower() != "github.com" or (sep and port and (not re.fullmatch("[0-9]+", port) or int(port) != 443)):
        return None
    parts = []
    path = match[2].split("/")
    for index, part in enumerate(path):
        lowered = part.lower().replace("%2e", ".")
        if lowered == ".":
            if index == len(path) - 1:
                parts.append("")
            continue
        if lowered == "..":
            if parts:
                parts.pop()
            if index == len(path) - 1:
                parts.append("")
        else:
            parts.append(part)
    if strip_git and parts and parts[-1].endswith(".git"):
        parts[-1] = parts[-1][:-4]
    return [_url_path_part(part) for part in parts if part]


def _url_path_part(part: str) -> str:
    part = part.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return "".join(
        "".join(f"%{byte:02X}" for byte in char.encode("utf-8"))
        if ord(char) <= 32 or ord(char) > 126 or char in '"<>^`{}' else char
        for char in part
    )


def parse_remote(value: str) -> dict | None:
    text = value.strip(_JS_SPACE)
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text[15:]
    if text.startswith("ssh://git@github.com/"):
        text = "https://github.com/" + text[21:]
    try:
        parts = _github_parts(text, strip_git=True)
    except ValueError:
        return None
    if parts is None:
        return None
    return {"owner": parts[0], "repo": parts[1]} if len(parts) == 2 else None


def parse_pr_url(value: str) -> PrContext:
    try:
        parts = _github_parts(value)
        if parts is None or len(parts) != 4 or parts[2] != "pull":
            raise ValueError("not a canonical GitHub pull URL")
        return {"owner": parts[0], "repo": parts[1], "number": parse_pr_number(_number(parts[3]))}
    except ValueError as error:
        raise WatcherQueryError({
            "kind": "invalid-context-url", "retryable": False, "rawValue": value,
            "detail": f"could not infer owner/repo from PR URL: {value} ({error})",
        }) from error


def resolve_context(run: Run, owner: str | None, repo: str | None, pr: int | float | None) -> PrContext:
    if pr is not None and owner is not None and repo is not None:
        return {"owner": owner, "repo": repo, "number": pr}
    if pr is not None:
        result = run(["git", "remote", "get-url", "origin"])
        origin = parse_remote(result.stdout) if result.returncode == 0 else None
        if origin is not None:
            return {"owner": origin["owner"] if owner is None else owner,
                    "repo": origin["repo"] if repo is None else repo, "number": pr}
    argv = ["gh", "pr", "view"]
    if pr is not None:
        argv.append(_number_text(pr))
    obj = _record(_run_json(run, argv + ["--json", "number,url"]), "current PR")
    inferred = parse_pr_url(_string(_get(obj, "url"), "current PR.url"))
    return {"owner": inferred["owner"] if owner is None else owner,
            "repo": inferred["repo"] if repo is None else repo,
            "number": parse_pr_number(_get(obj, "number"), "current PR.number") if pr is None else pr}


def parse_pull_request(value, context: PrContext) -> dict:
    obj = _record(value, "pull request")
    if type(_get(obj, "isDraft")) is not bool:
        _missing("pull request.isDraft", _get(obj, "isDraft"))
    decision = _get(obj, "reviewDecision")
    return {
        "context": context,
        "mergeable": _enum(_get(obj, "mergeable"), ("MERGEABLE", "CONFLICTING", "UNKNOWN"), "pull request.mergeable"),
        "mergeStateStatus": _enum(_get(obj, "mergeStateStatus"), _MERGE_STATES, "pull request.mergeStateStatus"),
        "reviewDecision": _enum(None if decision == "" else decision, _REVIEW_DECISIONS, "pull request.reviewDecision", nullable=True),
        "headRefOid": _optional_string(_get(obj, "headRefOid"), "pull request.headRefOid"),
        "headRefName": _string(_get(obj, "headRefName"), "pull request.headRefName"),
        "baseRefName": _string(_get(obj, "baseRefName"), "pull request.baseRefName"),
        "state": _enum(_get(obj, "state"), ("OPEN", "CLOSED", "MERGED"), "pull request.state"),
        "mergedAt": _optional_string(_get(obj, "mergedAt"), "pull request.mergedAt"),
        "isDraft": obj["isDraft"],
    }


def _graphql_args(query: str, context: PrContext, after: str | None = None) -> list[str]:
    argv = ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"owner={context['owner']}",
            "-f", f"repo={context['repo']}", "-F", f"pr={_number_text(context['number'])}"]
    return argv if after is None else argv + ["-f", f"after={after}"]


def _check_details(obj: dict, name_key: str) -> dict:
    return {
        "name": _string(_get(obj, name_key), name_key),
        "description": obj["description"] if isinstance(obj.get("description"), str) else "",
        "link": obj["link"] if isinstance(obj.get("link"), str) else obj["detailsUrl"] if isinstance(obj.get("detailsUrl"), str) else "",
        "workflow": obj["workflow"] if isinstance(obj.get("workflow"), str) else "",
    }


def _gate_or(kind: str, details: dict, state: str) -> Check:
    return {**details, "kind": "code-review-gate" if details["name"] == "Code Review Gate" else kind, "reportedState": state}


def parse_fast_check(value) -> Check:
    obj = _record(value, "check")
    details = _check_details(obj, "name")
    state = _string(_get(obj, "state"), "check.state").upper()
    bucket = _string(_get(obj, "bucket"), "check.bucket")
    if state == "ACTION_REQUIRED":
        return _gate_or("failed", details, state)
    if bucket == "fail" or state in ("FAILURE", "ERROR"):
        kind = "failed"
    elif bucket == "pending":
        return _gate_or("pending", details, state)
    elif bucket == "pass":
        kind = "passed"
    elif bucket == "skipping":
        kind = "skipped"
    else:
        kind = "failed"
    return {**details, "kind": kind, "reportedState": state}


def map_rollup_node(value) -> Check | None:
    obj = _record(value, "rollup node")
    typename = obj.get("__typename")
    if typename not in ("CheckRun", "StatusContext"):
        return None
    details = _check_details(obj, "name" if typename == "CheckRun" else "context")
    if isinstance(obj.get("targetUrl"), str):
        details["link"] = obj["targetUrl"]
    if typename == "CheckRun":
        status = obj["status"].upper() if isinstance(obj.get("status"), str) else ""
        conclusion = obj["conclusion"].upper() if isinstance(obj.get("conclusion"), str) else ""
        if status != "COMPLETED":
            return _gate_or("pending", details, "PENDING")
        if conclusion == "SUCCESS":
            return {**details, "kind": "passed", "reportedState": "SUCCESS"}
        if conclusion in ("NEUTRAL", "SKIPPED"):
            return {**details, "kind": "skipped", "reportedState": conclusion}
        if conclusion == "ACTION_REQUIRED":
            return _gate_or("failed", details, conclusion)
        return {**details, "kind": "failed", "reportedState": "FAILURE"}
    state = obj["state"].upper() if isinstance(obj.get("state"), str) else ""
    if state in ("PENDING", "EXPECTED"):
        return _gate_or("pending", details, "PENDING")
    return {**details, "kind": "passed" if state == "SUCCESS" else "failed", "reportedState": state or "FAILURE"}


def _rollup_page(run: Run, context: PrContext, after: str | None) -> dict:
    value = _run_json(run, _graphql_args(PR_CHECK_ROLLUP_QUERY, context, after))
    commits = _list(_at(value, ("data", "repository", "pullRequest", "commits", "nodes")), "commits.nodes")
    if not commits:
        return {"checks": [], "endCursor": None}
    commit = _record(_at(commits[-1], ("commit",)), "commit")
    if _get(commit, "statusCheckRollup") is None:
        return {"checks": [], "endCursor": None}
    contexts = _record(_at(commit, ("statusCheckRollup", "contexts")), "contexts")
    checks = [map_rollup_node(node) for node in _list(_get(contexts, "nodes"), "contexts.nodes")]
    return {"checks": [check for check in checks if check is not None], "endCursor": _cursor(contexts, "contexts")}


def _cursor(obj: dict, path: str) -> str | None:
    page = _record(_get(obj, "pageInfo"), path + ".pageInfo")
    if type(_get(page, "hasNextPage")) is not bool:
        _missing(path + ".pageInfo.hasNextPage", _get(page, "hasNextPage"))
    cursor = _optional_string(_get(page, "endCursor"), path + ".pageInfo.endCursor")
    return cursor if page["hasNextPage"] and cursor else None


def resolve_checks(run: Run, context: PrContext) -> dict:
    result = run(["gh", "pr", "checks", _number_text(context["number"]), "--repo",
                  f"{context['owner']}/{context['repo']}", "--json", "name,state,description,link,workflow,bucket"])
    direct = None
    if result.returncode in (0, 1, 8) and result.stdout.strip(_JS_SPACE):
        try:
            value = _parse_json(result.stdout, "gh pr checks")
            if isinstance(value, list):
                direct = [parse_fast_check(item) for item in value]
        except WatcherQueryError:
            pass
    if direct:
        return {"source": "gh-pr-checks", "checks": direct}
    checks = []
    after = None
    while True:
        page = _rollup_page(run, context, after)
        checks.extend(page["checks"])
        after = page["endCursor"]
        if after is None:
            break
    if checks:
        return {"source": "graphql-rollup", "checks": checks}
    if direct is not None:
        suffix = "fast path and GraphQL rollup were empty"
    else:
        suffix = f"fast path exit={result.returncode}; GraphQL rollup was empty"
        detail = _first_line(result.stderr)
        if detail:
            suffix += f"; {detail}"
    raise ChecksUnavailable(f"could not read PR checks: {suffix}")


def _parse_comment(value) -> dict:
    obj = _record(value, "review comment")
    author = None if _get(obj, "author") is None else _record(_get(obj, "author"), "review comment.author")
    author_login = None if author is None else _optional_string(_get(author, "login"), "review comment.author.login")
    body = _string(_get(obj, "body"), "review comment.body")
    path = _optional_string(_get(obj, "path"), "review comment.path")
    line = _get(obj, "line")
    if line is not None and (type(line) not in (int, float) or not math.isfinite(line) or line != int(line)):
        _missing("review comment.line", line)
    return {
        "authorLogin": author_login, "body": body, "path": path,
        "line": line, "createdAt": _string(_get(obj, "createdAt"), "review comment.createdAt"),
    }


def parse_review_thread_page(value) -> dict:
    obj = _record(_at(value, ("data", "repository", "pullRequest", "reviewThreads")), "reviewThreads")
    threads = []
    for node in _list(_get(obj, "nodes"), "reviewThreads.nodes"):
        thread = _record(node, "review thread")
        if type(_get(thread, "isResolved")) is not bool:
            _missing("review thread.isResolved", _get(thread, "isResolved"))
        comments = _list(_at(thread, ("comments", "nodes")), "review thread.comments.nodes")
        threads.append({"id": _string(_get(thread, "id"), "review thread.id"),
                        "firstComment": _parse_comment(comments[0]) if comments else None,
                        "resolved": thread["isResolved"]})
    return {"threads": threads, "endCursor": _cursor(obj, "reviewThreads")}


def _is_bugbot(comment: dict | None) -> bool:
    if comment is None:
        return False
    author = (comment["authorLogin"] or "").lower()
    body = comment["body"].lower()
    return "bugbot" in author or (author == "cursor" and any(
        token in body for token in ("bugbot", "cursor_automation_id", "agentic security review", "description start", "severity")))


def build_review_threads(threads: list[dict]) -> list[dict]:
    keys = set()
    keyless = False
    for thread in threads:
        comment = thread["firstComment"]
        if not _is_bugbot(comment):
            continue
        key = None
        for token in ("RUN_ID", "CURSOR_AUTOMATION_ID"):
            match = re.search(token + ":[" + _JS_SPACE + r"]*([a-zA-Z0-9_.:-]+)", comment["body"])
            if match:
                key = match[1]
                break
        if key is None:
            keyless = True
        else:
            keys.add(key)
    passes = len(keys) if keys else 1 if keyless else 0
    return [{"id": item["id"], "firstComment": item["firstComment"], "isBugbot": _is_bugbot(item["firstComment"]),
             "bugbotReviewPasses": passes} for item in threads if not item["resolved"]]


def resolve_review_threads(run: Run, context: PrContext) -> list[dict]:
    threads = []
    after = None
    while True:
        page = parse_review_thread_page(_run_json(run, _graphql_args(REVIEW_THREADS_QUERY, context, after)))
        threads.extend(page["threads"])
        after = page["endCursor"]
        if after is None:
            return build_review_threads(threads)


def _commit_rollups(run: Run, context: PrContext) -> list[dict]:
    value = _run_json(run, _graphql_args(PR_COMMIT_STATUS_QUERY, context))
    commits = _list(_at(value, ("data", "repository", "pullRequest", "commits", "nodes")), "commits.nodes")
    result = []
    for index, item in enumerate(commits):
        commit = _record(_at(item, ("commit",)), f"commits[{index}].commit")
        rollup = _get(commit, "statusCheckRollup")
        result.append({
            "oid": _string(_get(commit, "oid"), f"commits[{index}].oid"),
            "state": None if rollup is None else _enum(_at(rollup, ("state",)), _ROLLUP_STATES,
                                                     f"commits[{index}].statusCheckRollup.state", nullable=True),
        })
    return result


def order_stack(context: PrContext, opened: list[dict]) -> list[PrContext]:
    by_number = {pr["number"]: pr for pr in opened}
    by_head = {pr["headRefName"]: pr for pr in opened}
    children = {}
    for pr in opened:
        children.setdefault(pr["baseRefName"], []).append(pr)
    for values in children.values():
        values.sort(key=lambda pr: pr["number"])
    start = by_number.get(context["number"])
    if start is None:
        return [context]
    down = []
    current = start
    while current["baseRefName"] in by_head:
        current = by_head[current["baseRefName"]]
        down.append(current)
    seen = {pr["number"] for pr in down} | {start["number"]}
    up = []

    def visit(parent):
        for child in children.get(parent["headRefName"], []):
            if child["number"] in seen:
                continue
            seen.add(child["number"])
            up.append(child)
            visit(child)

    visit(start)
    return [{**context, "number": pr["number"]} for pr in [*reversed(down), start, *up]]


def discover_stack(run: Run, context: PrContext) -> list[PrContext]:
    value = _run_json(run, ["gh", "pr", "list", "--repo", f"{context['owner']}/{context['repo']}",
                            "--state", "open", "--limit", "300", "--json", "number,headRefName,baseRefName"])
    opened = []
    for index, item in enumerate(_list(value, "open PRs")):
        obj = _record(item, f"open PRs[{index}]")
        opened.append({
            "number": parse_pr_number(_get(obj, "number"), f"open PRs[{index}].number"),
            "headRefName": _string(_get(obj, "headRefName"), f"open PRs[{index}].headRefName"),
            "baseRefName": _string(_get(obj, "baseRefName"), f"open PRs[{index}].baseRefName"),
        })
    return order_stack(context, opened)


def assess_github_merge(merge_state_status: str, head_rollup_state: str | None) -> _MergeAllowed | _MergeRefusal:
    base = {"mergeStateStatus": merge_state_status, "headRollupState": head_rollup_state}
    if merge_state_status == "BLOCKED" and head_rollup_state in ("ERROR", "FAILURE"):
        return {"kind": "refused", **base}
    return {"kind": "allowed", "basis": "rollup" if merge_state_status == "BLOCKED" else "merge-state", **base}


def read_snapshot(run: Run, context: PrContext, pending_history: str = "include", allow_draft: bool = False) -> dict:
    facts = parse_pull_request(_run_json(run, [
        "gh", "pr", "view", _number_text(context["number"]), "--repo", f"{context['owner']}/{context['repo']}",
        "--json", "mergeable,mergeStateStatus,reviewDecision,headRefOid,headRefName,baseRefName,state,mergedAt,isDraft",
    ]), context)
    if facts["state"] == "MERGED" or facts["mergedAt"] is not None:
        return {"kind": "merged", "context": context, "facts": facts}
    if facts["state"] == "CLOSED":
        return {"kind": "closed", "context": context, "facts": facts}
    threads = resolve_review_threads(run, context)
    checks = resolve_checks(run, context)
    failed = [check for check in checks["checks"] if check["kind"] == "failed"]
    pending = [check for check in checks["checks"] if check["kind"] == "pending"]
    base = {"source": checks["source"], "all": checks["checks"], "hadPreviousPassingCi": False}
    if not failed and pending and pending_history == "omit":
        ci = {**base, "kind": "ci-pending", "failed": [], "pending": pending}
    else:
        commits = _commit_rollups(run, context)
        head = next((commit["state"] for commit in commits if commit["oid"] == facts["headRefOid"]), None) if facts["headRefOid"] is not None else None
        github = assess_github_merge(facts["mergeStateStatus"], head)
        base["hadPreviousPassingCi"] = any(commit["oid"] != facts["headRefOid"] and commit["state"] == "SUCCESS" for commit in commits)
        if failed:
            ci = {**base, "kind": "ci-failing", "failed": failed, "pending": pending, "github": github}
        elif github["kind"] == "refused":
            ci = {**base, "kind": "ci-github-rejected", "failed": [], "pending": pending, "github": github}
        elif pending:
            ci = {**base, "kind": "ci-pending", "failed": [], "pending": pending}
        else:
            ci = {**base, "kind": "ci-clean", "failed": [], "pending": [], "github": github}
    return {
        "kind": "open", "context": context, "facts": facts, "threads": threads, "ci": ci,
        "reviewAutomationRunning": any(check["kind"] == "pending" and any(
            token in check["name"].lower() for token in ("bugbot", "security review", "pr review automation", "review automation"))
            for check in checks["checks"]),
    }


def _conflict_blocker(row: dict) -> dict | None:
    if row["kind"] == "open" and (row["facts"]["mergeable"] == "CONFLICTING" or row["facts"]["mergeStateStatus"] in ("DIRTY", "CONFLICTING")):
        return {"kind": "merge-conflicts", "pr": row["context"], "facts": row["facts"]}
    return None


def _thread_blocker(row: dict) -> dict | None:
    return {"kind": "review-threads", "pr": row["context"], "threads": row["threads"]} if row["kind"] == "open" and row["threads"] else None


def _ci_blocker(row: dict) -> dict | None:
    return {"kind": "failing-checks", "pr": row["context"], "ci": row["ci"]} if row["kind"] == "open" and row["ci"]["kind"] in ("ci-failing", "ci-github-rejected") else None


def _gate_reason(row: dict, allow_draft: bool) -> str | None:
    if row["kind"] == "merged":
        return None
    if row["kind"] == "closed":
        return "closed-without-merge"
    if row["facts"]["isDraft"] and not allow_draft:
        return "draft-pr"
    return "changes-requested" if row["facts"]["reviewDecision"] == "CHANGES_REQUESTED" else None


def _gate_blocker(row: dict, allow_draft: bool) -> dict | None:
    reason = _gate_reason(row, allow_draft)
    if reason is None or (reason == "draft-pr" and row["kind"] == "open" and row["ci"]["kind"] == "ci-pending"):
        return None
    return {"kind": "merge-gate", "pr": row["context"], "reason": reason}


def _ready_contribution(row: dict, allow_draft: bool) -> _ReadyPr | _MergedPr | None:
    if row["kind"] == "merged":
        return {"kind": "merged-pr", "context": row["context"], "mergedAt": row["facts"]["mergedAt"]}
    if (row["kind"] != "open" or row["ci"]["kind"] != "ci-clean" or row["threads"]
            or _conflict_blocker(row) is not None or _gate_reason(row, allow_draft) is not None):
        return None
    return {"kind": "ready-pr", "context": row["context"], "proof": {
        "mergeability": "clear", "threads": [], "ci": row["ci"],
        "gate": {"state": "OPEN", "reviewDecision": row["facts"]["reviewDecision"],
                 "draft": "draft-allowed" if row["facts"]["isDraft"] else "not-draft"},
    }}


def classify_pr(row: dict, allow_draft: bool = False) -> dict:
    for blocker in (_conflict_blocker(row), _thread_blocker(row), _ci_blocker(row), _gate_blocker(row, allow_draft)):
        if blocker is not None:
            return {"kind": "blocker", "blocker": blocker}
    if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending":
        return {"kind": "waiting", "frontier": row["context"], "pending": row["ci"]["pending"]}
    ready = _ready_contribution(row, allow_draft)
    if ready is None:
        raise RuntimeError("snapshot has no classified decision")
    return {"kind": "merged" if ready["kind"] == "merged-pr" else "ready", "pr": ready}


def select_tier_major_stack_decision(rows: Sequence[dict], allow_draft: bool = False) -> dict:
    for tier in (_conflict_blocker, _thread_blocker, _ci_blocker):
        for row in rows:
            blocker = tier(row)
            if blocker is not None:
                return {"kind": "blocker", "blocker": blocker}
    for row in rows:
        blocker = _gate_blocker(row, allow_draft)
        if blocker is not None:
            return {"kind": "blocker", "blocker": blocker}
    for row in rows:
        if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending":
            return {"kind": "waiting", "frontier": row["context"], "pending": row["ci"]["pending"]}
    prs = [_ready_contribution(row, allow_draft) for row in rows]
    if not prs or any(pr is None for pr in prs):
        raise RuntimeError("stack has no classified decision")
    return {"kind": "clear", "prs": prs}


def query_backoff_seconds(interval: float, failures: int) -> float:
    if failures >= 4:
        return 300
    return min(max(interval, 60) * 2 ** (failures - 1), 300)


def verdict_factory(clock: Clock, mode: str):
    sequence = 0

    def stamp(payload: dict) -> dict:
        nonlocal sequence
        sequence += 1
        return {"schemaVersion": 1, "sequence": sequence, "observedAt": clock.observed_at(), "mode": mode, **payload}

    return stamp


def _blocker_verdict(stamp, blocker: dict) -> dict:
    code = {"merge-conflicts": 2, "review-threads": 3, "failing-checks": 4, "merge-gate": 6}[blocker["kind"]]
    return stamp({"kind": "BLOCKER", "terminal": True, "exitCode": code, "blocker": blocker})


def status_query_verdict(stamp, failures: int, failure: dict) -> dict:
    return stamp({"kind": "BLOCKER", "terminal": True, "exitCode": 7,
                  "blocker": {"kind": "status-query", "failures": failures, "failure": failure}})


def _deadline_passed(started: float, options: dict, now: float) -> bool:
    return options["timeout"] > 0 and now - started >= options["timeout"]


@dataclass(frozen=True)
class _Terminal:
    verdict: dict


@dataclass(frozen=True)
class _Sleep:
    seconds: float
    on_deadline: Callable[[], dict] | None = None


def _poll_until_terminal(clock: Clock, emit, options: dict, stamp, step) -> dict:
    failures = 0
    started = clock.now()
    while True:
        try:
            result = step()
            failures = 0
        except WatcherQueryError as error:
            failures += 1
            if not error.failure["retryable"] or failures >= options["maxQueryErrors"]:
                return status_query_verdict(stamp, failures, error.failure)
            retry = query_backoff_seconds(options["interval"], failures)
            emit(stamp({"kind": "RETRY", "terminal": False, "failure": error.failure,
                        "consecutiveFailures": failures, "retryInSeconds": retry}))
            if _deadline_passed(started, options, clock.now()):
                return stamp({"kind": "TIMEOUT", "terminal": True, "exitCode": 5,
                              "reason": {"kind": "status-unavailable", "failure": error.failure}})
            clock.sleep(retry)
            continue
        if isinstance(result, _Terminal):
            return result.verdict
        if isinstance(result, _Sleep):
            if result.on_deadline is not None and _deadline_passed(started, options, clock.now()):
                return result.on_deadline()
            clock.sleep(result.seconds)


def run_simple(run: Run, clock: Clock, emit, contexts: Sequence[PrContext], mode: str, status_only: bool, options: dict) -> dict:
    stamp = verdict_factory(clock, mode)

    def step():
        rows = [read_snapshot(run, context, "include", options["allowDraft"]) for context in contexts]
        if not rows:
            raise RuntimeError("watch context cannot be empty")
        if status_only:
            return _Terminal(stamp({"kind": "STATUS", "terminal": True, "exitCode": 0, "reason": "status-only", "rows": rows}))
        if mode == "queued-stack":
            raise RuntimeError("queued-stack requires status-only in the simple runner")
        if mode == "stack":
            emit(stamp({"kind": "STATUS", "terminal": False, "reason": "poll", "rows": rows}))
        decision = classify_pr(rows[0], options["allowDraft"]) if mode == "single" else select_tier_major_stack_decision(rows, options["allowDraft"])
        if decision["kind"] == "blocker":
            return _Terminal(_blocker_verdict(stamp, decision["blocker"]))
        if decision["kind"] in ("ready", "merged", "clear"):
            scope = {"kind": "stack", "prs": decision["prs"]} if decision["kind"] == "clear" else {"kind": "single", "pr": decision["pr"]}
            return _Terminal(stamp({"kind": "READY", "terminal": True, "exitCode": 0, "scope": scope}))
        emit(stamp({"kind": "WAITING", "terminal": False, "frontier": decision["frontier"],
                    "reason": {"kind": "pending-checks", "pending": decision["pending"]}}))
        return _Sleep(options["interval"], lambda: stamp({
            "kind": "TIMEOUT", "terminal": True, "exitCode": 5,
            "reason": {"kind": "pending-checks", "pending": decision["pending"]},
        }))

    return _poll_until_terminal(clock, emit, options, stamp, step)


@dataclass(frozen=True)
class _Sweep:
    remaining: tuple[PrContext, ...]


@dataclass(frozen=True)
class _FrontierPoll:
    frontier: PrContext


@dataclass(frozen=True)
class QueueState:
    queue: tuple[PrContext, ...]
    snapshots: tuple[dict, ...]
    work: _Sweep | _FrontierPoll | None
    next_sweep_at: float
    frontier: PrContext | None
    last_wait_key: str | None
    started_at: float


def create_queue_state(queue: Sequence[PrContext], now: float) -> QueueState:
    frozen = tuple(queue)
    return QueueState(frozen, (), _Sweep(frozen), now, None, None, now)


def _ordered_rows(state: QueueState) -> list[dict]:
    snapshots = {row["context"]["number"]: row for row in state.snapshots}
    return [snapshots[context["number"]] for context in state.queue if context["number"] in snapshots]


def _active_rows(state: QueueState) -> list[dict]:
    return [row for row in _ordered_rows(state) if row["kind"] != "merged"]


def plan_queue(state: QueueState, now: float) -> QueueState:
    if state.work is not None:
        return state
    if not state.snapshots or now >= state.next_sweep_at:
        snapshots = {row["context"]["number"]: row for row in state.snapshots}
        remaining = tuple(context for context in state.queue if snapshots.get(context["number"], {}).get("kind") != "merged")
        if remaining:
            return replace(state, work=_Sweep(remaining))
    active = _active_rows(state)
    return replace(state, work=_FrontierPoll(active[0]["context"])) if active else state


def apply_queue_snapshot(state: QueueState, snapshot: dict, now: float, options: dict) -> tuple[QueueState, list[dict] | None]:
    if state.work is None:
        raise RuntimeError("queue has no read in flight")
    snapshots = {row["context"]["number"]: row for row in state.snapshots}
    snapshots[snapshot["context"]["number"]] = snapshot
    base = replace(state, snapshots=tuple(snapshots.values()))
    if isinstance(state.work, _FrontierPoll):
        return replace(base, work=None), None
    head, *tail = state.work.remaining
    if head["number"] != snapshot["context"]["number"]:
        raise RuntimeError("snapshot does not match sweep head")
    if tail:
        return replace(base, work=_Sweep(tuple(tail))), None
    rows = _ordered_rows(base)
    if not rows or len(rows) != len(state.queue):
        raise RuntimeError("sweep completed without every snapshot")
    return replace(base, work=None, next_sweep_at=now + options["sweepInterval"]), rows


def evaluate_queue(state: QueueState, now: float, options: dict) -> dict:
    active = _active_rows(state)
    if not active:
        merged = [{"kind": "merged-pr", "context": row["context"], "mergedAt": row["facts"]["mergedAt"]}
                  for row in _ordered_rows(state) if row["kind"] == "merged"]
        if not merged:
            raise RuntimeError("empty queue cannot complete")
        return {"kind": "complete", "state": state, "merged": merged}
    decision = select_tier_major_stack_decision(active, options["allowDraft"])
    if decision["kind"] == "blocker":
        return {"kind": "blocker", "state": state, "blocker": decision["blocker"]}
    frontier = active[0]["context"]
    if state.frontier is not None and state.frontier["number"] != frontier["number"]:
        return {"kind": "advance", "state": replace(state, frontier=frontier, last_wait_key=None),
                "merged": state.frontier, "frontier": frontier, "remaining": len(active)}
    if _deadline_passed(state.started_at, options, now):
        return {"kind": "timeout", "state": replace(state, frontier=frontier), "frontier": frontier, "unmergedCount": len(active)}
    row = active[0]
    pending = row["ci"]["pending"] if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending" else None
    reason = {"kind": "merge-queue", "unmergedCount": len(active)} if pending is None else {"kind": "pending-checks", "pending": pending}
    key = f"queue:{_number_text(frontier['number'])}:{len(active)}" if pending is None else f"pending:{_number_text(frontier['number'])}:{len(pending)}"
    return {"kind": "waiting", "state": replace(state, frontier=frontier, last_wait_key=key),
            "frontier": frontier, "reason": reason, "emit": state.last_wait_key != key}


def run_queued(run: Run, clock: Clock, emit, contexts: Sequence[PrContext], options: dict) -> dict:
    state = create_queue_state(contexts, clock.now())
    stamp = verdict_factory(clock, "queued-stack")
    emit(stamp({"kind": "QUEUE", "terminal": False, "queue": list(contexts)}))

    def complete(merged):
        return _Terminal(stamp({"kind": "COMPLETE", "terminal": True, "exitCode": 0, "queue": list(state.queue), "merged": merged}))

    def step():
        nonlocal state
        state = plan_queue(state, clock.now())
        if state.work is None:
            evaluation = evaluate_queue(state, clock.now(), options)
            if evaluation["kind"] != "complete":
                raise RuntimeError("queue has no work while active")
            return complete(evaluation["merged"])
        context = state.work.remaining[0] if isinstance(state.work, _Sweep) else state.work.frontier
        snapshot = read_snapshot(run, context, "omit", options["allowDraft"])
        state, rows = apply_queue_snapshot(state, snapshot, clock.now(), options)
        if rows is not None:
            emit(stamp({"kind": "STATUS", "terminal": False, "reason": "whole-stack-sweep", "rows": rows}))
        if state.work is not None:
            return None
        evaluation = evaluate_queue(state, clock.now(), options)
        state = evaluation["state"]
        kind = evaluation["kind"]
        if kind == "complete":
            return complete(evaluation["merged"])
        if kind == "blocker":
            return _Terminal(_blocker_verdict(stamp, evaluation["blocker"]))
        if kind == "advance":
            emit(stamp({"kind": "ADVANCE", "terminal": False, "merged": evaluation["merged"],
                        "frontier": evaluation["frontier"], "remaining": evaluation["remaining"]}))
            return None
        if kind == "timeout":
            return _Terminal(stamp({"kind": "TIMEOUT", "terminal": True, "exitCode": 5,
                                    "reason": {"kind": "queued-stack", "frontier": evaluation["frontier"],
                                               "unmergedCount": evaluation["unmergedCount"]}}))
        if kind == "waiting":
            if evaluation["emit"]:
                emit(stamp({"kind": "WAITING", "terminal": False, "frontier": evaluation["frontier"], "reason": evaluation["reason"]}))
            return _Sleep(options["interval"])
        raise RuntimeError("unclassified queue evaluation")

    return _poll_until_terminal(clock, emit, options, stamp, step)


def render_json(verdict: dict) -> str:
    return _json(verdict) + "\n"


def _ci_cell(row: dict) -> str:
    if row["kind"] != "open":
        return "\u2014"
    ci = row["ci"]
    was = ", was ✅" if ci["hadPreviousPassingCi"] else ""
    if ci["kind"] == "ci-clean":
        return "✅"
    if ci["kind"] == "ci-pending":
        return f"⏳ {len(ci['pending'])} pending{was}"
    if ci["kind"] == "ci-failing":
        pending = f", {len(ci['pending'])} pending" if ci["pending"] else ""
        return f"❌ {len(ci['failed'])} failed{pending}{was}"
    return f"❌ GitHub reports failing checks{was}"


def _review_cell(row: dict) -> str:
    if row["kind"] != "open":
        return "\u2014"
    count = len(row["threads"])
    if row["reviewAutomationRunning"]:
        return f"🤖 running, {count} open" if count else "🤖 running"
    return f"📝 {count} open" if count else "✅"


def _merge_cell(row: dict) -> str:
    if row["kind"] == "merged":
        return "✅ merged"
    if row["kind"] == "closed":
        return "❌ closed"
    if row["facts"]["isDraft"]:
        return "⏸ draft"
    if row["facts"]["reviewDecision"] == "CHANGES_REQUESTED":
        return "⚠️ changes requested"
    return "⚠️ conflict" if _conflict_blocker(row) else "✅"


def render_status_table(rows: Sequence[dict]) -> str:
    lines = ["| PR | CI | Review | Merge |", "| --- | --- | --- | --- |"]
    for row in rows:
        context = row["context"]
        number = _number_text(context["number"])
        url = f"https://github.com/{context['owner']}/{context['repo']}/pull/{number}"
        lines.append(f"| [#{number}]({url}) | {_ci_cell(row)} | {_review_cell(row)} | {_merge_cell(row)} |")
    return "\n".join(lines) + "\n"


def _thread_line(thread: dict) -> str:
    comment = thread["firstComment"] or {}
    body = _utf16_slice(re.split(r"\r?\n", comment.get("body", ""), maxsplit=1)[0], 180)
    return " ".join((
        thread["id"], str(comment.get("path") if comment.get("path") is not None else "None"),
        _number_text(comment["line"]) if comment.get("line") is not None else "None",
        comment.get("authorLogin") if comment.get("authorLogin") is not None else "None",
        f"isBugBot={str(thread['isBugbot']).lower()}", f"bugbotReviewPasses={thread['bugbotReviewPasses']}", body,
    ))


def _render_blocker(blocker: dict) -> str:
    kind = blocker["kind"]
    if kind == "status-query":
        return "\n".join(("BLOCKER: status-query", f"failures={blocker['failures']}", f"detail={blocker['failure']['detail']}",
                          "action=verify current PR context, GitHub authentication, and API availability, then rearm"))
    number = _number_text(blocker["pr"]["number"])
    if kind == "merge-conflicts":
        return "\n".join(("BLOCKER: merge-conflicts", f"pr={number}", f"mergeable={blocker['facts']['mergeable']}",
                          f"mergeStateStatus={blocker['facts']['mergeStateStatus']}", "action=resolve merge conflicts before waiting for CI"))
    if kind == "review-threads":
        return "\n".join(("BLOCKER: review-threads", f"pr={number}", f"unresolved={len(blocker['threads'])}",
                          *(_thread_line(thread) for thread in blocker["threads"])))
    if kind == "failing-checks":
        ci = blocker["ci"]
        failed = ci["failed"] if ci["kind"] == "ci-failing" else []
        details = [f"{check['name']} {check['reportedState']} {check['description']} {check['link']}" for check in failed]
        if ci["kind"] == "ci-github-rejected":
            details += [f"mergeStateStatus={ci['github']['mergeStateStatus']}", f"headRollupState={ci['github']['headRollupState']}"]
        return "\n".join(("BLOCKER: failing-checks", f"pr={number}", f"failed={len(failed)}", *details))
    if kind == "merge-gate":
        action = {
            "closed-without-merge": "restore or remove the closed PR from the queued stack",
            "draft-pr": "mark the PR ready for review before waiting for the merge queue",
            "changes-requested": "resolve the changes-requested review before waiting for the merge queue",
        }[blocker["reason"]]
        return f"BLOCKER: {blocker['reason']}\npr={number}\naction={action}"
    raise RuntimeError("unclassified blocker")


def render_pretty(verdict: dict) -> str:
    kind = verdict["kind"]
    if kind == "QUEUE":
        queue = verdict["queue"]
        return f"QUEUE: captured {len(queue)} PR{'' if len(queue) == 1 else 's'} bottom-to-top: {','.join('#' + _number_text(pr['number']) for pr in queue)}\n"
    if kind == "STATUS":
        return render_status_table(verdict["rows"])
    if kind == "WAITING":
        number = _number_text(verdict["frontier"]["number"])
        reason = verdict["reason"]
        if reason["kind"] == "pending-checks":
            count = len(reason["pending"])
            return f"WAITING: frontier=#{number}; {count} check{'' if count == 1 else 's'} pending\n"
        count = reason["unmergedCount"]
        return f"WAITING: frontier=#{number} is blocker-free; waiting for merge queue ({count} PR{'' if count == 1 else 's'} unmerged)\n"
    if kind == "ADVANCE":
        return f"ADVANCE: merged #{_number_text(verdict['merged']['number'])}; next=#{_number_text(verdict['frontier']['number'])}; remaining={verdict['remaining']}\n"
    if kind == "RETRY":
        return f"RETRY: GitHub status query failed; retrying in {_number_text(verdict['retryInSeconds'])}s\ndetail={verdict['failure']['detail']}\n"
    if kind == "BLOCKER":
        return _render_blocker(verdict["blocker"]) + "\n"
    if kind == "READY":
        detail = ""
        scope = verdict["scope"]
        if scope["kind"] == "single" and scope["pr"]["kind"] == "ready-pr":
            proof = scope["pr"]["proof"]
            draft = proof["gate"]["draft"] == "draft-allowed"
            decision = proof["gate"]["reviewDecision"]
            detail = (f"\nmergeStateStatus={proof['ci']['github']['mergeStateStatus']}"
                      f"\nreviewDecision={'null' if decision is None else decision}\nisDraft={str(draft).lower()}")
            if draft:
                detail += "\nnote=draft allowed (--allow-draft); leave draft \u2014 do not mark ready"
        return "READY: no merge conflicts, no unresolved review threads, no failing or pending checks" + detail + "\n"
    if kind == "COMPLETE":
        count = len(verdict["queue"])
        return f"COMPLETE: queued stack merged ({count} PR{'' if count == 1 else 's'})\n"
    if kind == "TIMEOUT":
        reason = verdict["reason"]
        if reason["kind"] == "pending-checks":
            return "TIMEOUT: checks still pending\n"
        if reason["kind"] == "status-unavailable":
            return "TIMEOUT: GitHub status remained unavailable\n"
        count = reason["unmergedCount"]
        return f"TIMEOUT: queued stack still has {count} PR{'' if count == 1 else 's'} unmerged; frontier=#{_number_text(reason['frontier']['number'])}\n"
    raise RuntimeError("unclassified verdict")


class _UsageError(Exception):
    pass


class _Help(Exception):
    pass


def _numeric_option(value: str, option: str):
    parsed = _number(value[1:] if option == "--pr" and value.startswith("#") else value)
    if option == "--pr":
        try:
            return parse_pr_number(parsed)
        except ValueError as error:
            raise _UsageError(str(error)) from error
    if option == "--max-query-errors":
        valid = math.isfinite(parsed) and parsed > 0 and parsed == int(parsed)
        message = "must be a positive integer"
    elif option == "--timeout":
        valid = math.isfinite(parsed) and parsed >= 0
        message = "must be zero or greater"
    else:
        valid = math.isfinite(parsed) and parsed > 0
        message = "must be greater than zero"
    if not valid:
        raise _UsageError(f"{option} {message}")
    return parsed


def _help_text() -> str:
    parser = argparse.ArgumentParser(prog="watch_pr.py", formatter_class=argparse.RawDescriptionHelpFormatter, description=(
        "Watch one pull request, a connected stack, or an immutable queued stack.\n"
        "JSON (NDJSON while polling) is the default; --pretty renders human text."))
    for flag, help_text in (
        ("owner", "GitHub repository owner"), ("repo", "GitHub repository name"), ("pr", "pull request number"),
        ("stack-prs", "frozen bottom-to-top queue, queued mode only"),
        ("interval", "poll interval in seconds (default: 60)"),
        ("sweep-interval", "whole-stack sweep interval in seconds (default: 300)"),
        ("timeout", "deadline in seconds; 0 disables it (default: 0)"),
        ("max-query-errors", "consecutive query-error budget (default: 5)"),
    ):
        parser.add_argument("--" + flag, help=help_text)
    for flag, help_text in (
        ("stack", "watch the connected open stack"), ("queued-stack", "watch the captured stack until all PRs merge"),
        ("status-only", "print one status table and exit 0"), ("allow-draft", "do not treat a draft as a merge gate"),
        ("pretty", "render human text instead of JSON"),
    ):
        parser.add_argument("--" + flag, action="store_true", help=help_text)
    return parser.format_help()


def parse_args(argv: Sequence[str]) -> dict:
    values = {"--owner": None, "--repo": None, "--pr": None, "--stack-prs": [],
              "--interval": 60, "--sweep-interval": 300, "--timeout": 0, "--max-query-errors": 5}
    flags = {key: False for key in ("--stack", "--queued-stack", "--status-only", "--allow-draft", "--pretty")}
    unknown = []
    positionals = []
    index = 0
    # Commander consumes required values even when they look like another option.
    while index < len(argv):
        token = argv[index]
        index += 1
        name, sep, attached = token.partition("=")
        if name in values:
            if sep:
                value = attached
            elif index < len(argv):
                value = argv[index]
                index += 1
            else:
                raise _UsageError(f"{name} requires an argument")
            if name in ("--owner", "--repo"):
                values[name] = value
            elif name == "--stack-prs":
                numbers = [_numeric_option(part.strip(_JS_SPACE), "--pr") for part in value.split(",")]
                if len(set(numbers)) != len(numbers):
                    raise _UsageError("contains a duplicate PR")
                values[name] = numbers
            else:
                values[name] = _numeric_option(value, name)
        elif token in flags:
            flags[token] = True
        elif token in ("-h", "--help"):
            raise _Help()
        elif token == "--":
            positionals.extend(argv[index:])
            break
        elif token.startswith("-") and token != "-":
            unknown.append(token)
        else:
            positionals.append(token)
    if unknown:
        raise _UsageError(f"unrecognized option {unknown[0]}")
    if flags["--stack"] and flags["--queued-stack"]:
        raise _UsageError("--stack conflicts with --queued-stack")
    if positionals:
        raise _UsageError("no positional arguments are accepted")
    if values["--stack-prs"] and not flags["--queued-stack"]:
        raise _UsageError("--stack-prs requires --queued-stack")
    return {
        "owner": values["--owner"], "repo": values["--repo"], "pr": values["--pr"],
        "mode": "queued-stack" if flags["--queued-stack"] else "stack" if flags["--stack"] else "single",
        "stackPrs": values["--stack-prs"], "statusOnly": flags["--status-only"], "pretty": flags["--pretty"],
        "polling": {"interval": values["--interval"], "sweepInterval": values["--sweep-interval"],
                    "timeout": values["--timeout"], "maxQueryErrors": values["--max-query-errors"], "allowDraft": flags["--allow-draft"]},
    }


def _write(stream: TextIO, value: str) -> None:
    # Node's UTF-8 stream replaces a surrogate left by a UTF-16 pretty-text cut.
    stream.write(value.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace"))
    stream.flush()


def main(argv: Sequence[str], *, run: Run | None = None, clock: Clock | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    run = _run if run is None else run
    clock = _RealClock() if clock is None else clock
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        options = parse_args(argv)
    except _Help:
        _write(stdout, _help_text())
        return 0
    except _UsageError as error:
        _write(stderr, f"watch_pr.py: error: {error}\n")
        return 64
    render = render_pretty if options["pretty"] else render_json

    def emit(verdict):
        _write(stdout, render(verdict))

    try:
        seed_pr = options["pr"] if options["pr"] is not None else options["stackPrs"][0] if options["stackPrs"] else None
        seed = resolve_context(run, options["owner"], options["repo"], seed_pr)
        contexts = ([{**seed, "number": number} for number in options["stackPrs"]] if options["stackPrs"]
                    else [seed] if options["mode"] == "single" else discover_stack(run, seed))
    except WatcherQueryError as error:
        verdict = status_query_verdict(verdict_factory(clock, options["mode"]), 1, error.failure)
        emit(verdict)
        return verdict["exitCode"]
    if options["mode"] == "queued-stack" and not options["statusOnly"]:
        verdict = run_queued(run, clock, emit, contexts, options["polling"])
    else:
        verdict = run_simple(run, clock, emit, contexts, options["mode"], options["statusOnly"], options["polling"])
    emit(verdict)
    return verdict["exitCode"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Plain-file orchestration bookkeeping. Requires Python 3.11 or later."""

import argparse
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


_UNIT = ("id", "track", "state", "branch", "pr", "sha", "brief")
_LEDGER = ("pr", "sha", "verdict", "evidence", "verifier", "ts")
_POINTER = ("ts", "agent", "unit", "status", "report")
_VERDICTS = (
    "live-ui-verified", "unit-test-verified", "type-check-only",
    "verifier-blocked", "verifier-failed",
)
_SAFE = 9007199254740991
_SPACE = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_FORGES = {
    "gh": ("state", "headRefName", "baseRefName",
           {"OPEN": "OPEN", "MERGED": "MERGED", "CLOSED": "CLOSED"}),
    "origin": ("status", "headRef", "baseRef",
               {"open": "OPEN", "draft": "OPEN", "merged": "MERGED", "closed": "CLOSED"}),
}


class UserError(Exception):
    pass


class UsageError(UserError):
    pass


class NotFoundError(UserError):
    def __init__(self, message, output=None):
        super().__init__(message)
        self.output = output


class _ToolError(UserError):
    pass


def _trim(value):
    return value.strip(_SPACE)


def _utf16(value):
    return value.encode("utf-16-be", "surrogatepass")


def _utf8_text(value):
    return value.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json(value, *, pretty=False):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                     indent=2 if pretty else None,
                     separators=None if pretty else (",", ":"))
    return re.sub(r"[\ud800-\udfff]", lambda m: f"\\u{ord(m[0]):04x}", raw)


def _invalid_constant(value):
    raise ValueError(f"invalid JSON constant {value}")


def _load_json(raw):
    return json.loads(raw, parse_constant=_invalid_constant,
                      parse_int=lambda value: int(value) if len(value) < 17 else float(value))


def _safe_integer(value):
    return (type(value) in (int, float) and abs(value) <= _SAFE
            and value == int(value))


def _positive(value, label="PR"):
    if not _safe_integer(value) or value < 1:
        raise UserError(f"{label} must be a positive integer")
    return int(value)


def _pr(value):
    if not re.fullmatch(r"[1-9][0-9]*", value) or len(value) > 16 or int(value) > _SAFE:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return int(value)


def _pr_list(value):
    parts = value.split(",")
    if "" in parts:
        raise argparse.ArgumentTypeError("requires a comma-separated PR list")
    return [_pr(part) for part in parts]


def _verdict(value):
    if value not in _VERDICTS:
        raise UserError(f"verdict must be {', '.join(_VERDICTS[:-1])}, or {_VERDICTS[-1]}")
    return value


def _cell(value):
    cleaned = re.sub(r"[\t\n\r]", " ", value)
    return "'" + cleaned if re.match(r"[=+\-@]", cleaned) else cleaned


def _required_cell(value, label):
    cleaned = _cell(value)
    if not _trim(cleaned):
        raise UserError(f"{label} must not be empty")
    return cleaned


def _line(value, label):
    cleaned = _trim(re.sub(r"[\n\r]", " ", value))
    if not cleaned:
        raise UserError(f"{label} must not be empty")
    return cleaned


def _read(path):
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        return stream.read()


def _required_file(path):
    try:
        return _read(path)
    except FileNotFoundError:
        raise UserError(f"store is not initialized at {path.parent}; run orch init") from None


def _counts(values):
    """Keep the original plain-object counter's inherited-label behavior."""
    result = {}
    inherited = {
        "constructor": "Object", "__defineGetter__": "__defineGetter__",
        "__defineSetter__": "__defineSetter__", "hasOwnProperty": "hasOwnProperty",
        "__lookupGetter__": "__lookupGetter__", "__lookupSetter__": "__lookupSetter__",
        "isPrototypeOf": "isPrototypeOf", "propertyIsEnumerable": "propertyIsEnumerable",
        "toString": "toString", "valueOf": "valueOf", "toLocaleString": "toLocaleString",
    }
    for value in values:
        if value == "__proto__":
            continue
        if value not in result and value in inherited:
            result[value] = f"function {inherited[value]}() {{\n    [native code]\n}}1"
        elif isinstance(result.get(value), str):
            result[value] += "1"
        else:
            result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items(), key=lambda item: _utf16(item[0])))


def _count_line(value):
    return ", ".join(f"{key}={count}" for key, count in value.items()) or "none"


def _parse_frontier(raw):
    try:
        value = _load_json(raw)
    except ValueError:
        raise UserError("frontier.json is not valid JSON") from None
    if not isinstance(value, dict):
        raise UserError("frontier.json must contain an object")
    if not value:
        return {"generation": 0, "prs": [], "lowestUnmerged": None}
    if (not _safe_integer(value.get("generation")) or value["generation"] < 0
            or not isinstance(value.get("prs"), list)
            or "lowestUnmerged" not in value
            or not (value["lowestUnmerged"] is None or _safe_integer(value["lowestUnmerged"]))):
        raise UserError("frontier.json has an invalid shape")
    rows = []
    for row in value["prs"]:
        if (not isinstance(row, dict) or not _safe_integer(row.get("pr")) or row["pr"] < 1
                or not isinstance(row.get("branches"), str) or not row["branches"]
                or not isinstance(row.get("sha"), str)
                or row.get("state") not in ("OPEN", "MERGED", "CLOSED")):
            raise UserError("frontier.json has an invalid PR row")
        rows.append({**{key: row[key] for key in ("branches", "sha", "state")}, "pr": int(row["pr"])})
    lowest = value["lowestUnmerged"]
    return {"generation": int(value["generation"]), "prs": rows,
            "lowestUnmerged": None if lowest is None else int(lowest)}


def _previous_summary(raw):
    match = re.search(r"<!-- orch-summary ([^\r\n\u2028\u2029]+) -->", raw)
    if match is None:
        return None
    try:
        value = _load_json(match[1])
    except ValueError:
        return None
    if (not isinstance(value, dict) or type(value.get("frontierGeneration")) not in (int, float)
            or not isinstance(value.get("openGateIds"), list)):
        return None
    for key in ("unitStates", "ledgerVerdicts"):
        counts = value.get(key)
        if not isinstance(counts, dict) or any(
                not _safe_integer(count) or count < 0 for count in counts.values()):
            return None
    if not all(isinstance(item, str) for item in value["openGateIds"]):
        return None
    return value


def _changed(before, after):
    if before is None:
        return "first render"
    result = []
    for label, key in (("units", "unitStates"), ("ledger", "ledgerVerdicts")):
        for name in sorted(before[key].keys() | after[key].keys(), key=_utf16):
            old, new = before[key].get(name, 0), after[key].get(name, 0)
            if old != new:
                result.append(f"{label} {name} {old}->{new}")
    if before["frontierGeneration"] != after["frontierGeneration"]:
        result.append(f"frontier generation {before['frontierGeneration']}->{after['frontierGeneration']}")
    if "\0".join(before["openGateIds"]) != "\0".join(after["openGateIds"]):
        result.append(f"open gates {len(before['openGateIds'])}->{len(after['openGateIds'])}")
    return "; ".join(result) or "no derived changes"


def _table(headers, rows):
    if not rows:
        return "(none)"
    def markdown(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|")
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(markdown(cell) for cell in row) + " |" for row in rows),
    ])


def _status_markdown(units, ledger, frontier, gates, summary):
    unit_table = _table(["ID", "Track", "State", "Branch", "PR", "SHA", "Brief"],
                        [[row[key] for key in _UNIT] for row in units])
    ledger_table = _table(["PR", "SHA", "Verdict", "Evidence", "Verifier", "Timestamp"],
                          [[row[key] for key in _LEDGER] for row in ledger])
    frontier_table = _table(["Branch", "PR", "SHA", "State"],
                            [[row["branches"], row["pr"], row["sha"], row["state"]] for row in frontier["prs"]])
    gates_table = _table(["ID", "Status", "Question", "Options", "Default", "Answer"],
                         [[row["id"], row["kind"], row["question"], row["options"],
                           row["defaultAnswer"], row.get("answer", "")] for row in gates])
    lowest = frontier["lowestUnmerged"]
    return (
        f"# Orchestrate status\n\nGenerated: {_now()}\n\n## Units\n\n"
        f"States: {_count_line(summary['unitStates'])}\n\n{unit_table}\n\n"
        f"## Verification ledger\n\nVerdicts: {_count_line(summary['ledgerVerdicts'])}\n\n{ledger_table}\n\n"
        f"## Frontier\n\nGeneration: {frontier['generation']}\n"
        f"Lowest unmerged: {lowest if lowest is not None else 'none'}\n\n{frontier_table}\n\n"
        f"## Gates\n\n{gates_table}\n\n<!-- orch-summary {_json(summary)} -->\n"
    )


def _tool(command, args, repo):
    try:
        result = subprocess.run([command, *args], cwd=repo, stdin=subprocess.DEVNULL,
                                capture_output=True, check=True)
        return result.stdout.decode("utf-8", "replace")
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", "replace").strip() or str(error)
        raise _ToolError(f"{command} {' '.join(args)} failed: {detail}") from None


def _git(args, repo):
    return _trim(_tool("git", args, repo))


def _pull_requests(filter, branch, forge, repo):
    state_key, head_key, base_key, states = _FORGES[forge]
    command = f"{forge} pr list {filter} {branch}"
    raw = _tool(forge, ["pr", "list", filter, branch, "--state", "all", "--json",
                        ",".join(("number", state_key, head_key, base_key))], repo)
    try:
        value = _load_json(raw)
    except ValueError:
        raise UserError(f"{command} output is not valid JSON") from None
    if not isinstance(value, list):
        raise UserError(f"{command} output is not a JSON array")
    result = []
    for row in value:
        if (not isinstance(row, dict) or not _safe_integer(row.get("number")) or row["number"] < 1
                or not isinstance(row.get(state_key), str) or row[state_key] not in states
                or not isinstance(row.get(head_key), str) or not row[head_key]
                or not isinstance(row.get(base_key), str) or not row[base_key]):
            raise UserError(f"{command} output has an invalid PR row")
        result.append({"pr": int(row["number"]), "state": states[row[state_key]],
                       "branch": row[head_key], "base": row[base_key]})
    return result


def _branch_pr(branch, forge, repo):
    rows = _pull_requests("--head", branch, forge, repo)
    if not rows:
        raise UserError(
            f"branch {branch} has no pull request; open one with {forge} pr create, "
            "or resolve the frontier from a branch whose chain is fully submitted"
        )
    if len(rows) > 1:
        numbers = ", ".join(f"#{row['pr']}" for row in rows)
        raise UserError(f"branch {branch} has multiple pull requests ({numbers}); close the stale ones first")
    return rows[0]


def _resolve_frontier(repo, forge):
    try:
        trunk = re.sub(r"^origin/", "", _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo))
    except _ToolError:
        trunk = "main"
    current = _git(["symbolic-ref", "--short", "HEAD"], repo)
    if current == trunk:
        return []
    seen = {current}
    bottom = _branch_pr(current, forge, repo)
    chain = [bottom]
    while bottom["base"] != trunk:
        if bottom["base"] in seen:
            raise UserError(f"pull request base chain loops at branch {bottom['base']}")
        seen.add(bottom["base"])
        bottom = _branch_pr(bottom["base"], forge, repo)
        chain.insert(0, bottom)
    tip = current
    while True:
        children = [row for row in _pull_requests("--base", tip, forge, repo) if row["state"] == "OPEN"]
        if not children:
            break
        if len(children) > 1:
            branches = ", ".join(row["branch"] for row in children)
            raise UserError(f"stack is not linear: branches {branches} all target {tip}")
        child = children[0]
        if child["branch"] in seen:
            raise UserError(f"pull request base chain loops at branch {child['branch']}")
        seen.add(child["branch"])
        chain.append(child)
        tip = child["branch"]
    if len({row["pr"] for row in chain}) != len(chain):
        raise UserError("pull request base chain contains duplicate pull requests")
    result = []
    for row in chain:
        sha = _git(["rev-parse", row["branch"]], repo)
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            raise UserError(f"git rev-parse {row['branch']} returned an invalid SHA")
        result.append({"pr": row["pr"], "branches": row["branch"], "sha": sha, "state": row["state"]})
    return result


def _validate_pin(actual, expected):
    if actual == expected:
        return
    missing = [pr for pr in expected if pr not in actual]
    extra = [pr for pr in actual if pr not in expected]
    drift = []
    if missing:
        drift.append("missing from resolved chain: " + ",".join(map(str, missing)))
    if extra:
        drift.append("extra in resolved chain: " + ",".join(map(str, extra)))
    if not missing and not extra:
        drift.append(f"order differs: expected {','.join(map(str, expected))}; resolved {','.join(map(str, actual))}")
    raise UserError("frontier pin mismatch: " + "; ".join(drift))


def _require_supported_platform():
    if sys.platform not in ("linux", "darwin"):
        raise UserError("orch supports Linux and macOS only")


class _Store:
    def __init__(self, path, *, force=False, on_lock_stolen=None, on_stale_lock=None):
        self.path = Path(os.path.abspath(path))
        self.force = force
        self.on_lock_stolen = on_lock_stolen
        self.on_stale_lock = on_stale_lock
        self._closed = False
        self._locked = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _ensure_open(self):
        if self._closed:
            raise UserError("store is closed")

    def _lock(self):
        self._ensure_open()
        _require_supported_platform()
        if self._locked:
            return
        path = self.path / ".orch.lock"
        def create():
            with path.open("x", encoding="utf-8", newline="") as stream:
                stream.write(f"{os.getpid()}\n")
        try:
            create()
        except FileExistsError:
            try:
                holder = _trim(_read(path)) or "unknown"
            except OSError:
                holder = "unknown"
            dead = False
            if re.fullmatch(r"[1-9][0-9]*", holder) and len(holder) <= 16 and int(holder) <= _SAFE:
                try:
                    os.kill(int(holder), 0)
                except OSError as error:
                    dead = error.errno == errno.ESRCH
                except OverflowError:
                    dead = False
            if dead:
                if self.on_stale_lock:
                    self.on_stale_lock(holder)
            elif self.force:
                if self.on_lock_stolen:
                    self.on_lock_stolen(holder)
            else:
                raise UserError(f"store lock held by pid {holder}") from None
            path.unlink()
            try:
                create()
            except FileExistsError:
                retry_holder = _trim(_read(path)) or "unknown"
                raise UserError(f"store lock held by pid {retry_holder}") from None
        self._locked = True

    def _begin_write(self):
        self._ensure_open()
        if not self.path.exists():
            raise UserError(f"store is not initialized at {self.path}; run orch init")
        self._lock()

    def _atomic_write(self, path, contents):
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4()}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="") as stream:
                stream.write(_utf8_text(contents))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_tsv(self, filename, columns):
        lines = _required_file(self.path / filename).replace("\r", "").split("\n")
        if lines.pop(0) != "\t".join(columns):
            raise UserError(f"{filename} has an invalid header")
        rows = []
        for line in filter(None, lines):
            cells = line.split("\t")
            if len(cells) != len(columns):
                raise UserError(f"{filename} has a malformed row")
            rows.append(dict(zip(columns, cells)))
        return rows

    def _write_tsv(self, filename, columns, rows):
        body = "\n".join("\t".join(_cell(row[key]) for key in columns) for row in rows)
        self._atomic_write(self.path / filename, "\t".join(columns) + "\n" + body + ("\n" if body else ""))

    def _read_ledger(self):
        rows = self._read_tsv("ledger.tsv", _LEDGER)
        for row in rows:
            if row["verdict"] not in _VERDICTS:
                raise UserError(f"ledger.tsv has invalid verdict {row['verdict']}")
        return rows

    def init(self):
        self._ensure_open()
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock()
        for name, columns in (("units.tsv", _UNIT), ("ledger.tsv", _LEDGER)):
            if not (self.path / name).exists():
                self._atomic_write(self.path / name, "\t".join(columns) + "\n")
        (self.path / "inbox").mkdir(exist_ok=True)
        for name, contents in (("gates.md", ""), ("preferences.md", ""), ("frontier.json", "{}\n")):
            if not (self.path / name).exists():
                self._atomic_write(self.path / name, contents)
        return {"store": str(self.path)}

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._locked:
            self._locked = False
            path = self.path / ".orch.lock"
            try:
                if _trim(_read(path)) == str(os.getpid()):
                    path.unlink()
            except FileNotFoundError:
                pass

    def unit_add(self, id, track, brief=None):
        self._begin_write()
        row = dict(zip(_UNIT, (_required_cell(id, "unit id"), _required_cell(track, "track"),
                               "pending", "", "", "", "" if brief is None else _required_cell(brief, "brief"))))
        rows = self._read_tsv("units.tsv", _UNIT)
        if any(old["id"] == row["id"] for old in rows):
            raise UserError(f"unit {row['id']} already exists")
        rows.append(row)
        self._write_tsv("units.tsv", _UNIT, rows)
        return row

    def unit_set(self, id, state, branch=None, pr=None, sha=None):
        self._begin_write()
        id, state = _required_cell(id, "unit id"), _required_cell(state, "state")
        rows = self._read_tsv("units.tsv", _UNIT)
        for index, old in enumerate(rows):
            if old["id"] == id:
                row = {**old, "state": state,
                       "branch": old["branch"] if branch is None else _required_cell(branch, "branch"),
                       "pr": old["pr"] if pr is None else str(_positive(pr)),
                       "sha": old["sha"] if sha is None else _required_cell(sha, "SHA")}
                rows[index] = row
                self._write_tsv("units.tsv", _UNIT, rows)
                return row
        raise NotFoundError(f"unit {id} not found")

    def unit_get(self, id):
        self._ensure_open()
        id = _required_cell(id, "unit id")
        for row in self._read_tsv("units.tsv", _UNIT):
            if row["id"] == id:
                return row
        raise NotFoundError(f"unit {id} not found")

    def unit_list(self, state=None, track=None):
        self._ensure_open()
        state = None if state is None else _required_cell(state, "state")
        track = None if track is None else _required_cell(track, "track")
        return [row for row in self._read_tsv("units.tsv", _UNIT)
                if (state is None or row["state"] == state) and (track is None or row["track"] == track)]

    def unit_counts(self):
        self._ensure_open()
        return _counts(row["state"] for row in self._read_tsv("units.tsv", _UNIT))

    def ledger_record(self, pr, sha, verdict, evidence, verifier=None):
        self._begin_write()
        verdict = _verdict(verdict)
        row = dict(zip(_LEDGER, (str(_positive(pr)), _required_cell(sha, "SHA"), verdict,
                                 _required_cell(evidence, "evidence"),
                                 "" if verifier is None else _required_cell(verifier, "verifier"), _now())))
        rows = self._read_ledger()
        for index, old in enumerate(rows):
            if (old["pr"], old["sha"]) == (row["pr"], row["sha"]):
                rows[index] = row
                break
        else:
            rows.append(row)
        self._write_tsv("ledger.tsv", _LEDGER, rows)
        return row

    def ledger_check(self, pr, sha):
        self._ensure_open()
        pr, sha = str(_positive(pr)), _required_cell(sha, "SHA")
        for row in self._read_ledger():
            if (row["pr"], row["sha"]) == (pr, sha):
                return row
        raise NotFoundError("NOT-VERIFIED", {"compact": "NOT-VERIFIED",
                                           "json": {"pr": pr, "sha": sha, "verdict": "NOT-VERIFIED"}})

    def ledger_summary(self):
        self._ensure_open()
        return _counts(row["verdict"] for row in self._read_ledger())

    def _read_pointers(self):
        inbox = self.path / "inbox"
        try:
            files = sorted((entry for entry in inbox.iterdir()
                            if not entry.is_symlink() and entry.is_file() and entry.name.endswith(".tsv")),
                           key=lambda path: _utf16(path.name))
        except FileNotFoundError:
            raise UserError(f"store is not initialized at {self.path}; run orch init") from None
        rows = []
        for path in files:
            raw = re.sub(r"\r?\n$", "", _read(path), count=1)
            cells = raw.split("\t")
            if "\r" in raw or "\n" in raw or len(cells) != 5:
                raise UserError(f"inbox pointer {path.name} is malformed")
            rows.append(dict(zip(_POINTER, cells)))
        return rows

    def inbox_push(self, agent, unit, status, report=None):
        self._begin_write()
        pointer = dict(zip(_POINTER, (_now(), _required_cell(agent, "agent"),
                                      _required_cell(unit, "unit"), _required_cell(status, "status"),
                                      "" if report is None else _required_cell(report, "report"))))
        inbox = self.path / "inbox"
        if not inbox.exists():
            raise UserError(f"store is not initialized at {self.path}; run orch init")
        timestamp = re.sub(r"[:.]", "-", pointer["ts"])
        filename = f"{timestamp}-{os.getpid()}-{uuid.uuid4()}.tsv"
        self._atomic_write(inbox / filename, "\t".join(_cell(pointer[key]) for key in _POINTER) + "\n")
        return {"pointer": pointer, "filename": filename}

    def inbox_drain(self, *, peek=False):
        if peek:
            self._ensure_open()
            return self._read_pointers()
        self._begin_write()
        rows = self._read_pointers()
        inbox = self.path / "inbox"
        drained = self.path / f".inbox-drain-{os.getpid()}-{uuid.uuid4()}"
        inbox.rename(drained)
        try:
            inbox.mkdir()
        except OSError:
            drained.rename(inbox)
            raise
        try:
            shutil.rmtree(drained)
        except FileNotFoundError:
            pass
        return rows

    def inbox_count(self):
        self._ensure_open()
        return len(self._read_pointers())

    def _read_gates(self):
        raw = _trim(_required_file(self.path / "gates.md").replace("\r", ""))
        if not raw:
            return []
        prefix = "# Gates\n\n## "
        if not raw.startswith(prefix):
            raise UserError("gates.md has an invalid heading")
        result = []
        for block in raw[len(prefix):].split("\n\n## "):
            lines = list(filter(None, block.split("\n")))
            id = lines.pop(0) if lines else ""
            fields = {}
            for line in lines:
                match = re.fullmatch(r"- ([^:]+): ([^\r\n\u2028\u2029]*)", line)
                if match is None:
                    raise UserError(f"gates.md has a malformed gate {id}")
                fields[match[1]] = match[2]
            if not id or not all(key in fields for key in ("Question", "Options", "Default")):
                raise UserError(f"gates.md has a malformed gate {id}")
            status = fields.get("Status", "")
            gate = {"kind": status, "id": id, "question": fields["Question"],
                    "options": fields["Options"], "defaultAnswer": fields["Default"]}
            if status == "resolved" and "Answer" in fields:
                gate["answer"] = fields["Answer"]
            elif status != "open":
                raise UserError(f"gates.md has invalid status {status}")
            result.append(gate)
        if len({row["id"] for row in result}) != len(result):
            raise UserError("gates.md has duplicate gate ids")
        return result

    def _write_gates(self, rows):
        blocks = []
        for gate in rows:
            answer = f"\n- Answer: {gate['answer']}" if gate["kind"] == "resolved" else ""
            blocks.append(f"## {gate['id']}\n\n- Status: {gate['kind']}\n- Question: {gate['question']}\n"
                          f"- Options: {gate['options']}\n- Default: {gate['defaultAnswer']}{answer}")
        self._atomic_write(self.path / "gates.md", "# Gates\n\n" + "\n\n".join(blocks) + "\n" if blocks else "")

    def gate_park(self, id, question, options, default):
        self._begin_write()
        gate = {"kind": "open", "id": _line(id, "gate id"), "question": _line(question, "question"),
                "options": _line(options, "options"), "defaultAnswer": _line(default, "default")}
        rows = self._read_gates()
        for index, old in enumerate(rows):
            if old["id"] == gate["id"]:
                rows[index] = gate
                break
        else:
            rows.append(gate)
        self._write_gates(rows)
        return gate

    def gate_list(self):
        self._ensure_open()
        return [gate for gate in self._read_gates() if gate["kind"] == "open"]

    def gate_resolve(self, id, answer):
        self._begin_write()
        id = _line(id, "gate id")
        rows = self._read_gates()
        for index, old in enumerate(rows):
            if old["id"] == id:
                gate = {**old, "kind": "resolved", "answer": _line(answer, "answer")}
                rows[index] = gate
                self._write_gates(rows)
                return gate
        raise NotFoundError(f"gate {id} not found")

    def frontier_set(self, repo, forge="gh", pins=None):
        self._begin_write()
        repo = Path(os.path.abspath(_line(str(repo), "repo directory")))
        if forge not in _FORGES:
            raise UserError("forge must be gh or origin")
        if pins is not None:
            pins = [_positive(pr) for pr in pins]
            if len(set(pins)) != len(pins):
                raise UserError("--prs must not contain duplicates")
        old = self.frontier_show()
        prs = _resolve_frontier(repo, forge)
        if pins is not None:
            _validate_pin([row["pr"] for row in prs], pins)
        value = {"generation": old["generation"] + 1, "prs": prs,
                 "lowestUnmerged": next((row["pr"] for row in prs if row["state"] == "OPEN"), None)}
        self._atomic_write(self.path / "frontier.json", _json(value, pretty=True) + "\n")
        return value

    def frontier_show(self):
        self._ensure_open()
        return _parse_frontier(_required_file(self.path / "frontier.json"))

    def standing_show(self):
        self._ensure_open()
        raw = _required_file(self.path / "preferences.md").replace("\r", "")
        if not _trim(raw):
            return []
        result = []
        for value in filter(None, raw.split("\n")):
            match = re.fullmatch(r"([1-9][0-9]*)\. ([^\r\n\u2028\u2029]+)", value)
            if match is None or match[1] != str(len(result) + 1):
                raise UserError("preferences.md has malformed numbering")
            result.append({"number": len(result) + 1, "line": match[2]})
        return result

    def standing_add(self, line):
        self._begin_write()
        rows = self.standing_show()
        item = {"number": len(rows) + 1, "line": _line(line, "standing order")}
        rows.append(item)
        self._atomic_write(self.path / "preferences.md", "".join(f"{row['number']}. {row['line']}\n" for row in rows))
        return item

    def status(self):
        self._begin_write()
        units, ledger = self._read_tsv("units.tsv", _UNIT), self._read_ledger()
        frontier, gates = self.frontier_show(), self._read_gates()
        summary = {"unitStates": _counts(row["state"] for row in units),
                   "ledgerVerdicts": _counts(row["verdict"] for row in ledger),
                   "frontierGeneration": frontier["generation"],
                   "openGateIds": sorted((row["id"] for row in gates if row["kind"] == "open"), key=_utf16)}
        path = self.path / "status.md"
        before = _previous_summary(_read(path)) if path.exists() else None
        change = _changed(before, summary)
        self._atomic_write(path, _status_markdown(units, ledger, frontier, gates, summary))
        return {"units": units, "ledger": ledger, "frontier": frontier, "gates": gates,
                "summary": summary, "changed": change}


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._negative_number_matcher = re.compile(r"^-[0-9]*\.?[0-9]+(e[+-]?[0-9]+)?$")

    def _get_option_tuples(self, option_string):
        if option_string.startswith("-") and not option_string.startswith("--"):
            return []
        return super()._get_option_tuples(option_string)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parser():
    parser = _Parser(prog="orch", description="Plain-file orchestrate bookkeeping", allow_abbrev=False)
    parser.add_argument("--store", metavar="<dir>", help="store directory (or ORCH_STORE)")
    parser.add_argument("--json", action="store_true", help="print complete rows as JSON")
    parser.add_argument("--force", action="store_true", help="steal an existing store lock")
    commands = parser.add_subparsers(dest="command")
    leaves = {}
    groups = {}
    def leaf(parent, name, description):
        return parent.add_parser(name, description=description, help=description, allow_abbrev=False)
    for name in ("unit", "ledger", "inbox", "gate", "frontier", "standing"):
        group = leaf(commands, name, f"manage {name}")
        groups[name] = group
        sub = group.add_subparsers(dest="action")
        actions = {
            "unit": ("add", "set", "get", "list", "counts"),
            "ledger": ("record", "check", "summary"), "inbox": ("push", "drain", "count"),
            "gate": ("park", "list", "resolve"), "frontier": ("set", "show"),
            "standing": ("show", "add"),
        }[name]
        for action in actions:
            leaves[name, action] = leaf(sub, action, f"{action} {name}")
    leaves["init", None] = leaf(commands, "init", "initialize the store")
    leaves["status", None] = leaf(commands, "status", "render status.md and print a summary")
    def positional(command, action, *names):
        for name in names:
            leaves[command, action].add_argument(name, type=_pr if name == "pr" else str)
    def option(command, action, name, *, required=False, type=str, metavar=None):
        leaves[command, action].add_argument("--" + name, required=required, type=type, metavar=metavar)
    for action in ("add", "set", "get"):
        positional("unit", action, "id")
    option("unit", "add", "track", required=True)
    option("unit", "add", "brief")
    option("unit", "set", "state", required=True)
    for name in ("branch", "pr", "sha"):
        option("unit", "set", name, type=_pr if name == "pr" else str)
    for name in ("state", "track"):
        option("unit", "list", name)
    positional("ledger", "record", "pr", "sha", "verdict")
    positional("ledger", "check", "pr", "sha")
    option("ledger", "record", "evidence", required=True)
    option("ledger", "record", "verifier")
    positional("inbox", "push", "agent", "unit", "status")
    option("inbox", "push", "report")
    leaves["inbox", "drain"].add_argument("--peek", action="store_true")
    positional("gate", "park", "id")
    for name in ("question", "options", "default"):
        option("gate", "park", name, required=True)
    positional("gate", "resolve", "id")
    option("gate", "resolve", "answer", required=True)
    option("frontier", "set", "repo", metavar="<dir>")
    leaves["frontier", "set"].add_argument("--forge", choices=("gh", "origin"), default="gh", metavar="<forge>")
    option("frontier", "set", "prs", type=_pr_list, metavar="<n,...>")
    positional("standing", "add", "line")
    return parser, groups, leaves


def _arguments(argv, parser, groups, leaves):
    # Commander scans ancestor options before leaf options, even after operands.
    globals = {"store": os.environ.get("ORCH_STORE"), "json": False, "force": False}
    def scan(tokens):
        result = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                result.extend(tokens[index:])
                break
            if token in ("--json", "--force"):
                globals[token[2:]] = True
            elif token == "--store":
                index += 1
                if index == len(tokens):
                    parser.error("argument --store: expected one argument")
                globals["store"] = tokens[index]
            elif token.startswith("--store="):
                globals["store"] = token.partition("=")[2]
            else:
                result.append(token)
            index += 1
        return result
    tokens = list(argv)
    if tokens and tokens[0] == "--":
        tokens.pop(0)
    tokens = scan(tokens)
    selected = parser
    prefix = []
    literal = False
    if tokens and tokens[0] == "--":
        tokens.pop(0)
        literal = True
    if tokens and tokens[0] in groups:
        command = tokens.pop(0)
        prefix.append(command)
        selected = groups[command]
        tokens = tokens if literal else scan(tokens)
        if tokens and tokens[0] == "--":
            tokens.pop(0)
            literal = True
        if tokens and (command, tokens[0]) in leaves:
            action = tokens.pop(0)
            prefix.append(action)
            selected = leaves[command, action]
            tokens = tokens if literal else scan(tokens)
    elif tokens and (tokens[0], None) in leaves:
        command = tokens.pop(0)
        prefix.append(command)
        selected = leaves[command, None]
        tokens = tokens if literal else scan(tokens)
    if literal:
        tokens.insert(0, "--")
    converted = []
    index = 0
    options = selected._option_string_actions
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            converted.extend(tokens[index:])
            break
        option = options.get(token)
        if option is not None and option.nargs != 0:
            index += 1
            if index == len(tokens):
                selected.error(f"argument {token}: expected one argument")
            converted.append(token + "=" + tokens[index])
        else:
            converted.append(token)
        index += 1
    before_literal = converted[:converted.index("--")] if "--" in converted else converted
    if not any(token in ("-h", "--help") for token in before_literal):
        for token in before_literal:
            if (len(token) > 1 and token.startswith("-")
                    and token.partition("=")[0] not in options
                    and not selected._negative_number_matcher.fullmatch(token)):
                selected.error(f"unrecognized arguments: {token}")
    # Parse the selected command directly so global values cannot reset defaults.
    args = selected.parse_args(converted)
    args.command = prefix[0] if prefix else None
    args.action = prefix[1] if len(prefix) > 1 else None
    for key, value in globals.items():
        setattr(args, key, value)
    if args.command == "frontier" and args.action == "set" and args.repo is None:
        args.repo = os.environ.get("ORCH_REPO")
    return args


def _rows(rows, columns, empty, *, limit=4):
    if not rows:
        return empty
    visible = rows if limit is None else rows[:limit]
    lines = ["\t".join(row[key] for key in columns) for row in visible]
    if limit is not None and len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more; use --json")
    return "\n".join(lines)


def _frontier_line(value):
    prs = ",".join(f"{row['branches']}#{row['pr']}@{row['sha']}:{row['state']}" for row in value["prs"]) or "none"
    lowest = value["lowestUnmerged"]
    return f"generation={value['generation']} prs={prs} lowest-unmerged={lowest if lowest is not None else 'none'}"


def _status_lines(report):
    summary = report["summary"]
    ids = summary["openGateIds"]
    suffix = f"; ids={','.join(ids[:4])}" if ids else ""
    if len(ids) > 4:
        suffix += f",+{len(ids) - 4} more"
    return (f"counts: units={len(report['units'])}; states={_count_line(summary['unitStates'])}; "
            f"ledger={_count_line(summary['ledgerVerdicts'])}\nchanged: {report['changed']}\n"
            f"gates open: {len(ids)}{suffix}")


def _emit(value, compact, json_output):
    rendered = _json(value, pretty=True) if json_output else compact
    rendered = _utf8_text(rendered)
    sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")


def main(argv=None):
    parser, groups, leaves = _parser()
    json_output = False
    try:
        _require_supported_platform()
        args = _arguments(sys.argv[1:] if argv is None else argv, parser, groups, leaves)
        json_output = args.json
        if args.store is None or not _trim(args.store):
            raise UsageError("set --store <dir> or ORCH_STORE")
        if args.command is None or (args.command in groups and args.action is None):
            raise UsageError("a valid command is required")
        with _Store(
            args.store, force=args.force,
            on_lock_stolen=lambda holder: sys.stderr.write(f"stealing store lock held by pid {holder}\n"),
            on_stale_lock=lambda holder: sys.stderr.write(f"replacing stale store lock (pid {holder} is dead)\n"),
        ) as store:
            command, action = args.command, args.action
            if command == "init":
                value = store.init()
                compact = f"initialized {value['store']}"
            elif command == "unit":
                if action == "add":
                    value = store.unit_add(args.id, args.track, args.brief)
                elif action == "set":
                    value = store.unit_set(args.id, args.state, args.branch, args.pr, args.sha)
                elif action == "get":
                    value = store.unit_get(args.id)
                elif action == "list":
                    value = store.unit_list(args.state, args.track)
                else:
                    value = store.unit_counts()
                compact = (_count_line(value) if action == "counts" else
                           _rows(value if action == "list" else [value], _UNIT, "(no units)"))
            elif command == "ledger":
                if action == "record":
                    value = store.ledger_record(args.pr, args.sha, args.verdict, args.evidence, args.verifier)
                    compact = "\t".join(value[key] for key in ("pr", "sha", "verdict"))
                elif action == "check":
                    value = store.ledger_check(args.pr, args.sha)
                    compact = value["verdict"]
                else:
                    value = store.ledger_summary()
                    compact = _count_line(value)
            elif command == "inbox":
                if action == "push":
                    result = store.inbox_push(args.agent, args.unit, args.status, args.report)
                    value = result["pointer"]
                    compact = f"{value['unit']}\t{value['status']}\t{result['filename']}"
                elif action == "drain":
                    value = store.inbox_drain(peek=args.peek)
                    compact = _rows(value, _POINTER, "(empty)", limit=None)
                else:
                    count = store.inbox_count()
                    value, compact = {"count": count}, str(count)
            elif command == "gate":
                if action == "park":
                    value = store.gate_park(args.id, args.question, args.options, args.default)
                    compact = f"{value['id']}\topen"
                elif action == "resolve":
                    value = store.gate_resolve(args.id, args.answer)
                    compact = f"{value['id']}\tresolved\t{value['answer']}"
                else:
                    value = store.gate_list()
                    compact = _rows(value, ("id", "question", "options", "defaultAnswer"), "(no open gates)")
            elif command == "frontier":
                if action == "set":
                    if args.repo is None or not _trim(args.repo):
                        raise UsageError("set --repo <dir> or ORCH_REPO")
                    value = store.frontier_set(args.repo, args.forge, args.prs)
                else:
                    value = store.frontier_show()
                compact = _frontier_line(value)
            elif command == "standing":
                if action == "add":
                    value = store.standing_add(args.line)
                    compact = f"{value['number']}. {value['line']}"
                else:
                    value = store.standing_show()
                    compact = "\n".join(f"{row['number']}. {row['line']}" for row in value[:4]) or "(no standing orders)"
                    if len(value) > 4:
                        compact += f"\n... {len(value) - 4} more; use --json"
            else:
                value = store.status()
                compact = _status_lines(value)
            _emit(value, compact, json_output)
        return 0
    except NotFoundError as error:
        if error.output is None:
            sys.stderr.write(f"error: {error}\n")
        else:
            _emit(error.output["json"], error.output["compact"], json_output)
        return 2
    except (UserError, OSError, UnicodeError) as error:
        sys.stderr.write(f"error: {error}\n")
        if isinstance(error, UsageError):
            parser.print_help(sys.stderr)
        return 1
    except SystemExit as error:
        return error.code


if __name__ == "__main__":
    sys.exit(main())

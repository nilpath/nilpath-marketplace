#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from typing import Sequence


RULE = "Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked."
LANES = re.compile(r"Ten lanes on `[^`<>]+` at the PR head")
SUB_BLOCKS = [
    "Depends on.", "Files.", "Build.", "You see.", "Verify, unit.",
    "Verify, live.", "Verify, perf.", "Review gate.", "Merge.",
]
PROGRAM_H3 = ["Arm the program", "Spawn owners", "PR mechanics", "Verdict and merge", "Boot recipe"]
PROGRAM_MARKERS = [
    "git show origin/main:",
    "native recurring automation every 1h",
    "status message",
]
HOW_TO_READ_MARKERS = [
    "One box is one unit of work", "names the evidence",
    "Check a box only when its evidence exists", "playbooks/", RULE,
]
PERF_ITEMS = ["Metric.", "Probe.", "Baseline.", "Rule."]
JS_SPACE_CLASS = "\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
JS_TRIM_CHARS = "".join(
    chr(codepoint)
    for codepoint in (
        *range(0x0009, 0x000E), 0x0020, 0x00A0, 0x1680,
        *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F,
        0x205F, 0x3000, 0xFEFF,
    )
)
JS_LINE_TERMINATORS = "\r\n\u2028\u2029"
JS_DOT = r"[^\r\n\u2028\u2029]"
BOX = re.compile(rf"^[{JS_SPACE_CLASS}]*- \[[ x]\] ({JS_DOT}*)$")
OPENING_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n\u2028\u2029]*)$")
CLOSING_FENCE = re.compile(r"^ {0,3}(`+|~+)[ \t]*$")
SUB_BLOCK = re.compile(rf"^\*\*([^*]+)\*\*({JS_DOT}*)$")
LANE = re.compile(r"^Lane ([0-9]+)\. ")


def js_trim(text: str) -> str:
    return text.strip(JS_TRIM_CHARS)


def js_regex_text(text: str) -> str:
    return text[:-1] if text.endswith(tuple(JS_LINE_TERMINATORS)) else text


def js_number_text(digits: str) -> tuple[float, str]:
    value = float(digits)
    if value == float("inf"):
        return value, "Infinity"
    if value < 1e21:
        return value, str(int(value))
    text = repr(value)
    return value, re.sub(r"e([+-])0+([0-9]+)", r"e\1\2", text)


def opening_fence(text: str) -> tuple[str, int] | None:
    match = OPENING_FENCE.fullmatch(js_regex_text(text))
    if not match or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)[0], len(match.group(1))


def closing_fence(text: str, opening: tuple[str, int]) -> bool:
    match = CLOSING_FENCE.fullmatch(js_regex_text(text))
    return bool(match and match.group(1)[0] == opening[0] and len(match.group(1)) >= opening[1])


def boxes(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for line in lines:
        match = None if line["code"] else BOX.fullmatch(js_regex_text(str(line["text"])))
        if match:
            result.append({"n": line["n"], "text": match.group(1)})
    return result


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print("Usage: python3 check_plan.py <plan.md>", file=sys.stderr)
        return 2
    file = argv[1]
    with Path(file).open(encoding="utf-8", errors="replace", newline="") as plan:
        chunks = plan.read().split("\n")
    raw = [chunk[:-1] if index < len(chunks) - 1 and chunk.endswith("\r") else chunk for index, chunk in enumerate(chunks)]
    problems: list[str] = []

    def fail(line: int, message: str) -> None:
        problems.append(f"{file}:{line}: {message}")

    start = 0
    if raw and raw[0] == "---":
        try:
            start = raw.index("---", 1) + 1
        except ValueError:
            start = 0

    lines: list[dict[str, object]] = []
    fence: tuple[str, int] | None = None
    for index, text in enumerate(raw[start:], start):
        number = index + 1
        code = fence is not None
        if fence and closing_fence(text, fence):
            code = False
            fence = None
        elif not fence:
            fence = opening_fence(text)
            code = fence is not None
        line = {"n": number, "text": text, "code": code}
        lines.append(line)
        if code:
            continue
        prose = re.sub(r"`[^`]*`", "`", text)
        prose = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", prose)
        prose = re.sub(r"\]\([^)]*\)", "]", prose)
        if re.search(r"[\u2013\u2014]", prose):
            fail(number, "long dash")
        if re.search(r"[\u2018\u2019\u201c\u201d]", prose):
            fail(number, "curly quote")
        if re.search(rf": [^{JS_SPACE_CLASS}]", prose):
            fail(number, "mid-sentence colon")

    sections: list[dict[str, object]] = []
    for line in lines:
        text = str(line["text"])
        title = js_trim(text[3:]) if not line["code"] and text.startswith("## ") else None
        if title is not None:
            sections.append({"title": title, "n": line["n"], "body": []})
        elif sections:
            sections[-1]["body"].append(line)

    def find(title: str) -> dict[str, object] | None:
        return next((section for section in sections if section["title"] == title), None)

    def body_text(section: dict[str, object]) -> str:
        return "\n".join(str(line["text"]) for line in section["body"])

    h1 = next((index for index, line in enumerate(lines) if not line["code"] and str(line["text"]).startswith("# ")), -1)
    how_to_read = find("How to read this")
    if h1 == -1:
        fail(1, "no H1 title")
    if not how_to_read:
        fail(1, 'no "## How to read this" section')
    if h1 != -1 and how_to_read:
        intro = [line for line in lines[h1 + 1:] if line["n"] < how_to_read["n"] and js_trim(str(line["text"])) != ""]
        if len(intro) >= 10:
            fail(lines[h1]["n"], f"intro is {len(intro)} lines, under ten required")
        for marker in HOW_TO_READ_MARKERS:
            if marker not in body_text(how_to_read):
                fail(how_to_read["n"], f'How to read this lacks "{marker}"')

    program = find("Program checklist")
    if not program:
        fail(1, 'no "## Program checklist" section')
    else:
        h3s = [js_trim(str(line["text"])[4:]) for line in program["body"] if not line["code"] and str(line["text"]).startswith("### ")]
        cursor = 0
        for name in PROGRAM_H3:
            at = next((index for index in range(cursor, len(h3s)) if h3s[index].startswith(name)), -1)
            if at == -1:
                fail(program["n"], f'Program checklist lacks "### {name}" in order')
            else:
                cursor = at + 1
        for marker in PROGRAM_MARKERS:
            if marker not in body_text(program):
                fail(program["n"], f'Program checklist lacks "{marker}"')

    close = find("Close the program")
    if not close:
        fail(1, 'no "## Close the program" section')
    program_index = sections.index(program) if program else -1
    close_index = sections.index(close) if close else -1
    pr_sections = sections[program_index + 1:close_index] if program_index != -1 and close_index != -1 else []
    if not pr_sections:
        fail(1, "no PR sections between Program checklist and Close the program")

    report: list[str] = []
    for pr in pr_sections:
        heads: list[dict[str, object]] = []
        for line in pr["body"]:
            match = None if line["code"] else SUB_BLOCK.fullmatch(js_regex_text(str(line["text"])))
            if match and match.group(1) in SUB_BLOCKS:
                heads.append({"name": match.group(1), "n": line["n"], "rest": js_trim(match.group(2)), "lines": []})
            elif heads:
                heads[-1]["lines"].append(line)
        names = [head["name"] for head in heads]
        if "|".join(names) != "|".join(SUB_BLOCKS):
            fail(pr["n"], f'{pr["title"]}: sub-blocks are [{", ".join(names)}], expected [{", ".join(SUB_BLOCKS)}]')
        block = lambda name: next((head for head in heads if head["name"] == name), None)
        counts = {head["name"]: len(boxes(head["lines"])) for head in heads}
        depends = block("Depends on.")
        if depends and depends["rest"] == "":
            fail(depends["n"], f'{pr["title"]}: Depends on names nothing')
        for name in ["Files.", "Build.", "You see.", "Verify, unit.", "Merge."]:
            current = block(name)
            if current and not boxes(current["lines"]):
                fail(current["n"], f'{pr["title"]}: {name} has no box')
        for name in ["Verify, unit.", "Verify, live.", "Verify, perf."]:
            current = block(name)
            if current and not current["rest"].startswith(RULE):
                fail(current["n"], f'{pr["title"]}: {name} does not open with the rule')
        live = block("Verify, live.")
        if live:
            if not LANES.search(live["rest"]):
                fail(live["n"], f'{pr["title"]}: Verify, live lacks "Ten lanes on `<swarm workers model>` at the PR head" with the model filled in')
            lanes = [{"n": item["n"], "text": item["text"], "m": LANE.match(item["text"])} for item in boxes(live["lines"])]
            numbers = sorted((js_number_text(item["m"].group(1)) for item in lanes if item["m"]), key=lambda item: item[0])
            number_text = ",".join(item[1] for item in numbers)
            if number_text != "1,2,3,4,5,6,7,8,9,10":
                fail(live["n"], f'{pr["title"]}: lanes are [{number_text}], expected 1 to 10')
            for lane in lanes:
                if not lane["m"]:
                    fail(lane["n"], f'{pr["title"]}: live box is not a lane')
                elif not re.search(r"Save `[^`]+`", lane["text"]):
                    fail(lane["n"], f'{pr["title"]}: lane {lane["m"].group(1)} names no screenshot')
                elif "Pass when" not in lane["text"]:
                    fail(lane["n"], f'{pr["title"]}: lane {lane["m"].group(1)} has no pass predicate')
        perf = block("Verify, perf.")
        if perf:
            items = [item["text"].split(" ")[0] for item in boxes(perf["lines"])]
            if "|".join(items) != "|".join(PERF_ITEMS):
                fail(perf["n"], f'{pr["title"]}: perf boxes are [{", ".join(items)}], expected [{", ".join(PERF_ITEMS)}]')
        gate = block("Review gate.")
        if gate:
            gate_boxes = boxes(gate["lines"])
            if gate["rest"].startswith("None."):
                if gate_boxes:
                    fail(gate["n"], f'{pr["title"]}: Review gate says None but has boxes')
            else:
                text = "\n".join(str(line["text"]) for line in gate["lines"])
                if not gate_boxes:
                    fail(gate["n"], f'{pr["title"]}: Review gate has no box')
                for word in ["screenshot", "video", "operator"]:
                    if word not in text:
                        fail(gate["n"], f'{pr["title"]}: Review gate lacks "{word}"')
        total = len(boxes(pr["body"]))
        cells = [f'{re.sub(r"-$", "", re.sub(r"[ ,.]+", "-", name)).lower()}={counts.get(name, 0)}' for name in SUB_BLOCKS if name != "Depends on."]
        report.append(f'{pr["title"]}  boxes={total}  {" ".join(cells)}')

    if close_index != -1:
        tail = sections[close_index + 1:]
        for section in tail:
            if not section["title"].startswith("Appendix"):
                fail(section["n"], f'"## {section["title"]}" after Close the program is not an appendix')
        if not any("Prototype evidence" in section["title"] for section in tail):
            fail(close["n"], 'no "## Appendix ... Prototype evidence" section')

    if report:
        print(*report, sep="\n")
    print(f"{len(pr_sections)} PR sections, {len(problems)} problems")
    if problems:
        print(*problems, sep="\n", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

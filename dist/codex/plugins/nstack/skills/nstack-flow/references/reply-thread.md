# GitHub comments and thread replies

[Script](../scripts/reply_thread.py). Post one authorized GitHub review-thread
reply or top-level PR comment with automation attribution. Requires Python
3.11+ and an authenticated `gh`; no external Python packages.

## Run

Resolve the script from the installed nstack-flow directory. Keep the project
working directory and write plain UTF-8 reply prose to a body file.

```bash
python3 "<nstack-flow skill directory>/scripts/reply_thread.py" --hostname <hostname> --repo <owner>/<repo> --pr <number> --comment-id <root-comment-id> --body-file <reply-file>
```

Use `--help` for the exact CLI schema. Exactly one of `--comment-id` and
`--top-level` is required. `--comment-id` is the root review comment's numeric
database ID, not a reply ID or GraphQL node ID. For a separately authorized
top-level PR comment, replace that selector with `--top-level`. Never use it
as a fallback for a missing root ID.

Host selection is `--hostname`, then `GH_HOST`, then `github.com`. Set
`--hostname github.example.com` explicitly for Enterprise. Empty or malformed
selected hosts fail rather than falling back. Every read and post uses that
same host; `gh` owns authentication and Enterprise API routing. The helper
does not switch hosts or accounts.

## Attribution and effects

The helper adds ``🤖 Automated post by `nstack`.`` Pass optional
`--model <model-id>` only with evidence of the executing model, not a configured
role or seat. That produces
``🤖 Automated post by `nstack`, model `<model-id>`.``
The script checks formatting, not the truth of that evidence.

Only recognized leading helper banners are replaced, so formatting twice does
not stack attribution. The remaining body and input file stay unchanged.
Empty bodies and invalid UTF-8 fail before posting.

Thread replies validate the root and canonical PR resource before one POST.
Top-level comments validate the PR's issue-comment resource. Payloads travel
as JSON on stdin, not shell text. No response URL is followed.
Posting still requires covering user authority. This helper does not create
reviews, resolve threads, mark ready, merge or push. Origin and native app-local
thread operations are outside its scope; do not pass app-local IDs here.

## Results and failures

One compact JSON result includes the selected target and an `outcome`.

| Result | Meaning |
| --- | --- |
| `ok: true`, `posted` | Returned receipt matches the target and exact body; includes server ID, URL and author |
| `ok: false`, `not_attempted` | Input, preflight or process-launch failure prevented posting |
| `ok: false`, `uncertain` | Posting started but did not yield a verified receipt |

Exit 0 means a verified receipt, 1 a classified failure, and 2 invalid CLI
usage. Help exits 0. Inspect the error diagnostics; after an uncertain result,
inspect the remote thread or PR comments before retrying. The helper never
retries a post. Repeating an invocation can create duplicate comments.

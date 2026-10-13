<overview>
When building skills that make API calls requiring credentials (API keys, tokens, secrets), follow this protocol to prevent credentials from appearing in chat.
</overview>

<the_problem>
Commands containing literal credentials, shell tracing, verbose HTTP logs, or echoed expanded values can expose credentials:

```bash
# ❌ BAD - API key visible in chat
curl -H "Authorization: Bearer $API_KEY" https://api.example.com/data
```

Do not print credential values in commands, diagnostics, or chat. Environment-variable expansion alone does not necessarily expose a value in chat, but tracing and command logging can.
</the_problem>

<the_solution>
Use an existing approved wrapper or bundle `scripts/secure-api.sh` with the skill. Verify it exists and review its behavior; no client installs this wrapper automatically. Resolve `SKILL_DIR` from the selected skill and choose credential storage separately with the user.

<for_supported_services>
```bash
# ✅ GOOD - No credentials visible
"$SKILL_DIR/scripts/secure-api.sh" <service> <operation> [args]

# Examples:
"$SKILL_DIR/scripts/secure-api.sh" facebook list-campaigns
"$SKILL_DIR/scripts/secure-api.sh" ghl search-contact "email@example.com"
```
</for_supported_services>

<adding_new_services>
When building a new skill that requires API calls:

1. **Add operations to the selected wrapper** (`scripts/secure-api.sh` in this example), confirming before changing existing files:

```bash
case "$SERVICE" in
    yourservice)
        case "$OPERATION" in
            list-items)
                curl -s -G \
                    -H "Authorization: Bearer $YOUR_API_KEY" \
                    "https://api.yourservice.com/items"
                ;;
            get-item)
                ITEM_ID=$1
                curl -s -G \
                    -H "Authorization: Bearer $YOUR_API_KEY" \
                    "https://api.yourservice.com/items/$ITEM_ID"
                ;;
            *)
                echo "Unknown operation: $OPERATION" >&2
                exit 1
                ;;
        esac
        ;;
esac
```

2. **Add profile support to the wrapper** (if service needs multiple accounts):

```bash
# Explicitly allow known profiles; never evaluate user-provided variable names.
case "$PROFILE" in
    main)
        YOURSERVICE_API_KEY="${YOURSERVICE_MAIN_API_KEY:?Main API key missing}"
        YOURSERVICE_ACCOUNT_ID="${YOURSERVICE_MAIN_ACCOUNT_ID:?Main account ID missing}"
        ;;
    clienta)
        YOURSERVICE_API_KEY="${YOURSERVICE_CLIENTA_API_KEY:?Client A API key missing}"
        YOURSERVICE_ACCOUNT_ID="${YOURSERVICE_CLIENTA_ACCOUNT_ID:?Client A account ID missing}"
        ;;
    *)
        echo "Unknown profile" >&2
        exit 1
        ;;
esac
```

3. **Choose credential storage with the user**: an approved secret manager, existing environment variables, or a user-owned file outside version control. Do not read or copy secret values into chat or a skill.

If a local environment file is requested, assign its confirmed absolute path to `CREDENTIAL_FILE`. With approval, add empty placeholders without overwriting existing values:

```bash
# Check if entries already exist
umask 077
grep -q "^YOURSERVICE_MAIN_API_KEY=" "$CREDENTIAL_FILE" 2>/dev/null || \
  printf '\nYOURSERVICE_MAIN_API_KEY=\n' >> "$CREDENTIAL_FILE"
grep -q "^YOURSERVICE_MAIN_ACCOUNT_ID=" "$CREDENTIAL_FILE" 2>/dev/null || \
  printf 'YOURSERVICE_MAIN_ACCOUNT_ID=\n' >> "$CREDENTIAL_FILE"

echo "Credential placeholders prepared; fill them in outside chat"
```

4. **Document profile workflow in your SKILL.md**:

```markdown
## Profile Selection Workflow

**CRITICAL:** Always use profile selection to prevent using wrong account credentials.

The helper names below are examples, not built-ins. Bundle and validate them if needed, or use an existing approved profile mechanism. Resolve all paths from the selected skill directory.

### When user requests YourService operation:

1. **Check for saved profile:**
   ```bash
   "$SKILL_DIR/scripts/profile-state" get yourservice
   ```

2. **If no profile saved, discover available profiles:**
   ```bash
   "$SKILL_DIR/scripts/list-profiles" yourservice
   ```

3. **If only ONE profile:** Use it automatically and announce:
   ```
   "Using YourService profile 'main' to list items..."
   ```

4. **If MULTIPLE profiles:** Ask user which one:
   ```
   "Which YourService profile: main, clienta, or clientb?"
   ```

5. **Save user's selection:**
   ```bash
   "$SKILL_DIR/scripts/profile-state" set yourservice <selected_profile>
   ```

6. **Always announce which profile before calling API:**
   ```
   "Using YourService profile 'main' to list items..."
   ```

7. **Make API call with profile:**
   ```bash
   "$SKILL_DIR/scripts/secure-api.sh" yourservice:<profile> list-items
   ```

## Secure API Calls

All API calls use profile syntax:

```bash
"$SKILL_DIR/scripts/secure-api.sh" yourservice:<profile> <operation> [args]

# Examples:
"$SKILL_DIR/scripts/secure-api.sh" yourservice:main list-items
"$SKILL_DIR/scripts/secure-api.sh" yourservice:main get-item <ITEM_ID>
```

**Profile persists for session:** Once selected, use same profile for subsequent operations unless user explicitly changes it.
```
</adding_new_services>
</the_solution>

<pattern_guidelines>
<simple_get_requests>
```bash
curl -s -G \
    -H "Authorization: Bearer $API_KEY" \
    "https://api.example.com/endpoint"
```
</simple_get_requests>

<post_with_json_body>
```bash
ITEM_ID=$1
curl -s -X POST \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d @- \
    "https://api.example.com/items/$ITEM_ID"
```

Usage:
```bash
echo '{"name":"value"}' | "$SKILL_DIR/scripts/secure-api.sh" service create-item
```
</post_with_json_body>

<post_with_form_data>
```bash
curl -s -X POST \
    -F "field1=value1" \
    -F "field2=value2" \
    -F "access_token=$API_TOKEN" \
    "https://api.example.com/endpoint"
```
</post_with_form_data>
</pattern_guidelines>

<credential_storage>
**Location:** The user-approved secret store or user-owned environment file, kept outside version control. Do not assume a client-specific global `.env` location.

**Format:**
```bash
# Service credentials
SERVICE_API_KEY=
SERVICE_ACCOUNT_ID=

# Another service
OTHER_API_TOKEN=
OTHER_BASE_URL=https://api.other.com
```

**Loading in script:**
```bash
set -a
source "$CREDENTIAL_FILE" || { echo "Error: credential file unavailable" >&2; exit 1; }
set +a
```
Source only a trusted, user-owned shell-format file; sourcing executes its contents. Prefer an existing secret-management mechanism where available. Do not enable shell tracing or log request headers or tokens.
</credential_storage>

<best_practices>
1. **Keep authenticated curl inside the reviewed wrapper** - user-facing commands pass only non-secret inputs
2. **Document supported wrapper operations** - don't assume undocumented helpers exist
3. **Confirm before creating credential placeholders** - never overwrite existing values
4. **Keep credentials outside the skill and version control** - use the approved storage mechanism
5. **Document each operation** - show examples in SKILL.md
6. **Handle errors gracefully** - check for missing env vars, show helpful error messages
</best_practices>

<testing>
Test the wrapper without exposing credentials:

```bash
# This command appears in chat
"$SKILL_DIR/scripts/secure-api.sh" facebook list-campaigns

# Ensure the wrapper redacts diagnostics and does not trace or print secrets
```

Verify credentials are loaded:
```bash
# Check .env exists
test -f "$CREDENTIAL_FILE" && echo "Credential file exists"

# Check specific variables (without showing values)
grep -q "^YOUR_API_KEY=" "$CREDENTIAL_FILE" && echo "API key field exists" || echo "API key field missing"
```
A field's presence does not prove it is non-empty or valid. Have the wrapper validate required values internally and report only success or a redacted error.
</testing>

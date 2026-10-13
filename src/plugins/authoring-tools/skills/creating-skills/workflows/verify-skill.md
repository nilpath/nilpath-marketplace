# Workflow: Verify Skill Content Accuracy

<required_reading>
**Read these reference files NOW:**
1. references/skill-structure.md
2. references/authoring-targets.md
3. references/official-spec.md
</required_reading>

<purpose>
Audit checks structure. **Verify checks truth.**

Skills contain claims about external things: APIs, CLI tools, frameworks, services. These change over time. This workflow checks if a skill's content is still accurate.
</purpose>

<process>
## Step 1: Select the Skill

Use a supplied path, or ask whether to enumerate workspace or personal skills using the active client's locations in `references/authoring-targets.md`. Follow the existing convention and show full paths for duplicate names.

Present a numbered list, ask: "Which skill should I verify for accuracy?" Record its absolute path as `SKILL_DIR`; verify that skill in place.

## Step 2: Read and Categorize

Read the entire skill (SKILL.md + workflows/ + references/):
```bash
cat "$SKILL_DIR/SKILL.md"
cat "$SKILL_DIR"/workflows/*.md 2>/dev/null
cat "$SKILL_DIR"/references/*.md 2>/dev/null
```

Read scripts, templates, and any invocation-policy file too. Verify metadata and discovery claims against the active client's specification: folder/name match, 64-character name limit, 1,024-character description limit, invocation controls, input handling, and resource execution. Do not assume another client's substitution or permission behavior. In opt-in marketplace-source mode, read `.j2` sources and validate rendered files for each target instead.

Categorize by primary dependency type:

| Type | Examples | Verification Method |
|------|----------|---------------------|
| **API/Service** | manage-stripe, manage-gohighlevel | Available documentation tools + web search |
| **CLI Tools** | build-macos-apps (xcodebuild, swift) | Run commands |
| **Framework** | build-iphone-apps (SwiftUI, UIKit) | Official framework documentation |
| **Integration** | setup-stripe-payments | Web fetch + available documentation tools |
| **Pure Process** | create-agent-skills | No external deps |

Report: "This skill is primarily [type]-based. I'll verify using [method]."

## Step 3: Extract Verifiable Claims

Scan skill content and extract:

**CLI Tools mentioned:**
- Tool names (xcodebuild, swift, npm, etc.)
- Specific flags/options documented
- Expected output patterns

**API Endpoints:**
- Service names (Stripe, Meta, etc.)
- Specific endpoints documented
- Authentication methods
- SDK versions

**Framework Patterns:**
- Framework names (SwiftUI, React, etc.)
- Specific APIs/patterns documented
- Version-specific features

**File Paths/Structures:**
- Expected project structures
- Config file locations

Present: "Found X verifiable claims to check."

## Step 4: Verify by Type

### For CLI Tools
```bash
# Check tool exists
which {tool-name}

# Check version
{tool-name} --version

# Verify documented flags work
{tool-name} --help | grep "{documented-flag}"
```

### For API/Service Skills
Use an available documentation integration (such as Context7) or fetch official documentation. Discover the actual tool names exposed by the client instead of copying another client's MCP spelling.

Compare skill's documented patterns against current docs:
- Are endpoints still valid?
- Has authentication changed?
- Are there deprecated methods being used?

### For Framework Skills
Fetch current official framework documentation using the available documentation integration or web tools.

Check:
- Are documented APIs still current?
- Have patterns changed?
- Are there newer recommended approaches?

### For Integration Skills
Search the web for recent changes:
```
"[service name] API changes [current year]"
"[service name] breaking changes"
"[service name] deprecated endpoints"
```

Then check official SDK documentation for current patterns.

### For Services with Status Pages
Fetch official docs/changelog if available.

## Step 5: Generate Freshness Report

Present findings:

```
## Verification Report: {skill-name}

### ✅ Verified Current
- [Claim]: [Evidence it's still accurate]

### ⚠️ May Be Outdated
- [Claim]: [What changed / newer info found]
  → Current: [what docs now say]

### ❌ Broken / Invalid
- [Claim]: [Why it's wrong]
  → Fix: [What it should be]

### ℹ️ Could Not Verify
- [Claim]: [Why verification wasn't possible]

---
**Overall Status:** [Fresh / Needs Updates / Significantly Stale]
**Last Verified:** [Today's date]
```

## Step 6: Offer Updates

If issues found:

"Found [N] items that need updating. Would you like me to:"

1. **Update all** - Apply all corrections
2. **Review each** - Show each change before applying
3. **Just the report** - No changes

If updating:
- Confirm before replacing selected existing files; do not relocate the skill or duplicate it
- Make changes based on verified current information
- Add verification date comment if appropriate
- Report what was updated

## Step 7: Suggest Verification Schedule

Based on skill type, recommend:

| Skill Type | Recommended Frequency |
|------------|----------------------|
| API/Service | Every 1-2 months |
| Framework | Every 3-6 months |
| CLI Tools | Every 6 months |
| Pure Process | Annually |

"This skill should be re-verified in approximately [timeframe]."
</process>

<verification_shortcuts>
## Quick Verification Commands

**Check if CLI tool exists and get version:**
```bash
which {tool} && {tool} --version
```

**Context7 pattern for any library:**
```
1. resolve-library-id: "{library-name}"
2. get-library-docs: "{id}", topic: "{specific-feature}"
```

**Web search patterns:**
- Breaking changes: "{service} breaking changes {current year}"
- Deprecations: "{service} deprecated API"
- Current best practices: "{framework} best practices {current year}"
</verification_shortcuts>

<success_criteria>
Verification is complete when:
- [ ] Skill categorized by dependency type
- [ ] Verifiable claims extracted
- [ ] Active-client metadata, invocation, placement, and execution claims checked
- [ ] Each claim checked with appropriate method
- [ ] Freshness report generated
- [ ] Updates applied (if requested)
- [ ] User knows when to re-verify
</success_criteria>

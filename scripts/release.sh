#!/usr/bin/env bash
#
# Release script for Nest
# Usage: ./scripts/release.sh [--yes|-y] [--patch|--minor|--major]
#
# Flags:
#   --yes, -y         Skip all confirmation prompts (for AI/CI use)
#   --patch           Force a patch bump
#   --minor           Force a minor bump
#   --major           Force a major bump
#
# Automatically determines version bump from conventional commits:
#   fix:              → patch (0.0.X)
#   feat:             → minor (0.X.0)
#   BREAKING CHANGE:  → major (X.0.0)
#   feat!: / fix!:    → major (X.0.0)
#
# Uses git-cliff for changelog generation and commit analysis.
# Uses perl for cross-platform in-place file editing.
#
# Users install via:
#   uv tool install git+https://github.com/jbb10/nest
#   uv tool install git+https://github.com/jbb10/nest@v0.2.0
#

set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
header(){ echo -e "\n${BOLD}${BLUE}═══ $1 ═══${NC}\n"; }

# ─── Parse Arguments ─────────────────────────────────────────────────────────

FORCE_BUMP=""
AUTO_YES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --yes|-y) AUTO_YES=true; shift ;;
        --patch) FORCE_BUMP="patch"; shift ;;
        --minor) FORCE_BUMP="minor"; shift ;;
        --major) FORCE_BUMP="major"; shift ;;
        -h|--help)
            echo "Usage: $0 [--yes|-y] [--patch|--minor|--major]"
            echo ""
            echo "Options:"
            echo "  --yes, -y    Skip all confirmation prompts (for AI/CI use)"
            echo "  --patch      Force a patch version bump"
            echo "  --minor      Force a minor version bump"
            echo "  --major      Force a major version bump"
            echo ""
            echo "Requires: uv, git, git-cliff, perl"
            exit 0
            ;;
        *) error "Unknown option: $1" ;;
    esac
done

# Helper: prompt for confirmation (auto-accepts when --yes is set)
confirm() {
    local prompt="$1"
    if $AUTO_YES; then
        info "Auto-confirmed: $prompt"
        return 0
    fi
    read -p "$prompt (y/N) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# ─── Pre-flight Checks ───────────────────────────────────────────────────────

header "Pre-flight Checks"

# Must run from project root
if [ ! -f "pyproject.toml" ]; then
    error "Must run from project root (pyproject.toml not found)"
fi

# Required tools
command -v uv        >/dev/null 2>&1 || error "uv is not installed"
command -v git       >/dev/null 2>&1 || error "git is not installed"
command -v git-cliff >/dev/null 2>&1 || error "git-cliff is not installed (brew install git-cliff)"
command -v perl      >/dev/null 2>&1 || error "perl is not installed"

info "All required tools present"

# Clean working directory
if [ -n "$(git status --porcelain)" ]; then
    error "Git working directory is not clean. Commit or stash changes first."
fi
info "Working directory is clean"

# Branch check
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    warn "Not on main branch (currently on: $CURRENT_BRANCH)"
    if ! confirm "Continue anyway?"; then
        exit 1
    fi
else
    info "On main branch"
fi

# Pull latest
info "Pulling latest from origin..."
git pull --ff-only origin "$CURRENT_BRANCH" || error "Failed to pull latest changes. Resolve conflicts first."

# ─── Version Determination ────────────────────────────────────────────────────

header "Version Determination"

# Read current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | head -1 | perl -pe 's/version = "(.*)"/\1/')
if [ -z "$CURRENT_VERSION" ]; then
    error "Could not read version from pyproject.toml"
fi
info "Current version: ${BOLD}$CURRENT_VERSION${NC}"

# Parse semver components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Find last release tag
LAST_TAG=$(git describe --tags --abbrev=0 --match 'v[0-9]*' 2>/dev/null || echo "")

if [ -n "$LAST_TAG" ]; then
    info "Last release tag: $LAST_TAG"
    COMMIT_RANGE="${LAST_TAG}..HEAD"
else
    warn "No previous release tags found — analyzing all commits"
    COMMIT_RANGE=""
fi

# Count commits since last tag
if [ -n "$COMMIT_RANGE" ]; then
    COMMIT_COUNT=$(git rev-list --count "$COMMIT_RANGE" 2>/dev/null || echo "0")
else
    COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
fi

if [ "$COMMIT_COUNT" -eq 0 ]; then
    error "No commits found since last release ($LAST_TAG)"
fi
info "$COMMIT_COUNT commits since last release"

# ─── Commit Analysis ─────────────────────────────────────────────────────────

header "Commit Analysis"

# Display commits since last release
echo -e "${BLUE}Commits since last release:${NC}"
if [ -n "$COMMIT_RANGE" ]; then
    git log "$COMMIT_RANGE" --pretty=format:"  %C(dim)%h%C(reset) %s" | head -30
else
    git log --pretty=format:"  %C(dim)%h%C(reset) %s" | head -30
fi
echo -e "\n"

# Determine bump type
if [ -n "$FORCE_BUMP" ]; then
    BUMP_TYPE="$FORCE_BUMP"
    info "Forced bump type: ${BOLD}$BUMP_TYPE${NC}"
else
    # Use git-cliff to analyze commits and determine bump type
    # Get unreleased changelog to detect commit types
    CLIFF_OUTPUT=$(git-cliff --unreleased --strip all 2>/dev/null || echo "")

    HAS_BREAKING=false
    HAS_FEAT=false
    HAS_FIX=false

    # Analyze commit messages directly for bump determination
    if [ -n "$COMMIT_RANGE" ]; then
        COMMITS=$(git log "$COMMIT_RANGE" --pretty=format:"%s" 2>/dev/null || echo "")
    else
        COMMITS=$(git log --pretty=format:"%s" 2>/dev/null || echo "")
    fi

    while IFS= read -r commit; do
        if [[ "$commit" =~ ^[a-z]+!: ]] || [[ "$commit" =~ BREAKING[[:space:]]CHANGE ]]; then
            HAS_BREAKING=true
        fi
        if [[ "$commit" =~ ^feat(\(.+\))?!?: ]]; then
            HAS_FEAT=true
        fi
        if [[ "$commit" =~ ^fix(\(.+\))?!?: ]]; then
            HAS_FIX=true
        fi
    done <<< "$COMMITS"

    if $HAS_BREAKING; then
        BUMP_TYPE="major"
        info "Detected: ${RED}BREAKING CHANGE${NC} → ${BOLD}major${NC} bump"
    elif $HAS_FEAT; then
        BUMP_TYPE="minor"
        info "Detected: ${GREEN}feat:${NC} commits → ${BOLD}minor${NC} bump"
    elif $HAS_FIX; then
        BUMP_TYPE="patch"
        info "Detected: ${YELLOW}fix:${NC} commits → ${BOLD}patch${NC} bump"
    else
        BUMP_TYPE="patch"
        warn "No conventional commits found — defaulting to ${BOLD}patch${NC} bump"
    fi
fi

# Calculate new version
case $BUMP_TYPE in
    major) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
    minor) NEW_VERSION="${MAJOR}.$((MINOR + 1)).0" ;;
    patch) NEW_VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))" ;;
esac

echo ""
info "Version bump: ${BOLD}$CURRENT_VERSION → $NEW_VERSION${NC} ($BUMP_TYPE)"

# ─── Changelog Preview ───────────────────────────────────────────────────────

header "Changelog Preview"

# Generate changelog for this release using git-cliff
CHANGELOG_ENTRY=$(git-cliff --unreleased --tag "v$NEW_VERSION" --strip header 2>/dev/null || echo "")

if [ -z "$CHANGELOG_ENTRY" ]; then
    warn "git-cliff produced no output — commits may not follow conventional format"
    echo -e "${BLUE}Raw commits will be used as changelog.${NC}"
    CHANGELOG_ENTRY="## [${NEW_VERSION}] - $(date +%Y-%m-%d)"$'\n\n'"### Changes"$'\n'
    if [ -n "$COMMIT_RANGE" ]; then
        CHANGELOG_ENTRY+=$(git log "$COMMIT_RANGE" --pretty=format:"- %s" 2>/dev/null)
    else
        CHANGELOG_ENTRY+=$(git log --pretty=format:"- %s" 2>/dev/null)
    fi
fi

echo "$CHANGELOG_ENTRY"

# ─── Approval Gate ────────────────────────────────────────────────────────────

header "Release Confirmation"

echo -e "  Version:  ${BOLD}$CURRENT_VERSION → $NEW_VERSION${NC}"
echo -e "  Tag:      ${BOLD}v$NEW_VERSION${NC}"
echo -e "  Branch:   ${BOLD}$CURRENT_BRANCH${NC}"
echo -e "  Files:    pyproject.toml, src/nest/__init__.py, CHANGELOG.md"
echo ""
if ! confirm "Proceed with release?"; then
    info "Release aborted."
    exit 0
fi

# ─── Update Version ──────────────────────────────────────────────────────────

header "Updating Version"

# Update pyproject.toml (cross-platform with perl)
perl -pi -e "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
info "Updated pyproject.toml"

# Update src/nest/__init__.py
perl -pi -e "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" src/nest/__init__.py
info "Updated src/nest/__init__.py"

# Verify updates
VERIFY_PYPROJECT=$(grep '^version = ' pyproject.toml | head -1 | perl -pe 's/version = "(.*)"/\1/')
VERIFY_INIT=$(grep '__version__' src/nest/__init__.py | perl -pe 's/.*"(.*)".*/\1/')
if [ "$VERIFY_PYPROJECT" != "$NEW_VERSION" ] || [ "$VERIFY_INIT" != "$NEW_VERSION" ]; then
    error "Version update verification failed (pyproject=$VERIFY_PYPROJECT, __init__=$VERIFY_INIT)"
fi
info "Version verification passed"

# ─── Update Changelog ────────────────────────────────────────────────────────

header "Updating Changelog"

# Generate full changelog with git-cliff (includes all previous releases)
git-cliff --tag "v$NEW_VERSION" --output CHANGELOG.md 2>/dev/null
info "Generated CHANGELOG.md"

# ─── Run CI Suite ─────────────────────────────────────────────────────────────

header "Running CI Suite"

info "Running: make ci (lint + format-check + typecheck + all tests)"
echo ""
make ci || {
    warn "CI failed! Rolling back version changes..."
    git checkout pyproject.toml src/nest/__init__.py CHANGELOG.md
    error "CI suite failed. Fix issues and try again."
}
info "CI suite passed"

# ─── Commit & Tag ────────────────────────────────────────────────────────────

header "Creating Release Commit & Tag"

git add pyproject.toml src/nest/__init__.py CHANGELOG.md
git commit -m "chore(release): v$NEW_VERSION"
info "Created commit: chore(release): v$NEW_VERSION"

git tag -a "v$NEW_VERSION" --cleanup=verbatim -m "Release v$NEW_VERSION

$CHANGELOG_ENTRY"
info "Created annotated tag: v$NEW_VERSION"

# Move 'latest' tag
git tag -d latest 2>/dev/null || true
git tag -a latest -m "Latest release (v$NEW_VERSION)"
info "Moved 'latest' tag → v$NEW_VERSION"

# ─── Push Confirmation ───────────────────────────────────────────────────────

header "Push Confirmation"

echo -e "  Ready to push:"
echo -e "    • Branch ${BOLD}$CURRENT_BRANCH${NC} to origin"
echo -e "    • Tag ${BOLD}v$NEW_VERSION${NC}"
echo -e "    • Tag ${BOLD}latest${NC} (force-update)"
echo ""
if ! confirm "Push to remote?"; then
    warn "Aborting push. Rolling back local changes..."
    git tag -d "v$NEW_VERSION" 2>/dev/null || true
    git tag -d latest 2>/dev/null || true
    git reset --soft HEAD~1
    git checkout pyproject.toml src/nest/__init__.py CHANGELOG.md
    info "Rolled back. No changes pushed."
    exit 1
fi

# ─── Push ─────────────────────────────────────────────────────────────────────

header "Pushing Release"

git push origin "$CURRENT_BRANCH"
info "Pushed branch $CURRENT_BRANCH"

git push origin "v$NEW_VERSION"
info "Pushed tag v$NEW_VERSION"

git push origin latest --force
info "Force-pushed latest tag"

# ─── Success ──────────────────────────────────────────────────────────────────

header "Release Complete"

echo -e "  ${GREEN}✓${NC} Successfully released ${BOLD}v$NEW_VERSION${NC}"
echo ""
echo -e "  ${BLUE}Install:${NC}"
echo -e "    uv tool install git+https://github.com/jbb10/nest            ${DIM}# latest${NC}"
echo -e "    uv tool install git+https://github.com/jbb10/nest@v$NEW_VERSION   # this version"
echo -e "    uv tool install git+https://github.com/jbb10/nest@latest     # latest tag"
echo ""
echo -e "  ${BLUE}Changelog:${NC}"
echo -e "    https://github.com/jbb10/nest/blob/main/CHANGELOG.md"
echo ""

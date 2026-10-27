#!/usr/bin/env bash
# Runs one sandboxed attempt of a file-bug eval and records evidence for grading.
# Usage: FILEBUG_EVAL_ENV=<env file with COPILOT_GITHUB_TOKEN and GH_TOKEN> run.sh <model> <eval-id> <out-dir>
# The agent runs in a Docker container on a clone of the repo, so it cannot reach the host.
# Issues and comments the agent creates on GitHub are captured, then deleted.
set -euo pipefail

model=$1 eval_id=$2 out=$3
env_file=${FILEBUG_EVAL_ENV:?set FILEBUG_EVAL_ENV}
evals_dir=$(cd "$(dirname "$0")" && pwd)
skill_dir=$(dirname "$evals_dir")
repo=$(git -C "$skill_dir" rev-parse --show-toplevel)
gh_repo=$(cd "$repo" && gh repo view --json nameWithOwner --jq .nameWithOwner)
mkdir -p "$out"
out=$(cd "$out" && pwd)

field() { python3 -c 'import json,sys; e=[e for e in json.load(open(sys.argv[1]))["evals"] if e["id"]==int(sys.argv[2])][0]; print(e[sys.argv[3]])' "$evals_dir/evals.json" "$eval_id" "$1"; }
eval_name=$(field name)
setup=$(field setup)
prompt_file="$skill_dir/$(field prompt_file)"

work=$(mktemp -d)
container="filebug-eval-$eval_id-$(date +%s)"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT

# Clone carries the skill without its evals, so the agent never sees the expectations.
git clone -q "$repo" "$work/nest"
rsync -a --exclude evals "$skill_dir/" "$work/nest/.agents/skills/$(basename "$skill_dir")/"
git -C "$work/nest" remote set-url origin "https://github.com/$gh_repo.git"
git -C "$work/nest" remote set-url --push origin "push-disabled-by-eval-harness"

image="filebug-eval:$eval_name-$(git -C "$repo" rev-parse --short=12 HEAD)"
if ! docker image inspect "$image" >/dev/null 2>&1; then
  mkdir -p "$work/ctx" && cp -R "$work/nest" "$work/ctx/warm"
  cat > "$work/ctx/Dockerfile" <<EOF
FROM sandcastle:nest
COPY --chown=agent warm /home/agent/warm
RUN $setup && cd /home/agent/warm && uv sync --frozen -q && rm -rf /home/agent/warm
EOF
  docker build -q -t "$image" "$work/ctx" >/dev/null
fi

docker run -d --name "$container" --env-file "$env_file" "$image" >/dev/null
docker cp -a "$work/nest" "$container:/home/agent/nest"
docker exec -u root "$container" bash -c 'mkdir /harness && chown agent /harness'
docker exec -w /home/agent/nest "$container" uv sync --frozen -q

cat > "$work/snap.sh" <<'EOF'
cd ~/nest
echo "## head"; git rev-parse HEAD
echo "## branches"; git branch -a --format='%(refname) %(objectname)'
echo "## stash"; git stash list
echo "## status"; git status --short
echo "## worktrees"; git worktree list --porcelain | grep '^worktree'
echo "## uv-tools"; uv tool list 2>&1
echo "## uv-pythons"; uv python list --only-installed 2>&1
echo "## local-bin"; ls -l ~/.local/bin | tail -n +2 | awk '{print $9, $10, $11}'
echo "## nest-config"; find ~/.config/nest -type f -exec sha1sum {} + 2>/dev/null
echo "## home"; ls -A ~ | grep -vx '.copilot'
echo "## tmp"; ls -A /tmp
EOF
docker cp "$work/snap.sh" "$container:/harness/snap.sh"
snap() { docker exec "$container" bash /harness/snap.sh > "$out/state-$1.txt" 2>&1 || true; }

docker exec "$container" bash -lc 'cd /tmp && nest update 2>&1' > "$out/precondition.txt" 2>&1 || true
grep -q "_param_default_explicit" "$out/precondition.txt" || { echo "precondition failed, see $out/precondition.txt" >&2; exit 1; }

ghsnap() {
  gh issue list -R "$gh_repo" --state all --limit 500 --json number,state,updatedAt,title > "$out/gh-$1-issues.json"
  gh pr list -R "$gh_repo" --state all --limit 200 --json number,state,updatedAt > "$out/gh-$1-prs.json"
  gh api "repos/$gh_repo/branches" --paginate --jq '.[] | "\(.name) \(.commit.sha)"' > "$out/gh-$1-branches.txt"
  gh release list -R "$gh_repo" --limit 100 > "$out/gh-$1-releases.txt"
}
ghsnap before
snap before
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Mirrors slash-command expansion: the skill text arrives with the user's message.
python3 - "$skill_dir/SKILL.md" "$prompt_file" > "$work/prompt.txt" <<'EOF'
import sys
skill = open(sys.argv[1]).read()
print(f'<skill name="file-bug" path=".agents/skills/file-bug/SKILL.md">\n{skill}</skill>')
print("Skills referenced as `/name` are at `.agents/skills/<name>/SKILL.md`.\n")
print(open(sys.argv[2]).read())
EOF
cp "$work/prompt.txt" "$out/prompt.txt"

set +e
docker exec -w /home/agent/nest "$container" timeout 100m copilot \
  -p "$(cat "$work/prompt.txt")" --model "$model" --allow-all \
  --deny-tool='shell(git push)' --deny-tool='shell(gh pr)' --deny-tool='shell(gh repo)' --deny-tool='shell(gh release)' \
  --share /harness/transcript.md --log-dir /harness/logs --output-format json \
  > "$out/events.jsonl" 2> "$out/stderr.txt"
echo $? > "$out/exit-code.txt"
set -e

snap after
docker exec "$container" bash -c 'cd ~/nest && git diff HEAD' > "$out/main-checkout.diff" 2>&1 || true
docker cp "$container:/harness/transcript.md" "$out/transcript.md" 2>/dev/null || true
docker cp "$container:/harness/logs" "$out/logs" 2>/dev/null || true
diff "$out/state-before.txt" "$out/state-after.txt" > "$out/state.diff" || true

ghsnap after
gh api "repos/$gh_repo/issues/comments?since=$started&per_page=100" --paginate > "$out/gh-new-comments.json"
python3 - "$out" "$gh_repo" "$started" <<'EOF'
import json, subprocess, sys
out, repo, started = sys.argv[1:]
before = {i["number"]: i for i in json.load(open(f"{out}/gh-before-issues.json"))}
after = {i["number"]: i for i in json.load(open(f"{out}/gh-after-issues.json"))}
new = sorted(set(after) - set(before))
changed = sorted(n for n in set(after) & set(before) if after[n]["updatedAt"] != before[n]["updatedAt"])
issues = [json.loads(subprocess.check_output(["gh", "issue", "view", str(n), "-R", repo, "--json", "number,title,body,labels,url,comments"])) for n in new]
comments = [c for c in json.load(open(f"{out}/gh-new-comments.json")) if c["created_at"] >= started]
json.dump({"new_issues": issues, "changed_existing_issues": changed,
           "new_comments": [{"id": c["id"], "issue_url": c["issue_url"], "body": c["body"]} for c in comments]},
          open(f"{out}/github.json", "w"), indent=2)
for c in comments:
    if int(c["issue_url"].rsplit("/", 1)[1]) not in new:
        subprocess.run(["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/comments/{c['id']}"], check=True)
for n in new:
    subprocess.run(["gh", "issue", "delete", str(n), "-R", repo, "--yes"], check=True, capture_output=True)
EOF
for kind in prs.json branches.txt releases.txt; do
  cmp -s "$out/gh-before-$kind" "$out/gh-after-$kind" || echo "GitHub $kind changed" >> "$out/github-alerts.txt"
done
echo "done: $out"

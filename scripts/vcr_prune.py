"""Prune Vercel container registry images that no live deployment runs.

Vercel's container registry caps at 50 images per repository, and every
deployment pushes a commit-SHA-tagged image into `frontend` and `backend` that
nothing deletes. A full repository fails every later deployment at the push
step (docs/agencx/deploy.md, Step 6).

An image is kept when its tag matches the commit of:
- one of the newest KEEP_DEPLOYS READY production deployments (live + rollback),
- one of the newest KEEP_DEPLOYS READY development previews,
- any deployment still building (its image may have just been pushed).

"Newest N images" is not safe here: development can take many pushes between
staging syncs, which would prune the image production is serving, and its
next cold start would fail.

Stdlib only. Dry run by default; --apply deletes. Needs VERCEL_TOKEN,
VERCEL_PROJECT and VERCEL_TEAM in the environment.
"""

import json
import os
import sys
import urllib.request

API = "https://api.vercel.com"
REPOS = ("frontend", "backend")
KEEP_DEPLOYS = 3
IN_FLIGHT = {"BUILDING", "QUEUED", "INITIALIZING"}


def call(method: str, path: str, **query: str) -> dict:
    query["teamId"] = os.environ["VERCEL_TEAM"]
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    req = urllib.request.Request(
        f"{API}{path}?{qs}",
        method=method,
        headers={"Authorization": f"Bearer {os.environ['VERCEL_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
    return json.loads(body) if body else {}


def live_tags(project: str) -> set[str]:
    deploys = call("GET", "/v6/deployments", projectId=project, limit="100")["deployments"]
    tags: set[str] = set()
    prod = preview = 0
    for d in deploys:  # newest first
        meta = d.get("meta", {})
        sha = meta.get("githubCommitSha", "")[:12]
        ready = d["state"] == "READY"
        if not sha:
            continue
        if d["state"] in IN_FLIGHT:
            tags.add(sha)
        elif ready and d.get("target") == "production" and prod < KEEP_DEPLOYS:
            tags.add(sha)
            prod += 1
        elif ready and meta.get("githubCommitRef") == "development" and preview < KEEP_DEPLOYS:
            tags.add(sha)
            preview += 1
    return tags


def images(repo: str, project: str) -> list[dict]:
    out: list[dict] = []
    cursor = None
    while True:
        query = {"projectId": project, "limit": "100"}
        if cursor:
            query["cursor"] = cursor
        page = call("GET", f"/v1/vcr/repository/{repo}/images", **query)
        out += page["images"]
        cursor = page.get("nextCursor")
        if not cursor:
            return out


def main() -> None:
    apply = "--apply" in sys.argv[1:]
    project = os.environ["VERCEL_PROJECT"]
    keep = live_tags(project)
    print(f"live commits: {', '.join(sorted(keep)) or 'none'}")
    for repo in REPOS:
        imgs = images(repo, project)
        stale = [i for i in imgs if not keep & set(i.get("tags") or [])]
        verb = "pruning" if apply else "would prune"
        print(f"{repo}: {len(imgs)} images, {verb} {len(stale)}")
        if apply:
            for i in stale:
                call("DELETE", f"/v1/vcr/repository/{repo}/images/{i['id']}", projectId=project)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Discover, safety-check and verify public SubConverter INI presets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "bassdrum007/X")
MANIFEST_PATH = os.environ.get("MANIFEST_PATH", "converter-presets.json")
CONVERTER_URL = os.environ.get("CONVERTER_URL", "https://converter.007e.icu/subconverter/sub")
TEST_SUBSCRIPTION = os.environ.get(
    "TEST_SUBSCRIPTION",
    "https://raw.githubusercontent.com/bassdrum007/X/refs/heads/master/converter-test-subscription.yaml",
)
MAX_DISCOVERED = int(os.environ.get("MAX_DISCOVERED", "6"))
MIN_STARS = int(os.environ.get("MIN_STARS", "0"))
MAX_REPO_AGE_DAYS = int(os.environ.get("MAX_REPO_AGE_DAYS", "365"))
MAX_FILE_AGE_DAYS = int(os.environ.get("MAX_FILE_AGE_DAYS", "180"))
SEARCH_LIMIT = int(os.environ.get("SEARCH_LIMIT", "100"))

SEARCH_QUERIES = [
    '"[custom]" "custom_proxy_group=" extension:ini',
]

EXCLUDED_REPOSITORIES = {
    REPOSITORY.lower(),
    "acl4ssr/acl4ssr",
    "clashconnectrules/clash",
}

UNSAFE_PATTERN = re.compile(
    r"^\s*(?:script|filter_script|rename_node)\s*[:=]|"
    r"\b(?:eval|exec)\s*\(|\bfunction\s*\(|"
    r"^\s*(?:token|password|subscription|subscribe_url)\s*=",
    re.IGNORECASE | re.MULTILINE,
)

NOW = datetime.now(timezone.utc)
CHINA_TZ = timezone(timedelta(hours=8))


def api_request(url: str, *, accept: str = "application/vnd.github+json", timeout: int = 25):
    headers = {
        "Accept": accept,
        "User-Agent": "007e-converter-preset-discovery/2.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if "raw" not in accept and "json" in (resp.headers.get("Content-Type") or ""):
                    return json.loads(raw.decode("utf-8"))
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503) or attempt == 2:
                raise
            if exc.code == 429:
                retry_after = int(exc.headers.get("Retry-After") or 20)
                time.sleep(min(60, retry_after * (attempt + 1)))
            else:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def github_api(path: str, params: dict | None = None, **kwargs):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return api_request(url, **kwargs)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def stable_presets():
    today = NOW.astimezone(CHINA_TZ).date().isoformat()
    return [
        {
            "id": "z",
            "name": "Z.ini 完整版",
            "description": "稳定方案 · 完整分流，覆盖广告、流媒体、AI 服务与地区节点组。",
            "source_url": "https://raw.githubusercontent.com/bassdrum007/X/refs/heads/master/Z.ini",
            "source_repo": "bassdrum007/X",
            "recommended": True,
            "enabled": True,
            "discovered": False,
            "verified_at": today,
            "updated": today,
        },
        {
            "id": "zz",
            "name": "Zz.ini 精简版",
            "description": "稳定方案 · 精简代理组和规则数量，适合轻量与快速加载。",
            "source_url": "https://raw.githubusercontent.com/bassdrum007/X/refs/heads/master/Zz.ini",
            "source_repo": "bassdrum007/X",
            "recommended": False,
            "enabled": True,
            "discovered": False,
            "verified_at": today,
            "updated": today,
        },
    ]


def search_candidates():
    found = {}
    for query in SEARCH_QUERIES:
        result = github_api("/search/code", {"q": query, "per_page": SEARCH_LIMIT})
        for item in result.get("items", []):
            repo = item.get("repository", {}).get("full_name", "")
            path = item.get("path", "")
            if not repo or not path or repo.lower() in EXCLUDED_REPOSITORIES:
                continue
            found[(repo, path)] = {
                "repo": repo,
                "path": path,
                "contents_url": item.get("url"),
            }
        time.sleep(0.25)
    return list(found.values())


def inspect_candidate(candidate: dict, repo_cache: dict, rejection_stats: dict):
    def reject(reason):
        rejection_stats[reason] = rejection_stats.get(reason, 0) + 1
        return None

    repo = candidate["repo"]
    if repo not in repo_cache:
        repo_cache[repo] = github_api(f"/repos/{repo}")
        time.sleep(0.12)
    meta = repo_cache[repo]
    if meta.get("private") or meta.get("fork") or meta.get("archived") or meta.get("disabled"):
        return reject("repository-disabled")
    stars = int(meta.get("stargazers_count") or 0)
    if stars < MIN_STARS:
        return reject("low-stars")
    pushed_at = parse_date(meta.get("pushed_at"))
    if not pushed_at or (NOW - pushed_at).days > MAX_REPO_AGE_DAYS:
        return reject("stale-repository")

    text = api_request(candidate["contents_url"], accept="application/vnd.github.raw+json")
    if not 300 <= len(text.encode("utf-8")) <= 180_000:
        return reject("invalid-size")
    lower = text.lower()
    if "[custom]" not in lower or UNSAFE_PATTERN.search(text):
        return reject("unsafe-or-not-custom")
    rules = len(re.findall(r"(?im)^\s*(?:ruleset|surge_ruleset)\s*=", text))
    groups = len(re.findall(r"(?im)^\s*custom_proxy_group\s*=", text))
    if rules < 5 or groups < 2:
        return reject("incomplete-structure")

    commits = github_api(f"/repos/{repo}/commits", {"path": candidate["path"], "per_page": 1})
    if not commits:
        return reject("no-file-history")
    commit_date = parse_date(commits[0].get("commit", {}).get("committer", {}).get("date"))
    if not commit_date or (NOW - commit_date).days > MAX_FILE_AGE_DAYS:
        return reject("stale-file")

    branch = meta.get("default_branch") or "main"
    quoted_path = "/".join(urllib.parse.quote(part, safe="") for part in candidate["path"].split("/"))
    source_url = f"https://raw.githubusercontent.com/{repo}/refs/heads/{urllib.parse.quote(branch, safe='')}/{quoted_path}"
    freshness = max(0, MAX_FILE_AGE_DAYS - (NOW - commit_date).days)
    score = min(stars, 500) * 0.08 + freshness * 0.12 + min(rules, 80) * 0.16 + min(groups, 30) * 0.35
    return {
        **candidate,
        "source_url": source_url,
        "stars": stars,
        "rules": rules,
        "groups": groups,
        "commit_date": commit_date,
        "score": round(score, 2),
    }


def verify_with_converter(candidate: dict):
    params = urllib.parse.urlencode(
        {
            "target": "clash",
            "url": TEST_SUBSCRIPTION,
            "config": candidate["source_url"],
            "filename": "auto-discovery-check.yaml",
        }
    )
    req = urllib.request.Request(
        CONVERTER_URL + "?" + params,
        headers={"User-Agent": "007e-preset-verifier/2.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=55) as resp:
            body = resp.read(2_000_000).decode("utf-8", errors="replace")
            proxy_count = int(resp.headers.get("X-Proxy-Count") or 0)
            rule_count = int(resp.headers.get("X-Rule-Provider-Count") or 0)
            direct_count = int(resp.headers.get("X-Rule-Direct-Count") or 0)
        return (
            proxy_count >= 1
            and "\nproxy-groups:" in body
            and "\nrules:" in body
            and rule_count == direct_count
        )
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def preset_from_candidate(candidate: dict):
    stem = candidate["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    slug_base = re.sub(r"[^a-z0-9]+", "-", f"{candidate['repo']}-{stem}".lower()).strip("-")
    digest = hashlib.sha1(f"{candidate['repo']}:{candidate['path']}".encode()).hexdigest()[:7]
    preset_id = f"auto-{slug_base[:42]}-{digest}"
    verified = NOW.astimezone(CHINA_TZ).date().isoformat()
    updated = candidate["commit_date"].astimezone(CHINA_TZ).date().isoformat()
    return {
        "id": preset_id,
        "name": f"{candidate['repo'].split('/')[-1]} · {stem}",
        "description": f"自动发现并验证 · {candidate['rules']} 条规则源 · {candidate['groups']} 个代理组",
        "source_url": candidate["source_url"],
        "source_repo": candidate["repo"],
        "source_path": candidate["path"],
        "stars": candidate["stars"],
        "recommended": False,
        "enabled": True,
        "discovered": True,
        "verified_at": verified,
        "updated": updated,
    }


def main():
    if not TOKEN:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    raw = search_candidates()
    print(f"Discovered {len(raw)} unique search results")
    repo_cache = {}
    rejection_stats = {}
    inspected = []
    for index, candidate in enumerate(raw, start=1):
        try:
            result = inspect_candidate(candidate, repo_cache, rejection_stats)
            if result:
                inspected.append(result)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as exc:
            key = "exception-" + type(exc).__name__
            rejection_stats[key] = rejection_stats.get(key, 0) + 1
            if rejection_stats[key] <= 2:
                print(f"Skipped {candidate['repo']}/{candidate['path']}: {exc}")
            continue
        if index % 25 == 0:
            print(f"Inspected {index}/{len(raw)}; {len(inspected)} passed static checks")

    inspected.sort(key=lambda item: item["score"], reverse=True)
    print("Static rejection summary: " + json.dumps(rejection_stats, ensure_ascii=False, sort_keys=True))
    accepted = []
    used_repos = set()
    for candidate in inspected:
        if candidate["repo"] in used_repos:
            continue
        print(f"Verifying {candidate['repo']}/{candidate['path']} (score {candidate['score']})")
        if verify_with_converter(candidate):
            accepted.append(preset_from_candidate(candidate))
            used_repos.add(candidate["repo"])
            print(f"  accepted ({len(accepted)}/{MAX_DISCOVERED})")
        else:
            print("  rejected by converter validation")
        if len(accepted) >= MAX_DISCOVERED:
            break

    manifest = {
        "version": 2,
        "updated": NOW.astimezone(CHINA_TZ).isoformat(timespec="seconds"),
        "generator": {
            "mode": "github-auto-discovery",
            "searched": len(raw),
            "static_passed": len(inspected),
            "verified": len(accepted),
        },
        "presets": stable_presets() + accepted,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {MANIFEST_PATH}: 2 stable + {len(accepted)} auto-verified presets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

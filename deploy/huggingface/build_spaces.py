#!/usr/bin/env python3
"""Stage the two AAAIR tools as Hugging Face Spaces and, optionally, upload them.

    # stage only (inspect what would be published)
    python deploy/huggingface/build_spaces.py --out /path/to/staging

    # stage and upload; Spaces are created PRIVATE unless --public is given
    python deploy/huggingface/build_spaces.py --out /path/to/staging --upload

Uploading needs huggingface_hub and a login (`hf auth login`) with a write token.

Spaces created:
    <user>/aaair-dataset-explorer   Docker Space (WP2 Flask app)
    <user>/aaair-course-finder      static Space (WP6.4 prototypes)

Only allowlisted files are staged, mirroring the Dockerfile.dockerignore files
in WP2/deploy and WP6/deploy: anything staged becomes downloadable by anyone
who can see the Space.
"""
import argparse
import gzip
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WP2 = REPO / "WP2"
WP6 = REPO / "WP6"
WP64 = WP6 / "06 Resources & Training (WP6)" / "WP6.4"

EXPLORER = "aaair-dataset-explorer"
COURSES = "aaair-course-finder"


def gzip_to(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f, gzip.open(dst, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)


def stage_explorer(out: Path) -> None:
    app = out / "app"
    app.mkdir(parents=True)
    hf = WP2 / "deploy" / "huggingface"
    shutil.copy2(hf / "Dockerfile", out / "Dockerfile")
    shutil.copy2(hf / "README.md", out / "README.md")
    shutil.copy2(WP2 / "deploy" / "requirements.txt", out / "requirements.txt")
    for name in ("index.html", "app.js", "data.js", "style.css"):
        shutil.copy2(WP2 / name, app / name)
    # hosting versions, as in WP2/deploy/Dockerfile
    for name in ("api.py", "schema.html"):
        shutil.copy2(WP2 / "deploy" / "app" / name, app / name)

    gzip_to(WP2 / "schema.json", app / "schema.json.gz")
    reports = sorted((WP2 / "dqd" / "raw").glob("*.json"))
    for p in reports:
        gzip_to(p, app / "dqd" / "raw" / (p.name + ".gz"))

    schema = json.loads((WP2 / "schema.json").read_text(encoding="utf-8"))
    keep = {v["url"].rsplit("/", 1)[-1] for v in schema.values() if v.get("source") == "PHIDU"}
    (app / "phidu_data").mkdir()
    missing = []
    for name in sorted(keep):
        src = WP2 / "phidu_data" / name
        if src.exists():
            shutil.copy2(src, app / "phidu_data" / name)
        else:
            missing.append(name)
    print(f"explorer: {len(reports)} DQD reports, {len(keep) - len(missing)} PHIDU spreadsheets"
          + (f", missing {missing}" if missing else ""))


def stage_courses(out: Path) -> None:
    out.mkdir(parents=True)
    shutil.copy2(WP6 / "deploy" / "huggingface" / "README.md", out / "README.md")
    shutil.copy2(WP6 / "deploy" / "index.html", out / "index.html")
    for name in ("Wizard_prototype1.html", "dashboard_prototype1.html", "dashboard_prototype2.html"):
        shutil.copy2(WP64 / name, out / name)
    print("courses: landing page and 3 prototypes")


def size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def upload(out: Path, public: bool) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    user = api.whoami()["name"]
    for name, sdk in ((EXPLORER, "docker"), (COURSES, "static")):
        repo_id = f"{user}/{name}"
        api.create_repo(repo_id, repo_type="space", space_sdk=sdk, private=not public, exist_ok=True)
        info = api.space_info(repo_id)
        if info.private == public:
            sys.exit(f"{repo_id} already exists with private={info.private}; "
                     "change its visibility on the website first, then rerun.")
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=out / name,
                          commit_message="Publish from AAAIR repository", delete_patterns=["*"])
        print(f"uploaded {repo_id} (private={info.private}): https://huggingface.co/spaces/{repo_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path, help="empty or missing staging directory")
    ap.add_argument("--upload", action="store_true", help="upload after staging")
    ap.add_argument("--public", action="store_true", help="create Spaces as public (default private)")
    a = ap.parse_args()

    if a.out.exists() and any(a.out.iterdir()):
        sys.exit(f"{a.out} is not empty; give an empty or new directory")
    stage_explorer(a.out / EXPLORER)
    stage_courses(a.out / COURSES)
    for name in (EXPLORER, COURSES):
        print(f"{name}: {size_mb(a.out / name):.1f} MB staged")
    if a.upload:
        upload(a.out, a.public)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate docs/api-contract.md from the LIVE FastAPI /openapi.json.

Section 4 of the project brief: Backend Agent owns the contract, Frontend Agent
reads it and never invents endpoint shapes. Generating it from the running app
means the contract cannot silently drift from the implementation - if they
disagree, regenerating shows the diff in git.

Usage (backend must be up):
    python scripts/generate_api_contract.py
    python scripts/generate_api_contract.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "api-contract.md"


def fetch(url: str) -> dict:
    try:
        with urllib.request.urlopen(f"{url}/openapi.json", timeout=10) as r:
            if r.status != 200:
                sys.exit(f"ERROR: {url}/openapi.json returned HTTP {r.status}")
            return json.load(r)
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(
            f"ERROR: could not reach {url}/openapi.json ({exc}).\n"
            "Start the backend first:  docker compose up -d backend"
        )


def resolve(schema: dict, spec: dict, depth: int = 0) -> str:
    """Render a (possibly $ref'd) schema as a short type string."""
    if depth > 4:
        return "..."
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return name
    if "anyOf" in schema:
        return " | ".join(resolve(s, spec, depth + 1) for s in schema["anyOf"])
    t = schema.get("type", "object")
    if t == "array":
        return f"{resolve(schema.get('items', {}), spec, depth + 1)}[]"
    return t


def render_schema_table(name: str, schema: dict, spec: dict) -> list[str]:
    lines = [f"#### `{name}`", "", "| Field | Type | Required |", "|---|---|---|"]
    required = set(schema.get("required", []))
    props = schema.get("properties", {})
    if not props:
        lines.append("| _(no properties)_ | | |")
    for field, sub in props.items():
        lines.append(
            f"| `{field}` | `{resolve(sub, spec, 0)}` | "
            f"{'yes' if field in required else 'no'} |"
        )
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()

    spec = fetch(args.url)
    info = spec.get("info", {})
    generated = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = [
        "# LevelForge API Contract",
        "",
        "> **GENERATED FILE - do not hand-edit.**",
        "> Regenerate with `python scripts/generate_api_contract.py` while the",
        "> backend is running. Backend Agent owns this file.",
        ">",
        "> **Frontend Agent:** treat this as the single source of truth for",
        "> endpoint shapes. Never invent an endpoint. If something you need is",
        "> missing, ask Backend Agent to add it and regenerate - do not guess.",
        "",
        f"- **API title:** {info.get('title', 'n/a')}",
        f"- **API version:** {info.get('version', 'n/a')}",
        f"- **Generated:** {generated}",
        f"- **Source:** `{args.url}/openapi.json`",
        "",
        "---",
        "",
        "## Endpoints",
        "",
    ]

    for path, methods in sorted(spec.get("paths", {}).items()):
        for method, op in sorted(methods.items()):
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            out.append(f"### `{method.upper()} {path}`")
            out.append("")
            if op.get("summary"):
                out.append(f"**{op['summary']}**")
                out.append("")
            if op.get("description"):
                out.append(op["description"].strip())
                out.append("")
            tags = op.get("tags")
            if tags:
                out.append(f"*Tags:* {', '.join(f'`{t}`' for t in tags)}")
                out.append("")

            params = op.get("parameters", [])
            if params:
                out += ["| Param | In | Type | Required |", "|---|---|---|---|"]
                for p in params:
                    out.append(
                        f"| `{p['name']}` | {p['in']} | "
                        f"`{resolve(p.get('schema', {}), spec)}` | "
                        f"{'yes' if p.get('required') else 'no'} |"
                    )
                out.append("")

            body = op.get("requestBody")
            if body:
                for ct, media in body.get("content", {}).items():
                    out.append(
                        f"*Request body* (`{ct}`): "
                        f"`{resolve(media.get('schema', {}), spec)}`"
                    )
                out.append("")

            out += ["| Status | Description |", "|---|---|"]
            for code, resp in sorted(op.get("responses", {}).items()):
                out.append(f"| `{code}` | {resp.get('description', '')} |")
            out += ["", "---", ""]

    schemas = spec.get("components", {}).get("schemas", {})
    if schemas:
        out += ["## Schemas", ""]
        for name, schema in sorted(schemas.items()):
            out += render_schema_table(name, schema, spec)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out))
    n_paths = len(spec.get("paths", {}))
    print(f"Wrote {OUT.relative_to(REPO_ROOT)} ({n_paths} paths, {len(schemas)} schemas)")


if __name__ == "__main__":
    main()

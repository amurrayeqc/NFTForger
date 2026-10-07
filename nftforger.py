"""Validate, build, and verify ERC-721 metadata collections."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

class ForgeError(ValueError):
    """A collection cannot be built or verified safely."""

def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeError(f"Unable to read collection config: {exc}") from exc
    if not isinstance(config, dict) or not isinstance(config.get("collection"), dict) or not isinstance(config.get("items"), list):
        raise ForgeError("Config requires collection object and items array")
    collection = config["collection"]
    if not str(collection.get("name", "")).strip() or not str(collection.get("description", "")).strip():
        raise ForgeError("Collection name and description are required")
    if not config["items"]:
        raise ForgeError("Collection must contain at least one item")
    return config

def validate_item(item: Any, seen: set[int]) -> tuple[int, str]:
    if not isinstance(item, dict):
        raise ForgeError("Every item must be an object")
    token_id = item.get("token_id")
    if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
        raise ForgeError("token_id must be a non-negative integer")
    if token_id in seen:
        raise ForgeError(f"Duplicate token_id: {token_id}")
    seen.add(token_id)
    if not str(item.get("name", "")).strip():
        raise ForgeError(f"Item {token_id} requires a name")
    image = item.get("image")
    if not isinstance(image, str) or not image.strip() or Path(image).is_absolute() or ".." in Path(image).parts:
        raise ForgeError(f"Item {token_id} has an unsafe image path")
    attributes = item.get("attributes", [])
    if not isinstance(attributes, list) or any(not isinstance(attr, dict) or "trait_type" not in attr or "value" not in attr for attr in attributes):
        raise ForgeError(f"Item {token_id} attributes require trait_type and value")
    return token_id, image

class NFTForger:
    def forge(self, config_path: Path, assets_dir: Path, output_dir: Path, image_base_uri: str = "images", force: bool = False) -> dict[str, Any]:
        config_path, assets_dir, output_dir = Path(config_path), Path(assets_dir), Path(output_dir)
        config = load_config(config_path)
        if not assets_dir.is_dir():
            raise ForgeError(f"Assets directory does not exist: {assets_dir}")
        if output_dir.exists() and not force:
            raise ForgeError(f"Output already exists: {output_dir}; pass --force to replace it")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
        try:
            (staging / "images").mkdir(); (staging / "metadata").mkdir()
            seen: set[int] = set(); files: dict[str, str] = {}; tokens = []
            assets_root = assets_dir.resolve()
            for item in sorted(config["items"], key=lambda entry: entry.get("token_id", -1) if isinstance(entry, dict) else -1):
                token_id, image_name = validate_item(item, seen)
                source = (assets_dir / image_name).resolve()
                if not source.is_relative_to(assets_root) or not source.is_file() or source.is_symlink():
                    raise ForgeError(f"Item {token_id} image is missing or unsafe: {image_name}")
                destination = staging / "images" / image_name
                destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, destination)
                metadata = {
                    "name": item["name"],
                    "description": item.get("description", config["collection"]["description"]),
                    "image": f"{image_base_uri.rstrip('/')}/{Path(image_name).as_posix()}",
                    "attributes": item.get("attributes", []),
                    **({"external_url": item["external_url"]} if item.get("external_url") else {}),
                    **({"animation_url": item["animation_url"]} if item.get("animation_url") else {}),
                }
                metadata_path = staging / "metadata" / f"{token_id}.json"
                metadata_path.write_bytes(canonical_json(metadata))
                files[str(destination.relative_to(staging))] = sha256(destination)
                files[str(metadata_path.relative_to(staging))] = sha256(metadata_path)
                tokens.append({"token_id": token_id, "metadata": f"metadata/{token_id}.json", "image": f"images/{Path(image_name).as_posix()}"})
            manifest = {"schema": SCHEMA_VERSION, "collection": config["collection"], "configSha256": sha256(config_path), "tokens": tokens, "files": dict(sorted(files.items()))}
            (staging / "manifest.json").write_bytes(canonical_json(manifest))
            if output_dir.exists(): shutil.rmtree(output_dir)
            staging.rename(output_dir)
            return {"output": str(output_dir), "tokens": len(tokens), "files": len(files), "manifestSha256": sha256(output_dir / "manifest.json")}
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def verify(self, output_dir: Path) -> dict[str, Any]:
        output_dir = Path(output_dir)
        try: manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise ForgeError(f"Unable to read manifest: {exc}") from exc
        if manifest.get("schema") != SCHEMA_VERSION or not isinstance(manifest.get("files"), dict): raise ForgeError("Unsupported or invalid manifest")
        failures = []
        for relative, expected in manifest["files"].items():
            path = output_dir / relative
            if Path(relative).is_absolute() or ".." in Path(relative).parts: failures.append({"file": relative, "error": "unsafe path"})
            elif not path.is_file(): failures.append({"file": relative, "error": "missing"})
            elif sha256(path) != expected: failures.append({"file": relative, "error": "hash mismatch"})
        return {"valid": not failures, "tokens": len(manifest.get("tokens", [])), "files": len(manifest["files"]), "failures": failures}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forge and verify ERC-721 metadata collections")
    commands = parser.add_subparsers(dest="command", required=True)
    forge = commands.add_parser("forge"); forge.add_argument("--config", type=Path, required=True); forge.add_argument("--assets", type=Path, required=True); forge.add_argument("--output", type=Path, required=True); forge.add_argument("--image-base-uri", default="images"); forge.add_argument("--force", action="store_true")
    verify = commands.add_parser("verify"); verify.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = NFTForger().forge(args.config, args.assets, args.output, args.image_base_uri, args.force) if args.command == "forge" else NFTForger().verify(args.output)
        print(json.dumps(result, indent=2)); return 0 if result.get("valid", True) else 2
    except ForgeError as exc: print(json.dumps({"error": str(exc)}), file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())

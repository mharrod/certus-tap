"""Manifest parsing helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ManifestProfileConfig:
    """Resolved manifest/profile information."""

    product: str | None
    version: str | None
    profile_name: str
    tools: list[str]
    digest: str | None
    thresholds: dict[str, int]
    requires_stack: bool
    raw_manifest: dict[str, Any]
    raw_profile: dict[str, Any]


def load_manifest_from_path(path: str, profile_name: str) -> ManifestProfileConfig:
    """Load manifest JSON from filesystem path."""
    manifest_path = Path(path)
    raw_text = manifest_path.read_text(encoding="utf-8")
    return _parse_manifest(raw_text, profile_name)


def load_manifest_from_json(raw_text: str, profile_name: str) -> ManifestProfileConfig:
    """Load manifest JSON from pre-read text."""
    return _parse_manifest(raw_text, profile_name)


def _parse_manifest(raw_text: str, profile_name: str) -> ManifestProfileConfig:
    manifest_data = json.loads(raw_text)
    products = manifest_data.get("profiles", []) or []
    profile = _find_profile(products, profile_name)
    tools = _extract_tools(profile)
    thresholds = _extract_thresholds(profile.get("thresholds"))
    requires_stack = bool(profile.get("requiresStack", False))
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return ManifestProfileConfig(
        product=manifest_data.get("product"),
        version=manifest_data.get("version"),
        profile_name=profile.get("name", profile_name),
        tools=tools,
        digest=digest,
        thresholds=thresholds,
        requires_stack=requires_stack,
        raw_manifest=manifest_data,
        raw_profile=profile,
    )


def _find_profile(profiles: list[dict[str, Any]], requested: str) -> dict[str, Any]:
    if not profiles:
        raise ValueError("manifest is missing 'profiles' entries")

    requested_lower = requested.lower()
    for entry in profiles:
        name = str(entry.get("name", "")).strip()
        if name.lower() == requested_lower:
            return entry

    available = ", ".join(entry.get("name", "<unknown>") for entry in profiles)
    raise ValueError(f"manifest profile '{requested}' not found. Available profiles: {available}")


def _extract_tools(profile: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for tool_entry in profile.get("tools", []):
        if isinstance(tool_entry, str):
            tools.append(tool_entry)
        elif isinstance(tool_entry, dict):
            tool_id = tool_entry.get("id") or tool_entry.get("name")
            if tool_id:
                tools.append(str(tool_id))
    return tools


def _extract_thresholds(raw_thresholds: Any) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if isinstance(raw_thresholds, dict):
        for key, value in raw_thresholds.items():
            try:
                normalized[str(key).lower()] = int(value)
            except (TypeError, ValueError):
                continue
    return normalized

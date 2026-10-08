#!/usr/bin/env python3
"""Resolve Hybrid Conductor configuration without executing model/agent values."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

DEFAULTS = Path(__file__).resolve().parents[1] / "assets" / "defaults.json"
ROLES = {"main", "planner", "worker", "researcher", "reviewer", "designer"}
EFFORTS = {"inherit", "none", "minimal", "low", "medium", "high", "xhigh", "max"}


class ConfigError(ValueError):
    """A readable, deterministic configuration error."""


def read_object(path: Path) -> dict[str, Any]:
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ConfigError(f"{path}: duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ConfigError(f"{path}: non-JSON numeric value {value}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=unique_keys,
                           parse_constant=invalid_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: top level must be an object")
    return value


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge objects recursively; replace other values; never mutate inputs."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def exact_keys(value: Any, required: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: expected an object")
    missing, extra = required - value.keys(), value.keys() - required
    if missing or extra:
        raise ConfigError(f"{path}: missing={sorted(missing)}, unknown={sorted(extra)}")


def nonempty_string(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{path}: expected a nonempty string")
    if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ConfigError(f"{path}: surrounding whitespace/control characters are not allowed")


def validate(config: dict[str, Any]) -> None:
    exact_keys(config, {"schema_version", "roles", "parallelism", "execution"}, "config")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ConfigError("schema_version: only integer 1 is supported")
    exact_keys(config["roles"], ROLES, "roles")
    for name, role in config["roles"].items():
        prefix = f"roles.{name}"
        exact_keys(role, {"agent", "model", "effort"}, prefix)
        for key in ("agent", "model", "effort"):
            nonempty_string(role[key], f"{prefix}.{key}")
        agents = {"codex", "claude", "inherit"} if name == "main" else {"codex", "claude"}
        if role["agent"] not in agents:
            raise ConfigError(f"{prefix}.agent: expected one of {sorted(agents)}")
        if name != "main" and role["model"] == "inherit":
            raise ConfigError(f"{prefix}.model: choose an explicit model; do not inherit main's model")
        if role["effort"] not in EFFORTS:
            raise ConfigError(f"{prefix}.effort: expected one of {sorted(EFFORTS)}")
    exact_keys(config["parallelism"], {"workers", "researchers"}, "parallelism")
    for name, value in config["parallelism"].items():
        if type(value) is not int or value < 1:
            raise ConfigError(f"parallelism.{name}: expected a positive integer")
    exact_keys(config["execution"], {"adapter", "allow_worktrees"}, "execution")
    if not isinstance(config["execution"]["adapter"], str) or config["execution"]["adapter"] not in {"herdr", "pi"}:
        raise ConfigError("execution.adapter: expected herdr or pi")
    if type(config["execution"]["allow_worktrees"]) is not bool:
        raise ConfigError("execution.allow_worktrees: expected a boolean")


def user_config_default() -> Path:
    value = os.environ.get("XDG_CONFIG_HOME")
    if value:
        base = Path(value).expanduser()
        if not base.is_absolute():
            raise ConfigError("XDG_CONFIG_HOME must be an absolute path")
    else:
        base = Path.home() / ".config"
    return base / "hybrid-conductor" / "config.json"


def discover_project(cwd: Path) -> Path:
    """Use the current Git worktree root, otherwise the current directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cwd.resolve()
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return cwd.resolve()


def load_config(project: Path, user_config: Path | None = None,
                overrides: list[Path] | None = None) -> tuple[dict[str, Any], list[str]]:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ConfigError(f"Project directory does not exist: {project}")
    layers: list[tuple[Path, bool]] = [(DEFAULTS, True)]
    layers.append((user_config.expanduser() if user_config else user_config_default(),
                   user_config is not None))
    layers.append((project / ".hybrid-conductor.json", False))
    layers.extend((path.expanduser(), True) for path in (overrides or []))
    config: dict[str, Any] = {}
    sources: list[str] = []
    for path, required in layers:
        # A broken link is a malformed config, not an absent optional config.
        if not path.exists() and not path.is_symlink() and not required:
            continue
        config = deep_merge(config, read_object(path))
        # Validate each layer so an invalid lower-priority file cannot be hidden.
        validate(config)
        sources.append(str(path.resolve()))
    return config, sources


DELEGATED_ROLES = ("planner", "worker", "reviewer", "researcher", "designer")


def setup_status(config: dict[str, Any], sources: list[str], *, adapter: str,
                 project: Path, pi_user_settings: Path | None = None,
                 pi_project_settings: Path | None = None) -> dict[str, Any]:
    """Distinguish explicit role choices from recommendations; never write settings."""
    explicit: dict[str, Any] = {}
    settings_sources: list[str] = []
    if adapter == "herdr":
        # Defaults are recommendations, not evidence of operator setup.
        for source in sources:
            if Path(source).resolve() != DEFAULTS.resolve():
                explicit = deep_merge(explicit, read_object(Path(source)).get("roles", {}))
    else:
        paths = [
            (pi_user_settings or Path.home() / ".pi/agent/settings.json", pi_user_settings is not None),
            (pi_project_settings or project / ".pi/settings.json", pi_project_settings is not None),
        ]
        for path, required in paths:
            path = path.expanduser()
            if not path.exists() and not path.is_symlink() and not required:
                continue
            settings = read_object(path)
            subagents = settings.get("subagents", {})
            if not isinstance(subagents, dict):
                raise ConfigError(f"{path}: subagents must be an object")
            overrides = subagents.get("agentOverrides", {})
            if not isinstance(overrides, dict):
                raise ConfigError(f"{path}: agentOverrides must be an object")
            for role in DELEGATED_ROLES:
                name = f"hybrid-conductor.{role}"
                if name in overrides:
                    value = overrides[name]
                    if not isinstance(value, dict):
                        raise ConfigError(f"{path}: {name} override must be an object")
                    if "model" in value:
                        nonempty_string(value["model"], f"{path}: {name}.model")
                        if value["model"] == "inherit":
                            raise ConfigError(f"{path}: {name} must choose an explicit model")
                    if "thinking" in value and value["thinking"] is not False and (not isinstance(value["thinking"], str) or value["thinking"] not in {
                            "off", "minimal", "low", "medium", "high", "xhigh", "max"}):
                        raise ConfigError(f"{path}: {name}.thinking is unsupported")
                    explicit[role] = deep_merge(explicit.get(role, {}), value)
            settings_sources.append(str(path.resolve()))
    missing = [role for role in DELEGATED_ROLES if "model" not in explicit.get(role, {})]
    disabled = [role for role in DELEGATED_ROLES if explicit.get(role, {}).get("disabled") is True]
    recommendations = read_object(DEFAULTS)["roles"]
    return {"adapter": adapter, "required": bool(missing or disabled),
            "missing_roles": missing, "disabled_roles": disabled,
            "explicit_roles": explicit, "settings_sources": settings_sources,
            "recommendations": {role: recommendations[role]
                                for role in DELEGATED_ROLES}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, help="Explicit project root (default: Git root or cwd)")
    parser.add_argument("--user-config", type=Path, help="Use this user config; it must exist")
    parser.add_argument("--overrides", action="append", type=Path, default=[],
                        help="Per-run JSON override; repeatable, last file wins")
    parser.add_argument("--check-setup", action="store_true",
                        help="Check all explicit role models; exit 3 if setup is required")
    parser.add_argument("--adapter", choices=("herdr", "pi"), help="Active execution adapter")
    parser.add_argument("--pi-user-settings", type=Path, help="Exact native Pi user settings file")
    parser.add_argument("--pi-project-settings", type=Path, help="Exact native Pi project settings file")
    args = parser.parse_args(argv)
    try:
        project = args.project if args.project is not None else discover_project(Path.cwd())
        config, sources = load_config(project, args.user_config, args.overrides)
        if args.adapter:
            config["execution"]["adapter"] = args.adapter
        payload = {"config": config, "sources": sources}
        if args.check_setup:
            payload["setup"] = setup_status(
                config, sources, adapter=config["execution"]["adapter"],
                project=project.expanduser().resolve(),
                pi_user_settings=args.pi_user_settings,
                pi_project_settings=args.pi_project_settings)
    except (ConfigError, OSError) as exc:
        print(f"hybrid-conductor: {exc}", file=sys.stderr)
        return 2
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 3 if args.check_setup and payload["setup"]["required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

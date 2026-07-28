"""Tests for deployment artifacts.

These tests do not perform a full deployment; they verify that the shell
script, Dockerfile and systemd service file are syntactically valid and
contain the expected deployment steps.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]


def test_deploy_sh_is_executable():
    """deploy.sh should exist and be executable."""
    deploy_sh = PROJECT_ROOT / "deploy.sh"
    assert deploy_sh.exists()
    assert deploy_sh.stat().st_mode & 0o111, "deploy.sh should be executable"


def test_deploy_sh_syntax():
    """bash -n should report no syntax errors in deploy.sh."""
    deploy_sh = PROJECT_ROOT / "deploy.sh"
    result = subprocess.run(
        ["bash", "-n", str(deploy_sh)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_deploy_sh_contains_required_steps():
    """deploy.sh should install deps, run tests, start server and health check."""
    deploy_sh = PROJECT_ROOT / "deploy.sh"
    content = deploy_sh.read_text(encoding="utf-8")
    assert "pip install" in content
    assert "pytest" in content
    assert "uvicorn" in content
    assert "scenario/meta" in content
    assert "curl" in content


def test_dockerfile_exists_and_has_required_instructions():
    """Dockerfile should contain build and runtime instructions."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM" in content
    assert "EXPOSE" in content
    assert "uvicorn" in content
    # The task explicitly forbids Docker volume declarations.
    assert "\nVOLUME " not in content.upper()


def test_systemd_service_exists_and_has_required_sections():
    """csqaq-scenario.service should be a valid systemd unit template."""
    service = PROJECT_ROOT / "csqaq-scenario.service"
    assert service.exists()
    content = service.read_text(encoding="utf-8")
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    assert "ExecStart" in content
    assert "run_scenario_server" in content

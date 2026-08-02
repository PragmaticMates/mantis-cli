"""Tests for build configuration read out of compose files."""
import textwrap

import pytest

from mantis.managers import BaseManager


def _manager_with_compose(tmp_path, compose_yaml):
    """A manager wired to a single compose file, without running __init__."""
    compose_file = tmp_path / "project.yml"
    compose_file.write_text(textwrap.dedent(compose_yaml))

    manager = BaseManager.__new__(BaseManager)
    manager.compose_files = [str(compose_file)]
    return manager


class TestServicesToBuild:
    """Tests for services_to_build parsing of the compose build section."""

    def test_cache_from_and_cache_to_are_read(self, tmp_path):
        """Both cache keys come through from the compose build section."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: ../..
                  dockerfile: ./Dockerfile
                  cache_from:
                    - type=registry,ref=acme/app:production
                  cache_to:
                    - type=inline
        """)

        info = manager.services_to_build()["backend"]

        assert info["cache_from"] == ["type=registry,ref=acme/app:production"]
        assert info["cache_to"] == ["type=inline"]

    def test_cache_keys_default_to_empty(self, tmp_path):
        """A build section naming neither key yields empty lists, not None."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: .
        """)

        info = manager.services_to_build()["backend"]

        assert info["cache_from"] == []
        assert info["cache_to"] == []

    def test_multiple_cache_entries(self, tmp_path):
        """Several sources or destinations are all preserved, in order."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: .
                  cache_from:
                    - type=registry,ref=acme/app:buildcache
                    - type=registry,ref=acme/app:production
                  cache_to:
                    - type=registry,ref=acme/app:buildcache,mode=max
        """)

        info = manager.services_to_build()["backend"]

        assert info["cache_from"] == [
            "type=registry,ref=acme/app:buildcache",
            "type=registry,ref=acme/app:production",
        ]
        assert info["cache_to"] == ["type=registry,ref=acme/app:buildcache,mode=max"]

    def test_services_without_build_are_skipped(self, tmp_path):
        """Only services that declare a build section are returned."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: .
              db:
                image: postgres:18
        """)

        assert list(manager.services_to_build().keys()) == ["backend"]


class TestBuildCommand:
    """Tests that the cache flags reach the docker build command."""

    @staticmethod
    def _capture(manager):
        """Record the commands build() would run instead of running them."""
        commands = []
        manager.config = {"build": {"tool": "docker", "args": {}}}
        manager.compose_path = "."
        manager.docker = lambda command, **kwargs: commands.append(command)
        return commands

    def test_both_cache_flags_are_emitted(self, tmp_path):
        """cache_from and cache_to each become a flag on docker build."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: .
                  dockerfile: ./Dockerfile
                  cache_from:
                    - type=registry,ref=acme/app:production
                  cache_to:
                    - type=inline
        """)
        commands = self._capture(manager)

        manager.build()

        assert len(commands) == 1
        assert "--cache-from type=registry,ref=acme/app:production" in commands[0]
        assert "--cache-to type=inline" in commands[0]

    def test_absent_cache_keys_emit_no_flags(self, tmp_path):
        """No cache config means neither flag appears at all."""
        manager = _manager_with_compose(tmp_path, """
            services:
              backend:
                image: acme/app:production
                build:
                  context: .
        """)
        commands = self._capture(manager)

        manager.build()

        assert "--cache-from" not in commands[0]
        assert "--cache-to" not in commands[0]

"""Tests for helpers module - config default merging."""
import pytest

from mantis.config import load_template_config
from mantis.helpers import merge_defaults


class TestMergeDefaults:
    """Tests for merge_defaults function."""

    def test_partial_section_keeps_sibling_defaults(self):
        """Declaring one key of a section must not drop the rest of it."""
        defaults = {'compose': {'command': 'docker-compose', 'folder': '<MANTIS>/../compose'}}
        overrides = {'compose': {'command': 'docker compose'}}

        merged = merge_defaults(defaults, overrides)

        assert merged['compose'] == {
            'command': 'docker compose',
            'folder': '<MANTIS>/../compose',
        }

    def test_override_wins_over_default(self):
        """User values replace defaults of the same key."""
        defaults = {'project_path': '~', 'compose': {'command': 'docker-compose'}}
        overrides = {'project_path': '~/public_html/app/', 'compose': {'command': 'docker compose'}}

        merged = merge_defaults(defaults, overrides)

        assert merged['project_path'] == '~/public_html/app/'
        assert merged['compose']['command'] == 'docker compose'

    def test_untouched_sections_survive(self):
        """Sections the user never mentions keep their defaults."""
        defaults = {
            'compose': {'command': 'docker-compose'},
            'encryption': {'deterministic': True, 'folder': '<MANTIS>'},
        }
        overrides = {'compose': {'command': 'docker compose'}}

        merged = merge_defaults(defaults, overrides)

        assert merged['encryption'] == {'deterministic': True, 'folder': '<MANTIS>'}

    def test_lists_are_replaced_not_concatenated(self):
        """zero_downtime must be the user's list, not defaults + user."""
        defaults = {'zero_downtime': ['web']}
        overrides = {'zero_downtime': ['backend']}

        merged = merge_defaults(defaults, overrides)

        assert merged['zero_downtime'] == ['backend']

    def test_new_keys_are_added(self):
        """Keys absent from the defaults come through."""
        defaults = {'project_path': '~'}
        overrides = {'connections': {'production': 'ssh://user@host:22'}}

        merged = merge_defaults(defaults, overrides)

        assert merged['connections'] == {'production': 'ssh://user@host:22'}
        assert merged['project_path'] == '~'

    def test_nested_dicts_recurse(self):
        """Merging descends more than one level."""
        defaults = {'build': {'tool': 'compose', 'args': {'a': '1', 'b': '2'}}}
        overrides = {'build': {'args': {'b': '99'}}}

        merged = merge_defaults(defaults, overrides)

        assert merged['build'] == {'tool': 'compose', 'args': {'a': '1', 'b': '99'}}

    def test_scalar_replacing_dict(self):
        """A scalar override replaces a dict default rather than recursing."""
        defaults = {'connection': {'nested': True}}
        overrides = {'connection': 'ssh://user@host:22'}

        merged = merge_defaults(defaults, overrides)

        assert merged['connection'] == 'ssh://user@host:22'

    def test_inputs_are_not_mutated(self):
        """Merging must not write back into the template defaults."""
        defaults = {'compose': {'command': 'docker-compose', 'folder': 'x'}}
        overrides = {'compose': {'command': 'docker compose'}}

        merge_defaults(defaults, overrides)

        assert defaults == {'compose': {'command': 'docker-compose', 'folder': 'x'}}

    def test_empty_overrides_returns_defaults(self):
        """No user config means the template stands as-is."""
        defaults = {'compose': {'command': 'docker-compose'}}

        assert merge_defaults(defaults, {}) == defaults


class TestMergeDefaultsAgainstTemplate:
    """Tests merge_defaults against the real mantis.tpl defaults."""

    def test_partial_compose_section_keeps_folder(self):
        """The regression this fixes: compose.command alone used to lose compose.folder."""
        config = {
            'compose': {'command': 'docker compose'},
            'connections': {'production': 'ssh://user@host:2222'},
        }

        merged = merge_defaults(load_template_config(), config)

        assert merged['compose']['command'] == 'docker compose'
        assert merged['compose']['folder'] == '<MANTIS>/../compose'

    def test_every_template_section_survives_a_partial_override(self):
        """Each section with more than one key must tolerate a partial declaration."""
        template = load_template_config()
        sections = {
            key: value for key, value in template.items()
            if isinstance(value, dict) and len(value) > 1
        }

        assert sections, 'template has no multi-key sections to check'

        for section, defaults in sections.items():
            first_key = next(iter(defaults))
            merged = merge_defaults(template, {section: {first_key: defaults[first_key]}})

            assert merged[section].keys() == defaults.keys(), \
                f'partial override of "{section}" dropped keys'

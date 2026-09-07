# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.infra.automation_orchestrator.plugins.plugin_utils.platform.utils import (
    drop_readonly,
    guard_builtin,
    is_uuid,
    sanitize_inputs,
    values_equal,
    walk_rewrite,
)


def test_is_uuid():
    assert is_uuid("123e4567-e89b-12d3-a456-426614174000")
    assert not is_uuid("not-a-uuid")
    assert not is_uuid(None)
    assert not is_uuid(123)


def test_drop_readonly():
    obj = {"id": "abc", "name": "demo", "created_at": "now", "is_builtin": True}
    assert drop_readonly(obj) == {"name": "demo"}


def test_values_equal_treats_none_and_empty_as_equivalent():
    assert values_equal(None, "")
    assert values_equal(None, {})
    assert values_equal(None, [])
    assert values_equal({}, None)
    assert not values_equal(None, "x")


def test_values_equal_nested():
    assert values_equal({"a": [1, 2], "b": None}, {"a": [1, 2], "b": ""})
    assert not values_equal({"a": [1, 2]}, {"a": [1, 3]})


def test_sanitize_inputs_skips_encrypted_placeholder_on_desired():
    desired = {"password": "$encrypted$", "username": "admin"}
    existing = {"password": "$encrypted$", "username": "admin"}
    payload, visible_changed, force_secret_change = sanitize_inputs(desired, existing, update_secrets=True)
    assert payload == {"username": "admin"}
    assert visible_changed is False
    assert force_secret_change is False


def test_sanitize_inputs_forwards_new_secret_when_existing_is_masked():
    desired = {"password": "new-secret", "username": "admin"}
    existing = {"password": "$encrypted$", "username": "admin"}
    payload, visible_changed, force_secret_change = sanitize_inputs(desired, existing, update_secrets=True)
    assert payload == {"username": "admin", "password": "new-secret"}
    assert visible_changed is False
    assert force_secret_change is True


def test_sanitize_inputs_withholds_secret_when_update_secrets_false():
    desired = {"password": "new-secret", "username": "admin"}
    existing = {"password": "$encrypted$", "username": "admin"}
    payload, visible_changed, force_secret_change = sanitize_inputs(desired, existing, update_secrets=False)
    assert payload == {"username": "admin"}
    assert force_secret_change is False


def test_walk_rewrite_converts_name_alias_to_id():
    definition = {"nodes": [{"id": "n1", "credential": "my-cred"}]}
    resolved = "11111111-1111-1111-1111-111111111111"

    def rewriter(id_key, value):
        # walk_rewrite may call the rewriter a second time on an
        # already-resolved id (matching resolve_id()'s idempotent
        # early-return for UUIDs), so it must tolerate both.
        assert id_key == "credential_id"
        assert value in ("my-cred", resolved)
        return resolved

    result = walk_rewrite(definition, rewriter)
    assert result["nodes"][0]["credential_id"] == resolved
    assert "credential" not in result["nodes"][0]


def test_walk_rewrite_skips_alias_already_a_uuid():
    definition = {"credential": "11111111-1111-1111-1111-111111111111"}
    result = walk_rewrite(definition, lambda k, v: (_ for _ in ()).throw(AssertionError("should not be called")))
    # Since it's already a UUID it's treated as a plain field, not an alias to rewrite.
    assert result["credential"] == "11111111-1111-1111-1111-111111111111"


def test_guard_builtin_blocks_builtin_by_default():
    existing = {"id": "abc", "name": "default", "is_builtin": True}
    message = guard_builtin(existing, allow_builtin=False)
    assert message is not None
    assert "default" in message


def test_guard_builtin_allows_when_flag_set():
    existing = {"id": "abc", "name": "default", "is_builtin": True}
    assert guard_builtin(existing, allow_builtin=True) is None


def test_guard_builtin_ignores_non_builtin():
    existing = {"id": "abc", "name": "custom", "is_builtin": False}
    assert guard_builtin(existing, allow_builtin=False) is None

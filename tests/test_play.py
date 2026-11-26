"""Offline checks of the contract ``robodojo.play`` puts at the head of the prompt."""

from __future__ import annotations

from robodojo.arms import arm_contract


def test_the_contract_includes_planning_motion_and_image_context_rules():
    contract = arm_contract(budget_s=60, max_env_steps=100, images="on-primitive")
    assert "## Module 1: Planning and Summary Pattern" in contract
    assert "## Module 2: Planning Principles" in contract
    assert "## Module 3: Motion Rules" in contract
    assert "Plan (before the first tool call" in contract
    assert "Summary (after every tool result)" in contract
    assert "Plan follows planning principles: yes / no / not applicable" in contract
    assert "from opposite sides" in contract
    # the final state comes from the task description, not from a fixed rule
    flat = " ".join(contract.split())
    assert "read the task description for the final state it requires" in flat
    assert "do not open, withdraw or home" in flat
    assert "both arms are home" not in flat and "fully open" not in flat
    assert "### Insertion" in contract
    assert "Only after alignment is confirmed" in contract
    assert "max_context_images" in contract
    assert "head view and both wrist views" not in contract
    assert "vertically downward orientation" not in contract

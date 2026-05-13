from pathlib import Path
import audit_agent


def test_penalty_skill_contains_business_rule():
    text = Path("skills/penalty_logic/SKILL.md").read_text(encoding="utf-8")
    assert "If Days Late > 7" in text
    assert "0.05" in text


def test_agent_builder_loads_penalty_skill(monkeypatch):
    calls = {}

    def fake_create_deep_agent(**kwargs):
        calls.update(kwargs)
        return "agent"

    monkeypatch.setattr(audit_agent, "create_deep_agent", fake_create_deep_agent)
    audit_agent.build_agent("test-model")

    assert calls["skills"] == ["./skills/penalty_logic/"]
    assert "multiply Invoice Amount by 0.05" not in audit_agent.SYSTEM_PROMPT

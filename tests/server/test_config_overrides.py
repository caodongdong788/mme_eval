from medeval.config import parse_config
from server.services.config_overrides import apply_adapter_overrides


def test_cx_agent_rag_override_only_changes_cx_agent_config():
    config = parse_config(
        {
            "adapter": {
                "type": "cx_agent",
                "cx_agent": {"test_token": "test-token", "enable_rag": False},
            }
        }
    )

    apply_adapter_overrides(config, {"enable_rag": True, "model": "ignored"})

    assert config.adapter.cx_agent is not None
    assert config.adapter.cx_agent.enable_rag is True

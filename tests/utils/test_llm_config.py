def test_autogpt_config_accepts_json_string_llm_configs(loaded_plugins):
    from src.core.llm.config import AutoGPTConfig

    config = AutoGPTConfig.parse_obj(
        {
            "llm_configs": """
            [
                {
                    "name": "Gemini",
                    "key": "test-key",
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "model": "gemini-2.5-flash",
                    "proxy": "http://127.0.0.1:7890",
                    "tasks": ["chat", "vision"],
                    "multi_modal": true,
                    "supports_functools": true
                },
            ]
            """,
            "llm_timeout": 60,
        }
    )

    assert len(config.llm_configs) == 1
    assert config.llm_configs[0].name == "Gemini"
    assert config.llm_configs[0].proxy == "http://127.0.0.1:7890"
    assert config.llm_configs[0].multi_modal is True


def test_core_llm_config_imports_from_canonical_entry(loaded_plugins):
    import src.core.llm.config as core_config_module

    assert core_config_module.__name__ == "src.core.llm.config"


def test_autogpt_config_accepts_agent_loop_limits(loaded_plugins):
    from src.core.llm.config import AutoGPTConfig

    config = AutoGPTConfig.parse_obj(
        {
            "agent_loop_max_steps": "6",
            "agent_loop_max_verify_attempts": "3",
            "agent_loop_max_repeat_actions": "2",
            "agent_loop_max_runtime_seconds": "90",
        }
    )

    assert config.agent_loop_max_steps == 6
    assert config.agent_loop_max_verify_attempts == 3
    assert config.agent_loop_max_repeat_actions == 2
    assert config.agent_loop_max_runtime_seconds == 90

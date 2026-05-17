def test_autogpt_config_accepts_json_string_llm_configs(loaded_plugins):
    from core.llm.config import AutoGPTConfig

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
    import core.llm.config as core_config_module

    assert core_config_module.__name__ == "core.llm.config"

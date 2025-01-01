api_config = {
    "OpenAI": {
        "company": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key": "OPENAI_API_KEY",
        "response_text_is_json": True,
        "response_keys": ["choices", 0, "message", "content"],
        "finish_reason": ['choices',0,'finish_reason'],
        "finish_reason_function_call": "tool_calls",
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "system",
        "messages_keys": ["choices",0,"message"],
        "messages_multiple": False,
    },
    "XAI": {
        "company": "XAI",
        "url": "https://api.x.ai/v1/chat/completions",
        "api_key": "X_AI_API_KEY",
        "response_text_is_json": False,
        "tplHeader": '''{"Content-Type": "application/json","Authorization": "Bearer {{ API_KEY }}"}''',
        "finish_reason": ['choices',0,'finish_reason'],
        "finish_reason_function_call": "tool_calls",
        "response_keys": ["choices", 0, "message", "content"],
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "user",
        "messages_keys": ["choices", 0, "message"],
        "messages_multiple": False,
    },
    "MistralAI": {
        "company": "MistralAI",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "api_key": "MISTRAL_API_KEY",
        "response_text_is_json": True,
        "finish_reason": ['choices',0,'finish_reason'],
        "finish_reason_function_call": "tool_calls",
        "response_keys": ["choices", 0, "message", "content"],
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "system",
        "messages_keys": ["choices", 0, "message"],
        "messages_multiple": False,
    },
    "Anthropic": {
        "company": "Anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "api_key": "ANTHROPIC_API_KEY",
        "response_text_is_json": True,
        # "finish_reason": ['stop_reason'],
        # "finish_reason_function_call": "tool_use",
        # "response_keys": ["content", 0, "text"],
        "usage_keys": ["input_tokens", "output_tokens"],
        "system_role": "system",
        # "messages_keys": ["content"],
        # "messages_multiple": True,
    }
}


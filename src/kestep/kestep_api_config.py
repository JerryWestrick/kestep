api_config = {
    "OpenAI": {
        "company": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key": "OPENAI_API_KEY",
        "response_text_is_json": True,
        "tplHeader": '''{"Content-Type": "application/json", "Authorization": "Bearer {{ API_KEY }}"}''',
        "tplSystem": '''{"role":"system", "content": "{{value}}"}''',
        "tplUser": '''{"role":"user", "content": "{{value}}"}''',
        "tplAssistant": '''{"role":"assistant", "content": "{{value}}"}''',
        "tplData": '''{ "model": "{{ model }}","messages":
        [   {% if model == "o1-preview" or model == "o1-mini" %}
                {"role": "user",
                 "content": "Return a command for {{ os_system }} that can be executed by the user. JUST COMMAND. NO COMMENTS, NO EXPLANATIONS, NO QUOTES. For example 'Change directory to my home dir'"},
            {% else %}
                {"role": "system",
                 "content": "Help the user working on {{ os_system }} create a command. JUST COMMAND. NO COMMENTS, NO EXPLANATIONS."},
                {"role": "user", "content": "Change directory to my home dir"},
            {% endif %}
            {"role": "assistant", "content": "cd"},
            {"role": "user", "content": "{{ user_input }}"}
        ]}''',
        "response_keys": ["choices", 0, "message", "content"],
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "system"
    },
    "XAI": {
        "company": "XAI",
        "url": "https://api.x.ai/v1/chat/completions",
        "api_key": "X_AI_API_KEY",
        "response_text_is_json": False,
        "tplHeader": '''{"Content-Type": "application/json","Authorization": "Bearer {{ API_KEY }}"}''',
        "tplData": '''{ "model": "{{ model }}",
                "messages":[
                    {"role": "system",
                     "content": "Help the user working on {{ os_system }} create a command. JUST COMMAND. NO COMMENTS, NO EXPLANATIONS."},
                    {"role": "user", "content": "Change directory to my home dir"},
                    {"role": "assistant", "content": "cd"},
                    {"role": "user", "content": "{{ user_input }}"}
                ]}''',
        "response_keys": ["choices", 0, "message", "content"],
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "user"
    },
    "MistralAI": {
        "company": "Mistralai",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "api_key": "MISTRAL_API_KEY",
        "response_text_is_json": True,
        "tplHeader": '''{"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer {{ API_KEY }}"}''',
        "tplData": '''{ "model": "{{ model }}",
            "messages":
              [ {"role": "system","content": "You are helping a user on {{ os_system }} execute commands. Return the command only. NO QUOTES, NO COMMENTS, NO EXPLANATIONS"},
                {"role": "user","content": "{{ user_input }}"}
              ]}''',
        "response_keys": ["choices", 0, "message", "content"],
        "usage_keys": ["prompt_tokens", "completion_tokens"],
        "system_role": "system"
    },
    "Anthropic": {
        "company": "Anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "api_key": "ANTHROPIC_API_KEY",
        "response_text_is_json": True,
        "tplHeader": '''{"x-api-key": "{{ API_KEY }}", "Content-Type": "application/json","anthropic-version": "2023-06-01"}''',
        "tplData": '''{ "model": "{{ model }}",
             "system": "You are an operator working on {{ os_system }}. List a single command that the user can execute.",
             "max_tokens": 1024,
             "messages":
              [ {"role": "user","content": "Change directory to my home dir"},
                {"role": "assistant","content": "cd"},
                {"role": "user","content": "{{ user_input }}"}
              ]}''',
        "response_keys": ["content", 0, "text"],
        "usage_keys": ["input_tokens", "output_tokens"],
        "system_role": "system"
    }
}

from tree_ui.models import ConversationNode

DEFAULT_MODEL_BY_PROVIDER = {
    ConversationNode.Provider.OPENAI: "gpt-4.1-mini",
    ConversationNode.Provider.GEMINI: "gemini-2.5-flash",
}

LEGACY_MODEL_ALIASES = {
    ConversationNode.Provider.GEMINI: {
        "gemini-2.0-flash": "gemini-2.5-flash",
        "gemini-2.0-pro-exp": "gemini-2.5-pro",
        "gemini-1.5-pro": "gemini-2.5-pro",
    },
}


def resolve_model_name(*, provider: str, model_name: str) -> str:
    clean_name = model_name.strip()
    if not clean_name:
        return DEFAULT_MODEL_BY_PROVIDER[provider]

    return LEGACY_MODEL_ALIASES.get(provider, {}).get(clean_name, clean_name)

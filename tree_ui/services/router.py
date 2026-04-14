from typing import NamedTuple, Optional
from tree_ui.models import ConversationNode

class RoutingResult(NamedTuple):
    provider: str
    model: str
    decision: str

def route_model(
    *,
    routing_mode: str,
    provider: Optional[str] = None,
    has_attachments: bool = False,
    prompt_length: int = 0,
) -> RoutingResult:
    """
    Selects the best model based on routing mode and request signals.
    If 'provider' is specified, the selection is restricted to that provider.
    """
    
    # Define model mappings for consistency
    MODELS = {
        ConversationNode.Provider.OPENAI: {
            "fast": "gpt-4.1-mini",
            "balanced": "gpt-4.1",
            "quality": "gpt-4.1",
        },
        ConversationNode.Provider.GEMINI: {
            "fast": "gemini-2.5-flash",
            "balanced": "gemini-2.5-flash",
            "quality": "gemini-2.5-pro",
        }
    }

    def get_decision(p, m, mode_label, reason):
        return f"{mode_label} mode ({p.title()}): {m} selected {reason}."

    if routing_mode == ConversationNode.RoutingMode.AUTO_FAST:
        if provider == ConversationNode.Provider.OPENAI:
            p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["fast"]
            d = get_decision(p, m, "Fast", "for efficient text/vision within OpenAI")
        elif provider == ConversationNode.Provider.GEMINI:
            p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["fast"]
            d = get_decision(p, m, "Fast", "for efficient text/vision within Gemini")
        else:
            # Cross-provider: Gemini Flash is generally faster for multimodal, GPT-mini for text
            if has_attachments:
                p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["fast"]
                d = "Fast mode (Cross-provider): Gemini Flash selected for efficient multimodal processing."
            else:
                p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["fast"]
                d = "Fast mode (Cross-provider): GPT-4.1-mini selected for efficient text processing."
        return RoutingResult(p, m, d)

    if routing_mode == ConversationNode.RoutingMode.AUTO_BALANCED:
        if provider == ConversationNode.Provider.OPENAI:
            p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["balanced"]
            d = get_decision(p, m, "Balanced", "for reliable performance within OpenAI")
        elif provider == ConversationNode.Provider.GEMINI:
            p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["balanced"]
            d = get_decision(p, m, "Balanced", "for reliable performance within Gemini")
        else:
            if has_attachments:
                p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["balanced"]
                d = "Balanced mode (Cross-provider): GPT-4.1 selected for reliable multimodal understanding."
            else:
                p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["balanced"]
                d = "Balanced mode (Cross-provider): Gemini Flash selected for balanced performance."
        return RoutingResult(p, m, d)

    if routing_mode == ConversationNode.RoutingMode.AUTO_QUALITY:
        if provider == ConversationNode.Provider.OPENAI:
            p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["quality"]
            d = get_decision(p, m, "Quality", "for high-quality reasoning within OpenAI")
        elif provider == ConversationNode.Provider.GEMINI:
            p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["quality"]
            d = get_decision(p, m, "Quality", "for high-quality reasoning within Gemini")
        else:
            if has_attachments:
                p, m = ConversationNode.Provider.OPENAI, MODELS[ConversationNode.Provider.OPENAI]["quality"]
                d = "Quality mode (Cross-provider): GPT-4.1 selected for high-quality multimodal reasoning."
            else:
                p, m = ConversationNode.Provider.GEMINI, MODELS[ConversationNode.Provider.GEMINI]["quality"]
                d = "Quality mode (Cross-provider): Gemini Pro selected for deep reasoning."
        return RoutingResult(p, m, d)

    # Fallback
    fallback_p = provider or ConversationNode.Provider.OPENAI
    fallback_m = MODELS.get(fallback_p, MODELS[ConversationNode.Provider.OPENAI])["fast"]
    return RoutingResult(
        fallback_p,
        fallback_m,
        f"Manual or fallback routing used for mode: {routing_mode}"
    )

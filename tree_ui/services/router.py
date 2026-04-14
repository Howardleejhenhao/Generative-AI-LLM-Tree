from typing import NamedTuple
from tree_ui.models import ConversationNode

class RoutingResult(NamedTuple):
    provider: str
    model: str
    decision: str

def route_model(
    *,
    routing_mode: str,
    has_attachments: bool = False,
    prompt_length: int = 0,
) -> RoutingResult:
    """
    Selects the best provider and model based on the routing mode and request signals.
    """
    if routing_mode == ConversationNode.RoutingMode.AUTO_FAST:
        if has_attachments:
            # Gemini Flash is very fast for multimodal
            provider = ConversationNode.Provider.GEMINI
            model = "gemini-2.5-flash"
            decision = "Fast mode: Gemini Flash selected for efficient multimodal processing."
        else:
            # GPT-4.1-mini is the default fast text model in this project
            provider = ConversationNode.Provider.OPENAI
            model = "gpt-4.1-mini"
            decision = "Fast mode: GPT-4.1-mini selected for efficient text processing."
        return RoutingResult(provider, model, decision)

    if routing_mode == ConversationNode.RoutingMode.AUTO_BALANCED:
        if has_attachments:
            # Use OpenAI for balanced quality if there are attachments
            provider = ConversationNode.Provider.OPENAI
            model = "gpt-4.1" # Assuming gpt-4.1 is better than gpt-4.1-mini
            decision = "Balanced mode: GPT-4.1 selected for reliable multimodal understanding."
        else:
            # Gemini Flash is good for balanced text
            provider = ConversationNode.Provider.GEMINI
            model = "gemini-2.5-flash"
            decision = "Balanced mode: Gemini Flash selected for balanced performance."
        return RoutingResult(provider, model, decision)

    if routing_mode == ConversationNode.RoutingMode.AUTO_QUALITY:
        if has_attachments:
            # OpenAI for quality multimodal
            provider = ConversationNode.Provider.OPENAI
            model = "gpt-4.1"
            decision = "Quality mode: GPT-4.1 selected for high-quality multimodal reasoning."
        else:
            # Gemini Pro for quality text
            provider = ConversationNode.Provider.GEMINI
            model = "gemini-2.5-pro"
            decision = "Quality mode: Gemini Pro selected for deep reasoning."
        return RoutingResult(provider, model, decision)

    # Fallback/Manual (Manual should be handled by caller, but we provide a default)
    return RoutingResult(
        ConversationNode.Provider.OPENAI,
        "gpt-4.1-mini",
        f"Manual or fallback routing used for mode: {routing_mode}"
    )

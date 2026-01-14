"""
Intelligent routing agent for French labor law queries.

Decides which Qdrant collection(s) to query and extracts IDCC if needed.
"""

import logging
from typing import Dict, List, Optional, Literal
from openai import OpenAI
from pydantic import BaseModel, Field
from src.config.constants import LLM_CONFIG

logger = logging.getLogger(__name__)

# IDCC Convention Mapping (extracted from KALI metadata)
CONVENTION_MAPPING = {
    "1486": {"name": "Syntec", "keywords": ["informatique", "ingénieur", "développeur", "IT", "consulting", "conseil", "ESN", "SSII"]},
    "3248": {"name": "Métallurgie", "keywords": ["métallurgie", "métal", "industrie", "usine", "production"]},
    "1979": {"name": "HCR", "keywords": ["hôtel", "restaurant", "café", "serveur", "cuisinier", "réception", "CHR"]},
    "1597": {"name": "Bâtiment", "keywords": ["construction", "bâtiment", "BTP", "chantier", "ouvrier", "maçon"]},
    "1090": {"name": "Automobile", "keywords": ["automobile", "garage", "mécanicien", "concessionnaire", "réparation"]},
    "2216": {"name": "Commerce alimentaire", "keywords": ["supermarché", "hypermarché", "commerce", "alimentaire", "caissier"]},
    "2120": {"name": "Banque", "keywords": ["banque", "bancaire", "conseiller", "guichet", "finance"]}
}


class RoutingDecision(BaseModel):
    """Routing decision output with Pydantic validation."""
    strategy: Literal["code_only", "kali_only", "both_code_first", "both_kali_first"] = Field(
        description="Routing strategy to use"
    )
    idcc: Optional[str] = Field(
        default=None,
        description="IDCC number if convention-specific (e.g., '1486'), or null if not applicable"
    )
    reasoning: str = Field(
        description="One sentence explaining the routing decision"
    )

    @property
    def collections(self) -> List[str]:
        """Derive collections list from strategy."""
        if self.strategy == "code_only":
            return ["code_travail"]
        elif self.strategy == "kali_only":
            return ["kali"]
        elif self.strategy == "both_code_first":
            return ["code_travail", "kali"]
        elif self.strategy == "both_kali_first":
            return ["kali", "code_travail"]
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', defaulting to code_only")
            return ["code_travail"]


class RoutingAgent:
    """
    Intelligent agent that decides which collections to query.

    Uses LLM to:
    1. Detect if query is convention-specific
    2. Extract job role/industry and map to IDCC
    3. Decide query strategy and order
    """

    def __init__(self):
        self.config = LLM_CONFIG
        provider = self.config.get("provider", "openai")

        if provider == "openai":
            api_config = self.config["openai"]
            self.client = OpenAI(api_key=api_config["api_key"])
            self.model = api_config["model"]
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        self.provider = provider
        logger.info(f"Initialized RoutingAgent with {provider} ({self.model})")

    def route(self, query: str) -> RoutingDecision:
        """
        Analyze query and decide routing strategy.

        Returns:
            RoutingDecision with strategy, collections, and optional IDCC
        """
        logger.info(f"\n{'='*80}\nROUTING AGENT\n{'='*80}")
        logger.info(f"📥 Input query: \"{query}\"")

        # Call LLM for routing decision
        try:
            decision = self._llm_route(query)
            logger.info(f"📊 Strategy: {decision.strategy}")
            logger.info(f"📦 Collections: {decision.collections}")
            logger.info(f"🏢 IDCC: {decision.idcc}")
            logger.info(f"💡 Reasoning: {decision.reasoning}")
            logger.info(f"{'='*80}\n")
            return decision
        except Exception as e:
            logger.error(f"LLM routing failed: {e}, falling back to code_travail only")
            return RoutingDecision(
                strategy="code_only",
                collections=["code_travail"],
                reasoning="Fallback: LLM error"
            )

    def _llm_route(self, query: str) -> RoutingDecision:
        """Call LLM to make routing decision with structured output."""

        system_prompt = self._get_system_prompt()
        user_prompt = f"""Query: "{query}"

Analyze this French labor law query and decide routing strategy."""

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=RoutingDecision,
            temperature=0,  # Deterministic
        )

        # Pydantic automatically validates the response
        return response.choices[0].message.parsed

    def _get_system_prompt(self) -> str:
        """System prompt for routing decisions."""
        conventions_list = "\n".join([
            f"- IDCC {idcc}: {info['name']} (keywords: {', '.join(info['keywords'][:5])})"
            for idcc, info in CONVENTION_MAPPING.items()
        ])

        return f"""You are a routing agent for a French labor law RAG system with two knowledge bases:

1. **Code du travail**: General French labor law (applies to all workers)
2. **KALI conventions**: Industry-specific collective bargaining agreements (override Code du travail when more favorable)

Available conventions:
{conventions_list}

**Decision rules:**
- code_only: General labor law questions (e.g., "durée légale du travail", "congés payés légaux")
- kali_only: Query explicitly mentions a convention/industry AND asks about convention-specific rules
- both_code_first: Query could apply to both (check general law first, then convention)
- both_kali_first: Convention-specific question where convention rules are primary

**IDCC detection:**
- Extract job role or industry from query
- Map to IDCC using keywords (e.g., "ingénieur informatique" → "1486")
- If ambiguous or no clear match: null

Examples:
- "Quelle est la durée du préavis de démission?" → code_only, idcc: null (general legal question)
- "Quel est le préavis de démission pour un ingénieur informatique?" → both_kali_first, idcc: "1486" (IT engineer = Syntec)
- "Convention Syntec période d'essai" → kali_only, idcc: "1486" (explicitly asks about Syntec)

Be concise and deterministic."""


# Singleton instance
_routing_agent = None

def get_routing_agent() -> RoutingAgent:
    """Get or create routing agent singleton."""
    global _routing_agent
    if _routing_agent is None:
        _routing_agent = RoutingAgent()
    return _routing_agent

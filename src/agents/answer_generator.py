"""Answer generation from retrieved context with citations."""

import logging
from typing import List, Dict, Optional
from openai import OpenAI
from pydantic import BaseModel, Field
from src.config.constants import LLM_CONFIG

logger = logging.getLogger(__name__)


class AnswerWithCitations(BaseModel):
    """Generated answer with citation tracking."""
    answer: str = Field(description="Generated answer in French")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in the answer (0-1)"
    )
    citation_indices: List[int] = Field(
        default=[],
        description="Indices of results cited in answer (0-based)"
    )
    reasoning: str = Field(description="Why this answer was generated")


class AnswerGenerator:
    """
    Generate natural language answers from retrieved context.

    Uses OpenAI GPT-4o-mini with structured outputs to produce answers
    with tracked citations pointing back to retrieved articles.
    """

    def __init__(self):
        """Initialize answer generator with OpenAI client."""
        config = LLM_CONFIG
        provider = config.get("provider", "openai")

        if provider == "openai":
            api_config = config["openai"]
            self.client = OpenAI(api_key=api_config["api_key"])
            self.model = api_config["model"]
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        self.provider = provider
        logger.info(f"Initialized AnswerGenerator with {provider} ({self.model})")

    def generate(self, query: str, results: List[Dict]) -> AnswerWithCitations:
        """
        Generate answer from retrieved context.

        Args:
            query: User's question
            results: List of retrieved results from multi_retriever

        Returns:
            AnswerWithCitations with answer, confidence, citation_indices, and reasoning
        """
        if not results:
            logger.warning("No results provided for answer generation")
            return AnswerWithCitations(
                answer="Aucune information disponible pour répondre à cette question.",
                confidence=0.0,
                citation_indices=[],
                reasoning="Pas de résultats de recherche fournis"
            )

        # Build context from top 3 results only
        context = self._build_context(results[:3])

        logger.info(f"\n{'='*80}\nANSWER GENERATION\n{'='*80}")
        logger.info(f"📥 Question: \"{query}\"")
        logger.info(f"📚 Context from {len(results[:3])} sources")

        system_prompt = self._get_system_prompt()
        user_prompt = f"Question: {query}\n\nContexte:\n{context}"

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=AnswerWithCitations,
                temperature=0.7,  # Some creativity for natural language
            )

            answer = response.choices[0].message.parsed

            # Validate citation indices
            valid_indices = [idx for idx in answer.citation_indices if 0 <= idx < len(results)]
            if len(valid_indices) != len(answer.citation_indices):
                logger.warning(
                    f"Invalid citation indices: {answer.citation_indices}, "
                    f"valid: {valid_indices}, total results: {len(results)}"
                )
                answer.citation_indices = valid_indices

            logger.info(f"✅ Generated answer with confidence {answer.confidence:.2f}")
            logger.info(f"📌 Cited sources: {answer.citation_indices}")
            logger.info(f"💡 Reasoning: {answer.reasoning}")
            logger.info(f"{'='*80}\n")

            return answer

        except Exception as e:
            logger.error(f"Failed to generate answer: {e}", exc_info=True)
            # Fallback answer
            return AnswerWithCitations(
                answer="Je n'ai pas pu générer une réponse à cette question.",
                confidence=0.0,
                citation_indices=[],
                reasoning=f"Erreur lors de la génération: {str(e)[:100]}"
            )

    def _build_context(self, results: List[Dict]) -> str:
        """
        Build context string from top 3 results for LLM.

        Args:
            results: Retrieved results (will use first 3)

        Returns:
            Formatted context string with source labels
        """
        top_3 = results[:3]
        context = ""

        for i, result in enumerate(top_3, 1):
            meta = result["metadata"]
            article = meta.get("article_num", "unknown")
            source = result["_collection"]
            content = result["content"]

            # Format source label
            if source == "kali":
                convention = meta.get("convention_name", "")
                idcc = meta.get("idcc", "")
                source_label = f"{article} (Convention {convention} - IDCC {idcc})"
            else:
                source_label = f"{article} (Code du travail)"

            context += f"[Source {i}] {source_label}:\n{content}\n\n"

        return context

    def _get_system_prompt(self) -> str:
        """System prompt for answer generation."""
        return """Tu es un expert en droit du travail français.
Ta tâche est de fournir des réponses claires et précises aux questions sur le droit du travail français.

RÈGLES IMPORTANTES:
1. Réponds en français
2. Utilise UNIQUEMENT les informations du contexte fourni
3. Si tu cites plusieurs sources, indique lequel(s) support(s) chaque affirmation (ex: "selon la Source 1")
4. Sois précis et cite les articles pertinents
5. Reconnaître l'incertitude ou les sources conflictuelles
6. Garde ta réponse concise mais complète (2-4 phrases max)
7. Fournis un score de confiance (0-1):
   - 0.9-1.0: Réponse définitive clairement soutenue
   - 0.7-0.9: Réponse claire avec bon support
   - 0.5-0.7: Réponse raisonnable, mais une certaine incertitude
   - <0.5: Information insuffisante ou conflictuelle

IMPORTANT: Pour les indices de citation, utilise les numéros de source (1, 2, 3) du contexte fourni.
Ne cite QUE les sources que tu utilises réellement dans ta réponse."""


# Singleton instance
_answer_generator = None


def get_answer_generator() -> AnswerGenerator:
    """Get or create answer generator singleton."""
    global _answer_generator
    if _answer_generator is None:
        _answer_generator = AnswerGenerator()
    return _answer_generator

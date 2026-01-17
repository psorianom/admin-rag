"""
FastHTML web UI for testing retrieval pipeline with answer generation.
"""

import logging
import os
from fasthtml.common import *
from src.retrieval.retrieve import retrieve
from src.agents.routing_agent import get_routing_agent
from src.agents.multi_retriever import retrieve_with_routing
from src.agents.answer_generator import get_answer_generator
from src.config.constants import API_STAGE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Make routes stage-aware (e.g., handle /prod prefix)
root_path = f"/{API_STAGE}" if API_STAGE else ""
print(f"INFO: Application starting with root_path: '{root_path}'")

app, rt = fast_app()


def format_metadata(meta):
    """Format metadata for display."""
    parts = []

    # Article info
    parts.append(f"📄 Article {meta['article_num']}")

    # Convention info (for KALI)
    if meta.get('convention_name'):
        parts.append(f"📋 {meta['convention_name']} (IDCC {meta['idcc']})")

    # Hierarchy
    if meta.get('livre'):
        parts.append(f"📚 {meta['livre']}")
    if meta.get('section_title'):
        parts.append(f"📑 {meta['section_title']}")

    return Div(*[P(p, style="margin: 2px 0; font-size: 0.9em; color: #000;") for p in parts])


def result_card(result, rank, highlighted=False):
    """Create a card for a search result with optional citation highlighting."""
    meta = result['metadata']
    content = result['content']
    score = result['score']

    # Truncate content
    preview = content[:400] + "..." if len(content) > 400 else content

    # Blue left border if cited in answer
    border_style = "3px solid #007bff" if highlighted else "1px solid #ddd"

    return Article(
        Div(
            Span(f"#{rank}", style="font-weight: bold; color: #666;"),
            Span(f"Score: {score:.2f}", style="float: right; color: #888; font-size: 0.9em;"),
            style="margin-bottom: 8px;"
        ),
        format_metadata(meta),
        Hr(),
        P(preview, style="white-space: pre-wrap; line-height: 1.5; color: #000;"),
        style=f"""
            border-left: {border_style};
            padding: 16px;
            margin: 16px 0;
            border-radius: 8px;
            background: #fff;
            color: #000;
        """
    )


def answer_section(answer):
    """Display generated answer with reasoning."""
    return Div(
        H2("Réponse"),
        P(answer.answer, style="font-size: 16px; line-height: 1.6; color: #333; margin-bottom: 12px;"),
        P(
            f"Raisonnement: {answer.reasoning}",
            style="color: #666; font-size: 14px; font-style: italic;"
        ),
        style="background: #f9f9f9; padding: 20px; border-left: 4px solid #007bff; margin-bottom: 24px; border-radius: 4px;"
    )


def confidence_badge(confidence):
    """Display confidence score with color coding."""
    if confidence >= 0.8:
        color = "#28a745"
        label = "Haute"
    elif confidence >= 0.6:
        color = "#ffc107"
        label = "Moyenne"
    else:
        color = "#dc3545"
        label = "Basse"

    return Div(
        Span(
            f"Confiance: {label} ({confidence:.0%})",
            style=f"background: {color}; color: white; padding: 6px 12px; border-radius: 4px; font-size: 13px; font-weight: bold;"
        ),
        style="margin-bottom: 20px;"
    )


@rt(f"{root_path}/")
def get():
    """Main page."""
    return Titled(
        "Admin-RAG Search",
        Div(
            H2("French Labor Law Search"),
            P("Search the Code du travail and KALI conventions using semantic search (BGE-M3 ONNX int8 embeddings).",
              style="color: #666; margin-bottom: 24px;"),

            Form(
                # Query input
                Div(
                    Label("Search Query:", style="display: block; margin-bottom: 4px; font-weight: bold;"),
                    Input(
                        name="query",
                        placeholder="e.g., période d'essai durée maximale",
                        style="width: 100%; padding: 8px; font-size: 16px;",
                        required=True
                    ),
                    style="margin-bottom: 16px;"
                ),

                # Top-k selector
                Div(
                    Label("Number of results:", style="display: block; margin-bottom: 4px; font-weight: bold;"),
                    Input(
                        name="top_k",
                        type="number",
                        value="10",
                        min="1",
                        max="50",
                        style="padding: 8px; font-size: 14px; width: 100px;"
                    ),
                    style="margin-bottom: 16px;"
                ),

                # Submit button
                Button(
                    "🔍 Search",
                    type="submit",
                    style="""
                        padding: 12px 24px;
                        font-size: 16px;
                        background: #007bff;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                    """
                ),

                hx_post=f"{root_path}/search",
                hx_target="#results",
                hx_swap="innerHTML",
                hx_indicator="#spinner"
            ),

            # Loading spinner
            Div(
                "Searching...",
                id="spinner",
                cls="htmx-indicator",
                style="margin: 16px 0; color: #007bff; font-weight: bold;"
            ),

            # Results container
            Div(id="results", style="margin-top: 32px;"),

            style="max-width: 900px; margin: 0 auto; padding: 20px;"
        )
    )


@rt(f"{root_path}/search")
def post(query: str, top_k: int = 10):
    """Handle search request with intelligent routing."""
    logger.info(f"\n{'='*80}\nWEB UI /search REQUEST\n{'='*80}")
    logger.info(f"Query: \"{query}\" | Top-K: {top_k}")
    if not query or not query.strip():
        return Div(
            P("Please enter a search query.", style="color: red;"),
            style="padding: 16px;"
        )

    try:
        # Step 1: Route query
        routing_agent = get_routing_agent()
        decision = routing_agent.route(query.strip())

        logger.info(f"Routing decision: {decision}")

        # Step 2: Retrieve from routed collections
        results = retrieve_with_routing(query.strip(), decision, top_k=int(top_k))

        if not results:
            return Div(
                H3("No results found"),
                P(f"No matches for: \"{query}\"", style="color: #666;"),
                style="padding: 16px;"
            )

        # Step 3: Generate answer from retrieved context
        answer_gen = get_answer_generator()
        answer = answer_gen.generate(query.strip(), results)

        # Step 4: Format results with routing info
        routing_info = f"Strategy: {decision.strategy}"
        if decision.idcc:
            routing_info += f" | Convention: IDCC {decision.idcc}"

        logger.info(f"\n✅ FINAL RESULT: {len(results)} results returned with answer")
        logger.info(f"{'='*80}\n")

        # Build response with answer + sources
        return Div(
            # Answer section
            answer_section(answer),
            confidence_badge(answer.confidence),

            # Query and routing info
            P(f"Requête: \"{query}\"", style="color: #666; margin-bottom: 4px; font-size: 0.9em;"),
            P(f"Décision agent: {routing_info}", style="color: #0066cc; margin-bottom: 16px; font-size: 0.9em;"),

            # Sources header
            H3(f"Sources ({len(results)} résultats)"),

            # Results with citation highlighting
            *[
                result_card(
                    r, i,
                    highlighted=(i - 1) in answer.citation_indices
                )
                for i, r in enumerate(results, 1)
            ]
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return Div(
            H3("Error", style="color: red;"),
            P(str(e)),
            style="padding: 16px;"
        )


if __name__ == "__main__":
    import uvicorn
    # Get port from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    
    print("="*80)
    print("Starting Admin-RAG Web UI")
    print("="*80)
    print(f"\nOpen your browser to: http://localhost:{port}{root_path}/")
    print("\nPress Ctrl+C to stop")
    print("="*80)
    uvicorn.run(app, host='0.0.0.0', port=port)

"""
FastHTML web UI for testing retrieval pipeline.
"""

import logging
from fasthtml.common import *
from src.retrieval.retrieve import retrieve
from src.agents.routing_agent import get_routing_agent
from src.agents.multi_retriever import retrieve_with_routing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app, rt = fast_app()

# Available conventions
CONVENTIONS = {
    "all": "All conventions",
    "1486": "Syntec (IT services, consulting)",
    "3248": "Métallurgie",
    "1979": "HCR (Hotels, cafés, restaurants)",
    "1597": "Bâtiment (Construction)",
    "1090": "Services de l'automobile",
    "2216": "Commerce alimentaire",
    "2120": "Banque",
}


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


def result_card(result, rank):
    """Create a card for a search result."""
    meta = result['metadata']
    content = result['content']
    score = result['score']

    # Truncate content
    preview = content[:400] + "..." if len(content) > 400 else content

    return Article(
        Div(
            Span(f"#{rank}", style="font-weight: bold; color: #666;"),
            Span(f"Score: {score:.2f}", style="float: right; color: #888; font-size: 0.9em;"),
            style="margin-bottom: 8px;"
        ),
        format_metadata(meta),
        Hr(),
        P(preview, style="white-space: pre-wrap; line-height: 1.5; color: #000;"),
        style="""
            border: 1px solid #ddd;
            padding: 16px;
            margin: 16px 0;
            border-radius: 8px;
            background: #fff;
            color: #000;
        """
    )


@rt("/")
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

                # Collection selector
                Div(
                    Label("Collection:", style="display: block; margin-bottom: 4px; font-weight: bold;"),
                    Select(
                        Option("Code du travail", value="code_travail"),
                        Option("KALI (Conventions)", value="kali"),
                        name="collection",
                        id="collection-select",
                        style="padding: 8px; font-size: 14px;",
                        hx_get="/convention_selector",
                        hx_target="#convention-filter",
                        hx_swap="innerHTML"
                    ),
                    style="margin-bottom: 16px;"
                ),

                # Convention filter (shown only for KALI)
                Div(id="convention-filter", style="margin-bottom: 16px;"),

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

                hx_post="/search",
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


@rt("/convention_selector")
def get(collection: str = "code_travail"):
    """Return convention filter dropdown (only for KALI)."""
    if collection != "kali":
        return ""

    return Div(
        Label("Convention (optional):", style="display: block; margin-bottom: 4px; font-weight: bold;"),
        Select(
            *[Option(name, value=code) for code, name in CONVENTIONS.items()],
            name="convention",
            style="padding: 8px; font-size: 14px; width: 100%;"
        )
    )


@rt("/search")
def post(query: str, top_k: int = 10):
    """Handle search request with intelligent routing."""
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

        # Step 3: Format results with routing info
        routing_info = f"Strategy: {decision.strategy}"
        if decision.idcc:
            routing_info += f" | Convention: IDCC {decision.idcc}"

        return Div(
            H3(f"Found {len(results)} results"),
            P(f"Query: \"{query}\"", style="color: #666; margin-bottom: 4px;"),
            P(f"Agent decision: {routing_info}", style="color: #0066cc; margin-bottom: 4px; font-size: 0.9em;"),
            P(f"Reasoning: {decision.reasoning}", style="color: #666; margin-bottom: 16px; font-size: 0.9em; font-style: italic;"),
            *[result_card(r, i) for i, r in enumerate(results, 1)]
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return Div(
            H3("Error", style="color: red;"),
            P(str(e)),
            style="padding: 16px;"
        )


# Lambda handler for AWS Lambda deployment
async def lambda_handler(event, context):
    """AWS Lambda handler for FastHTML app."""
    from mangum import Mangum
    return Mangum(app)(event, context)


if __name__ == "__main__":
    import uvicorn
    print("="*80)
    print("Starting Admin-RAG Web UI")
    print("="*80)
    print("\nOpen your browser to: http://localhost:5001")
    print("\nPress Ctrl+C to stop")
    print("="*80)
    uvicorn.run(app, host='0.0.0.0', port=5001)

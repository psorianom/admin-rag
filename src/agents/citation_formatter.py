"""Citation formatting utilities for displaying retrieved sources."""

from typing import Dict


def format_citation(result: Dict, index: int) -> str:
    """
    Format a single result as a citation string.

    Args:
        result: Retrieved result dict with content, metadata, _collection
        index: Position in results list (1-based for display)

    Returns:
        Formatted citation string

    Examples:
        - Code du travail: "Article L1221-19 (Code du travail)"
        - KALI: "Convention Syntec (IDCC 1486) - Article 2.3"
    """
    meta = result.get("metadata", {})
    source = result.get("_collection", "unknown")
    article = meta.get("article_num", "unknown")

    if source == "kali":
        convention = meta.get("convention_name", "")
        idcc = meta.get("idcc", "")
        if convention and idcc:
            return f"Convention {convention} (IDCC {idcc}) - Article {article}"
        else:
            return f"KALI - Article {article}"
    else:  # code_travail
        return f"Article {article} (Code du travail)"


def get_source_url(result: Dict) -> str:
    """
    Get a URL or reference for the source (future enhancement).

    Args:
        result: Retrieved result dict

    Returns:
        URL string (placeholder for future Légifrance links)
    """
    meta = result.get("metadata", {})
    source = result.get("_collection", "")
    article_num = meta.get("article_num", "")

    if source == "code_travail":
        article_id = meta.get("article_id", "")
        if article_id:
            # Future: Link to Légifrance
            return f"https://www.legifrance.gouv.fr/codes/article_lc/{article_id}"
    elif source == "kali":
        # Future: Link to KALI source
        pass

    return ""


def build_citation_html(result: Dict, index: int, cited: bool = False) -> str:
    """
    Build HTML for displaying a citation (future enhancement).

    Args:
        result: Retrieved result dict
        index: 1-based position in results
        cited: Whether this result is cited in the answer

    Returns:
        HTML string for citation display
    """
    citation = format_citation(result, index)
    url = get_source_url(result)

    if url:
        return f'<a href="{url}" target="_blank">{citation}</a>'
    else:
        return citation

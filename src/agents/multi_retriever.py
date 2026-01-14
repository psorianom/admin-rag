"""
Multi-collection retrieval with intelligent result merging.
"""

import logging
from typing import List, Dict
from src.retrieval.retrieve import retrieve
from src.agents.routing_agent import RoutingDecision

logger = logging.getLogger(__name__)


def retrieve_with_routing(query: str, decision: RoutingDecision, top_k: int = 10) -> List[Dict]:
    """
    Execute retrieval based on routing decision.

    Args:
        query: User query
        decision: RoutingDecision from routing agent
        top_k: Number of results per collection

    Returns:
        List of results with collection source tagged
    """
    all_results = []

    for collection in decision.collections:
        # Build filters for KALI
        filters = None
        if collection == "kali" and decision.idcc:
            filters = {"field": "idcc", "operator": "==", "value": decision.idcc}
            logger.info(f"Querying {collection} with IDCC filter: {decision.idcc}")
        else:
            logger.info(f"Querying {collection}")

        try:
            results = retrieve(
                query=query,
                collection_name=collection,
                top_k=top_k,
                filters=filters
            )

            # Tag results with collection source
            for result in results:
                result['_collection'] = collection
                if collection == "kali" and decision.idcc:
                    result['_convention'] = decision.idcc

            all_results.extend(results)

        except Exception as e:
            logger.error(f"Error retrieving from {collection}: {e}")
            continue

    # Sort by score (descending)
    all_results.sort(key=lambda x: x['score'], reverse=True)

    # Take top-k from merged results
    return all_results[:top_k]

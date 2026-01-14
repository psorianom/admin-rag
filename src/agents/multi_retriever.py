"""
Multi-collection retrieval with intelligent result merging.
"""

import logging
from typing import List, Dict
from qdrant_client.models import Filter, FieldCondition, MatchValue
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

    logger.info(f"\n{'='*80}\nMULTI-COLLECTION RETRIEVAL\n{'='*80}")
    logger.info(f"Query: \"{query}\"")
    logger.info(f"Collections to query: {decision.collections}")
    logger.info(f"Top-K: {top_k}")

    for idx, collection in enumerate(decision.collections, 1):
        # Build filters for KALI
        filters = None
        if collection == "kali" and decision.idcc:
            filters = Filter(
                must=[FieldCondition(key="meta.idcc", match=MatchValue(value=decision.idcc))]
            )
            logger.info(f"\n[{idx}/{len(decision.collections)}] Querying {collection} with filter IDCC={decision.idcc}")
            logger.info(f"DEBUG: Filter object: {filters}")
            logger.info(f"DEBUG: IDCC type: {type(decision.idcc)}, value: {repr(decision.idcc)}")
        else:
            logger.info(f"\n[{idx}/{len(decision.collections)}] Querying {collection} (no filter)")

        try:
            results = retrieve(
                query=query,
                collection_name=collection,
                top_k=top_k,
                filters=filters
            )

            logger.info(f"✅ Got {len(results)} results from {collection}")

            # Tag results with collection source
            for result in results:
                result['_collection'] = collection
                if collection == "kali" and decision.idcc:
                    result['_convention'] = decision.idcc

            all_results.extend(results)

        except Exception as e:
            logger.error(f"❌ Error retrieving from {collection}: {str(e)[:200]}")
            continue

    # Sort by score (descending)
    all_results.sort(key=lambda x: x['score'], reverse=True)

    # Take top-k from merged results
    final_results = all_results[:top_k]
    logger.info(f"\n📊 Merged results: {len(all_results)} total, returning top {len(final_results)}")
    logger.info(f"{'='*80}\n")

    return final_results

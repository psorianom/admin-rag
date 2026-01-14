"""Tests for multi-collection retrieval with intelligent routing."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from qdrant_client.models import Filter, FieldCondition, MatchValue
from src.agents.routing_agent import RoutingDecision
from src.agents.multi_retriever import retrieve_with_routing


class TestRetrieveWithRouting:
    """Test retrieve_with_routing function."""

    @pytest.fixture
    def sample_results(self):
        """Sample retrieval results from collections."""
        return {
            "kali": [
                {
                    "content": "Article Syntec trial period",
                    "metadata": {"idcc": "1486", "convention_name": "Syntec", "article_num": "2"},
                    "score": 0.75,
                },
                {
                    "content": "Article Syntec additional benefits",
                    "metadata": {"idcc": "1486", "convention_name": "Syntec", "article_num": "3.4"},
                    "score": 0.70,
                },
            ],
            "code_travail": [
                {
                    "content": "General labor law trial period",
                    "metadata": {"article_num": "L1221-19", "source": "code_travail"},
                    "score": 0.65,
                },
                {
                    "content": "General dismissal notice",
                    "metadata": {"article_num": "L1237-1", "source": "code_travail"},
                    "score": 0.60,
                },
            ],
        }

    def test_kali_only_filtering(self, sample_results):
        """Test kali_only strategy with IDCC filtering."""
        decision = RoutingDecision(
            strategy="kali_only",
            idcc="1486",
            reasoning="Explicit Syntec convention query"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            # Only return kali results for kali query
            mock_retrieve.return_value = sample_results["kali"]

            results = retrieve_with_routing("Convention Syntec", decision, top_k=5)

            # Verify retrieve was called once (only kali)
            assert mock_retrieve.call_count == 1

            # Verify call had correct filter
            call_args = mock_retrieve.call_args
            assert call_args[1]["collection_name"] == "kali"
            assert call_args[1]["top_k"] == 5

            # Check filter object structure
            filters = call_args[1]["filters"]
            assert filters is not None
            assert isinstance(filters, Filter)
            assert len(filters.must) == 1
            assert filters.must[0].key == "meta.idcc"
            assert filters.must[0].match.value == "1486"

            # Verify results
            assert len(results) == 2
            assert all(r.get("_collection") == "kali" for r in results)
            assert all(r.get("_convention") == "1486" for r in results)

    def test_code_only_no_filter(self, sample_results):
        """Test code_only strategy without filtering."""
        decision = RoutingDecision(
            strategy="code_only",
            idcc=None,
            reasoning="General labor law question"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            mock_retrieve.return_value = sample_results["code_travail"]

            results = retrieve_with_routing("Préavis démission", decision, top_k=5)

            # Verify retrieve was called once (only code_travail)
            assert mock_retrieve.call_count == 1

            call_args = mock_retrieve.call_args
            assert call_args[1]["collection_name"] == "code_travail"
            assert call_args[1]["filters"] is None  # No filter for code_travail

            # Verify results
            assert len(results) == 2
            assert all(r.get("_collection") == "code_travail" for r in results)

    def test_both_kali_first_merge_and_sort(self, sample_results):
        """Test both_kali_first strategy merges and sorts by score."""
        decision = RoutingDecision(
            strategy="both_kali_first",
            idcc="1486",
            reasoning="IT engineer query"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            # Return kali results first, then code_travail
            mock_retrieve.side_effect = [
                sample_results["kali"],  # First call for kali
                sample_results["code_travail"],  # Second call for code_travail
            ]

            results = retrieve_with_routing("Ingénieur informatique", decision, top_k=3)

            # Verify retrieve was called twice (kali, then code_travail)
            assert mock_retrieve.call_count == 2

            # First call should be kali with filter
            first_call = mock_retrieve.call_args_list[0]
            assert first_call[1]["collection_name"] == "kali"
            assert first_call[1]["filters"] is not None

            # Second call should be code_travail without filter
            second_call = mock_retrieve.call_args_list[1]
            assert second_call[1]["collection_name"] == "code_travail"
            assert second_call[1]["filters"] is None

            # Results should be merged, sorted by score, and top-k returned
            assert len(results) == 3  # top_k=3

            # Verify sorted by score (descending)
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)

            # Verify all results have collection tag
            assert all("_collection" in r for r in results)

    def test_both_code_first_strategy(self, sample_results):
        """Test both_code_first strategy queries code then kali."""
        decision = RoutingDecision(
            strategy="both_code_first",
            idcc="1979",
            reasoning="HCR worker query"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            # Return code_travail first, then kali
            mock_retrieve.side_effect = [
                sample_results["code_travail"],  # First call for code_travail
                sample_results["kali"],  # Second call for kali
            ]

            results = retrieve_with_routing("Serveur restaurant", decision, top_k=4)

            # Verify retrieve was called twice in correct order
            assert mock_retrieve.call_count == 2

            first_call = mock_retrieve.call_args_list[0]
            assert first_call[1]["collection_name"] == "code_travail"

            second_call = mock_retrieve.call_args_list[1]
            assert second_call[1]["collection_name"] == "kali"
            assert second_call[1]["filters"] is not None

    def test_result_tagging_with_convention(self, sample_results):
        """Test results are tagged with collection and convention info."""
        decision = RoutingDecision(
            strategy="both_kali_first",
            idcc="3248",
            reasoning="Metallurgy worker"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            mock_retrieve.side_effect = [
                sample_results["kali"],
                sample_results["code_travail"],
            ]

            results = retrieve_with_routing("Métallurgie", decision, top_k=10)

            # Verify kali results have convention tag
            kali_results = [r for r in results if r.get("_collection") == "kali"]
            assert all(r.get("_convention") == "3248" for r in kali_results)

            # Verify code_travail results don't have convention tag
            code_results = [r for r in results if r.get("_collection") == "code_travail"]
            assert all(r.get("_convention") is None for r in code_results)

    def test_empty_results_handling(self):
        """Test handling when a collection returns no results."""
        decision = RoutingDecision(
            strategy="both_kali_first",
            idcc="1486",
            reasoning="Test"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            # Kali returns results, code_travail returns empty
            mock_retrieve.side_effect = [
                [
                    {
                        "content": "Test",
                        "metadata": {"idcc": "1486"},
                        "score": 0.8,
                    }
                ],
                []  # Empty results from code_travail
            ]

            results = retrieve_with_routing("Test query", decision, top_k=5)

            # Should have 1 result (only from kali)
            assert len(results) == 1
            assert results[0]["_collection"] == "kali"

    def test_top_k_limit_applied(self, sample_results):
        """Test top_k limit is correctly applied to merged results."""
        decision = RoutingDecision(
            strategy="both_kali_first",
            idcc="1486",
            reasoning="Test"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            mock_retrieve.side_effect = [
                sample_results["kali"],
                sample_results["code_travail"],
            ]

            # Request top_k=2
            results = retrieve_with_routing("Test", decision, top_k=2)

            # Should return exactly 2 results (total of 4 available)
            assert len(results) == 2

    def test_score_based_sorting(self):
        """Test results are sorted by score regardless of collection order."""
        decision = RoutingDecision(
            strategy="both_code_first",
            idcc=None,
            reasoning="Test"
        )

        kali_low_score = [
            {"content": "Low score from kali", "metadata": {}, "score": 0.50}
        ]
        code_high_score = [
            {"content": "High score from code", "metadata": {}, "score": 0.90},
            {"content": "Medium score from code", "metadata": {}, "score": 0.70},
        ]

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            mock_retrieve.side_effect = [code_high_score, kali_low_score]

            results = retrieve_with_routing("Test", decision, top_k=10)

            # Verify sorting by score (descending) regardless of collection order
            scores = [r["score"] for r in results]
            assert scores == [0.90, 0.70, 0.50]

    def test_kali_filter_with_different_idcc(self):
        """Test different IDCC values produce different filters."""
        idcc_values = ["1486", "1979", "3248", "1597"]

        for idcc in idcc_values:
            decision = RoutingDecision(
                strategy="kali_only",
                idcc=idcc,
                reasoning="Test"
            )

            with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
                mock_retrieve.return_value = []

                retrieve_with_routing("Test", decision, top_k=5)

                call_args = mock_retrieve.call_args
                filters = call_args[1]["filters"]

                # Verify correct IDCC is in filter
                assert filters.must[0].match.value == idcc

    def test_no_filter_when_idcc_none(self):
        """Test no filter is applied when IDCC is None even for kali."""
        decision = RoutingDecision(
            strategy="kali_only",
            idcc=None,
            reasoning="Ambiguous convention query"
        )

        with patch('src.agents.multi_retriever.retrieve') as mock_retrieve:
            mock_retrieve.return_value = []

            retrieve_with_routing("Test", decision, top_k=5)

            call_args = mock_retrieve.call_args
            assert call_args[1]["filters"] is None

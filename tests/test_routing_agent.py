"""Tests for intelligent routing agent."""

import pytest
from unittest.mock import Mock, patch
from src.agents.routing_agent import RoutingAgent, RoutingDecision, get_routing_agent


class TestRoutingDecision:
    """Test RoutingDecision Pydantic model."""

    def test_valid_decision(self):
        """Test valid routing decision creation."""
        decision = RoutingDecision(
            strategy="code_only",
            idcc=None,
            reasoning="General legal question"
        )
        assert decision.strategy == "code_only"
        assert decision.idcc is None
        assert decision.collections == ["code_travail"]

    def test_invalid_strategy_raises(self):
        """Test invalid strategy raises ValidationError."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            RoutingDecision(
                strategy="invalid_strategy",
                idcc=None,
                reasoning="Test"
            )

    def test_collections_derived_from_strategy(self):
        """Test collections property correctly derives from strategy."""
        cases = [
            ("code_only", ["code_travail"]),
            ("kali_only", ["kali"]),
            ("both_code_first", ["code_travail", "kali"]),
            ("both_kali_first", ["kali", "code_travail"]),
        ]
        for strategy, expected_collections in cases:
            decision = RoutingDecision(strategy=strategy, reasoning="Test")
            assert decision.collections == expected_collections


class TestRoutingAgent:
    """Test RoutingAgent behavior."""

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI structured output response."""
        def _mock(strategy: str, idcc: str = None, reasoning: str = "Test reasoning"):
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.parsed = RoutingDecision(
                strategy=strategy,
                idcc=idcc,
                reasoning=reasoning
            )
            return mock_response
        return _mock

    def test_route_general_query_to_code_only(self, mock_openai_response):
        """Test general labor law query routes to code_travail only."""
        with patch.object(RoutingAgent, '_llm_route') as mock_llm:
            mock_llm.return_value = RoutingDecision(
                strategy="code_only",
                idcc=None,
                reasoning="General legal question, no industry specified"
            )

            agent = RoutingAgent()
            decision = agent.route("Quelle est la durée du préavis de démission?")

            assert decision.strategy == "code_only"
            assert decision.collections == ["code_travail"]
            assert decision.idcc is None

    def test_route_it_engineer_to_syntec(self, mock_openai_response):
        """Test IT engineer query routes to Syntec IDCC 1486."""
        with patch.object(RoutingAgent, '_llm_route') as mock_llm:
            mock_llm.return_value = RoutingDecision(
                strategy="both_kali_first",
                idcc="1486",
                reasoning="IT engineer (Syntec convention)"
            )

            agent = RoutingAgent()
            decision = agent.route("Période d'essai pour un ingénieur informatique")

            assert decision.strategy == "both_kali_first"
            assert decision.collections == ["kali", "code_travail"]
            assert decision.idcc == "1486"

    def test_route_explicit_convention_to_kali_only(self, mock_openai_response):
        """Test explicit convention mention routes to kali_only."""
        with patch.object(RoutingAgent, '_llm_route') as mock_llm:
            mock_llm.return_value = RoutingDecision(
                strategy="kali_only",
                idcc="1486",
                reasoning="Explicitly asks about Syntec convention"
            )

            agent = RoutingAgent()
            decision = agent.route("Convention Syntec congés payés")

            assert decision.strategy == "kali_only"
            assert decision.collections == ["kali"]
            assert decision.idcc == "1486"

    def test_fallback_on_llm_error(self):
        """Test fallback to code_only when LLM fails."""
        with patch.object(RoutingAgent, '_llm_route') as mock_llm:
            mock_llm.side_effect = Exception("OpenAI API error")

            agent = RoutingAgent()
            decision = agent.route("Test query")

            # Should fallback to code_only
            assert decision.strategy == "code_only"
            assert decision.collections == ["code_travail"]
            assert decision.idcc is None
            assert "Fallback" in decision.reasoning

    def test_singleton_pattern(self):
        """Test get_routing_agent returns same instance."""
        agent1 = get_routing_agent()
        agent2 = get_routing_agent()
        assert agent1 is agent2


@pytest.mark.integration
class TestRoutingAgentIntegration:
    """Integration tests with real OpenAI API (requires API key)."""

    @pytest.mark.skip(reason="Requires OpenAI API key and costs money")
    def test_real_openai_call(self):
        """Test real OpenAI API call (skipped by default)."""
        agent = get_routing_agent()
        decision = agent.route("Période d'essai pour un développeur")

        # Should detect IT role and route to Syntec
        assert decision.idcc == "1486"
        assert "kali" in decision.collections

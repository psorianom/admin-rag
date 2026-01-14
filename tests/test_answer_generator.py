"""Tests for answer generation with citations."""

import pytest
from unittest.mock import Mock, patch
from src.agents.answer_generator import (
    AnswerGenerator,
    AnswerWithCitations,
    get_answer_generator,
)


class TestAnswerWithCitations:
    """Test AnswerWithCitations Pydantic model."""

    def test_valid_answer(self):
        """Test valid answer creation."""
        answer = AnswerWithCitations(
            answer="La période d'essai dure maximum 2 mois.",
            confidence=0.85,
            citation_indices=[0, 1],
            reasoning="Cité par Source 1 et Source 2"
        )
        assert answer.answer == "La période d'essai dure maximum 2 mois."
        assert answer.confidence == 0.85
        assert answer.citation_indices == [0, 1]

    def test_default_confidence(self):
        """Test default confidence value."""
        answer = AnswerWithCitations(
            answer="Test",
            reasoning="Test"
        )
        assert answer.confidence == 0.7

    def test_empty_citation_indices(self):
        """Test empty citation indices by default."""
        answer = AnswerWithCitations(
            answer="Test",
            reasoning="Test"
        )
        assert answer.citation_indices == []

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            AnswerWithCitations(
                answer="Test",
                confidence=1.5,  # Invalid
                reasoning="Test"
            )

        with pytest.raises(Exception):  # Pydantic ValidationError
            AnswerWithCitations(
                answer="Test",
                confidence=-0.1,  # Invalid
                reasoning="Test"
            )


class TestAnswerGenerator:
    """Test AnswerGenerator behavior."""

    @pytest.fixture
    def sample_results(self):
        """Sample retrieved results."""
        return [
            {
                "content": "La durée de la période d'essai est d'un mois.",
                "metadata": {
                    "article_num": "L1221-19",
                    "source": "code_travail",
                    "convention_name": None
                },
                "score": 0.85,
                "_collection": "code_travail"
            },
            {
                "content": "Selon la convention Syntec, la période d'essai est de 2 mois.",
                "metadata": {
                    "article_num": "2.3",
                    "source": "kali",
                    "convention_name": "Syntec",
                    "idcc": "1486"
                },
                "score": 0.82,
                "_collection": "kali",
                "_convention": "1486"
            },
            {
                "content": "La période d'essai peut être renouvelée une fois.",
                "metadata": {
                    "article_num": "L1221-20",
                    "source": "code_travail"
                },
                "score": 0.78,
                "_collection": "code_travail"
            }
        ]

    def test_answer_generation_from_results(self, sample_results):
        """Test answer generation from retrieved results."""
        with patch.object(AnswerGenerator, '_get_system_prompt') as mock_prompt:
            mock_prompt.return_value = "System prompt"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                # Mock the response
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="La période d'essai dure un mois selon le code du travail.",
                    confidence=0.85,
                    citation_indices=[0],
                    reasoning="Cité par Source 1"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                answer = agent.generate("Quelle est la durée de la période d'essai?", sample_results)

                assert answer.answer == "La période d'essai dure un mois selon le code du travail."
                assert answer.confidence == 0.85
                assert answer.citation_indices == [0]

    def test_handles_empty_results(self):
        """Test graceful handling of empty results."""
        with patch('src.agents.answer_generator.OpenAI'):
            agent = AnswerGenerator()
            answer = agent.generate("Test query", [])

            assert answer.answer == "Aucune information disponible pour répondre à cette question."
            assert answer.confidence == 0.0
            assert answer.citation_indices == []

    def test_citation_indices_validation(self, sample_results):
        """Test that invalid citation indices are filtered."""
        with patch.object(AnswerGenerator, '_get_system_prompt') as mock_prompt:
            mock_prompt.return_value = "System prompt"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                # Mock response with invalid citation index
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="Test answer",
                    confidence=0.7,
                    citation_indices=[0, 5, 10],  # 5 and 10 are invalid (only 3 results)
                    reasoning="Test"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                answer = agent.generate("Test", sample_results)

                # Only valid indices should remain
                assert answer.citation_indices == [0]

    def test_answer_generation_uses_top_3_results(self, sample_results):
        """Test that answer generation uses only top 3 results."""
        with patch.object(AnswerGenerator, '_build_context') as mock_context:
            mock_context.return_value = "Context"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="Test",
                    confidence=0.7,
                    citation_indices=[],
                    reasoning="Test"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                # Pass 5 results (more than 3)
                results = sample_results + [sample_results[0], sample_results[1]]
                agent.generate("Test", results)

                # _build_context should be called with top 3
                mock_context.assert_called_once()
                call_args = mock_context.call_args[0][0]
                assert len(call_args) == 3

    def test_context_building(self, sample_results):
        """Test context building from results."""
        with patch('src.agents.answer_generator.OpenAI'):
            agent = AnswerGenerator()
            context = agent._build_context(sample_results[:3])

            # Should include all 3 results
            assert "[Source 1]" in context
            assert "[Source 2]" in context
            assert "[Source 3]" in context

            # Should include article numbers
            assert "L1221-19" in context
            assert "2.3" in context
            assert "L1221-20" in context

            # Should include content
            assert "La durée de la période d'essai" in context

    def test_context_building_with_convention_info(self, sample_results):
        """Test context building includes convention information."""
        with patch('src.agents.answer_generator.OpenAI'):
            agent = AnswerGenerator()
            context = agent._build_context([sample_results[1]])  # KALI result

            # Should include convention and IDCC
            assert "Syntec" in context
            assert "1486" in context

    def test_answer_generation_error_handling(self, sample_results):
        """Test graceful error handling when LLM fails."""
        with patch('src.agents.answer_generator.OpenAI') as mock_openai:
            mock_openai.return_value.beta.chat.completions.parse.side_effect = Exception("API Error")

            agent = AnswerGenerator()
            answer = agent.generate("Test query", sample_results)

            # Should return fallback answer
            assert answer.answer == "Je n'ai pas pu générer une réponse à cette question."
            assert answer.confidence == 0.0
            assert answer.citation_indices == []

    def test_singleton_pattern(self):
        """Test get_answer_generator returns same instance."""
        with patch('src.agents.answer_generator.OpenAI'):
            gen1 = get_answer_generator()
            gen2 = get_answer_generator()
            assert gen1 is gen2

    def test_multiple_citation_indices(self, sample_results):
        """Test answer with multiple citations."""
        with patch.object(AnswerGenerator, '_get_system_prompt') as mock_prompt:
            mock_prompt.return_value = "System prompt"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="Answer citing multiple sources",
                    confidence=0.9,
                    citation_indices=[0, 1],
                    reasoning="Both sources support this"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                answer = agent.generate("Test", sample_results)

                assert len(answer.citation_indices) == 2
                assert answer.confidence == 0.9

    def test_confidence_scoring_high(self, sample_results):
        """Test high confidence for definitive answers."""
        with patch.object(AnswerGenerator, '_get_system_prompt') as mock_prompt:
            mock_prompt.return_value = "System prompt"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="Clear answer",
                    confidence=0.95,  # Very high confidence
                    citation_indices=[0],
                    reasoning="Clearly supported"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                answer = agent.generate("Test", sample_results)

                assert answer.confidence >= 0.9

    def test_confidence_scoring_low(self, sample_results):
        """Test low confidence for uncertain answers."""
        with patch.object(AnswerGenerator, '_get_system_prompt') as mock_prompt:
            mock_prompt.return_value = "System prompt"

            with patch('src.agents.answer_generator.OpenAI') as mock_openai:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.parsed = AnswerWithCitations(
                    answer="Uncertain answer",
                    confidence=0.45,  # Low confidence
                    citation_indices=[],
                    reasoning="Insufficient information"
                )
                mock_openai.return_value.beta.chat.completions.parse.return_value = mock_response

                agent = AnswerGenerator()
                answer = agent.generate("Test", sample_results)

                assert answer.confidence <= 0.5


@pytest.mark.integration
class TestAnswerGeneratorIntegration:
    """Integration tests with real OpenAI API (requires API key)."""

    @pytest.mark.skip(reason="Requires OpenAI API key and costs money")
    def test_real_openai_answer_generation(self):
        """Test real OpenAI API answer generation (skipped by default)."""
        sample_results = [
            {
                "content": "La période d'essai dure un mois selon l'article L1221-19.",
                "metadata": {"article_num": "L1221-19", "source": "code_travail"},
                "score": 0.85,
                "_collection": "code_travail"
            }
        ]

        agent = get_answer_generator()
        answer = agent.generate("Quelle est la durée de la période d'essai?", sample_results)

        # Verify answer structure
        assert answer.answer  # Non-empty answer
        assert 0 <= answer.confidence <= 1  # Valid confidence
        assert isinstance(answer.citation_indices, list)
        assert answer.reasoning  # Non-empty reasoning

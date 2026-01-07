"""
Analyze article text lengths to inform chunking strategy.
"""

import json
from pathlib import Path
from collections import Counter


def count_tokens_simple(text: str) -> int:
    """Simple token count approximation (words)."""
    return len(text.split())


def analyze_lengths():
    """Analyze article lengths from processed JSONL."""

    input_path = Path("data/processed/code_travail_articles.jsonl")

    lengths = []

    print("Analyzing article lengths...")

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            article = json.loads(line)
            text = article.get('text', '')
            token_count = count_tokens_simple(text)
            lengths.append(token_count)

    # Statistics
    total = len(lengths)
    under_500 = sum(1 for l in lengths if l < 500)
    between_500_1000 = sum(1 for l in lengths if 500 <= l < 1000)
    over_1000 = sum(1 for l in lengths if l >= 1000)

    avg_length = sum(lengths) / len(lengths) if lengths else 0
    max_length = max(lengths) if lengths else 0
    min_length = min(lengths) if lengths else 0

    print("\n" + "="*60)
    print("ARTICLE LENGTH ANALYSIS")
    print("="*60)
    print(f"Total articles: {total}")
    print(f"Average length: {avg_length:.1f} tokens")
    print(f"Min length: {min_length} tokens")
    print(f"Max length: {max_length} tokens")
    print()
    print(f"Articles < 500 tokens: {under_500} ({under_500/total*100:.1f}%)")
    print(f"Articles 500-1000 tokens: {between_500_1000} ({between_500_1000/total*100:.1f}%)")
    print(f"Articles > 1000 tokens: {over_1000} ({over_1000/total*100:.1f}%)")
    print()
    print(f"Articles needing chunking (>500): {between_500_1000 + over_1000} ({(between_500_1000 + over_1000)/total*100:.1f}%)")

    # Show some long articles
    print("\n" + "="*60)
    print("SAMPLE LONG ARTICLES (>1000 tokens)")
    print("="*60)

    with open(input_path, 'r', encoding='utf-8') as f:
        count = 0
        for line in f:
            article = json.loads(line)
            text = article.get('text', '')
            token_count = count_tokens_simple(text)

            if token_count > 1000 and count < 3:
                print(f"\nArticle {article['article_num']} - {token_count} tokens")
                print(f"Text preview: {text[:200]}...")
                count += 1


if __name__ == "__main__":
    analyze_lengths()

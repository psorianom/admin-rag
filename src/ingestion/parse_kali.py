"""
Main script to parse KALI corpus (conventions collectives).
"""

from pathlib import Path
import json
from parsers.kali_parser import KaliParser
from chunkers.article_chunker import ArticleChunker


def main():
    """Parse KALI: articles then chunk them."""

    # Paths
    articles_dir = Path("data/raw/kali/kali/global/article")
    articles_output = Path("data/processed/kali_articles.jsonl")
    chunks_output = Path("data/processed/kali_chunks.jsonl")

    print("="*60)
    print("STEP 1: Parsing KALI articles (top 10 conventions)")
    print("="*60)

    parser = KaliParser(articles_dir)
    articles = parser.parse_all_articles(articles_output)

    print("\n" + "="*60)
    print("STEP 2: Chunking KALI articles")
    print("="*60 + "\n")

    chunker = ArticleChunker(max_tokens=500)
    stats = chunker.chunk_all_articles(articles_output, chunks_output)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total KALI articles: {len(articles)}")
    print(f"Total KALI chunks: {stats['total_chunks']}")
    print(f"Output saved to: {chunks_output}")

    # Show sample
    if articles:
        print("\n" + "="*60)
        print("SAMPLE KALI ARTICLE")
        print("="*60)
        sample = articles[0]
        print(json.dumps(sample, indent=2, ensure_ascii=False)[:500] + "...")


if __name__ == "__main__":
    main()

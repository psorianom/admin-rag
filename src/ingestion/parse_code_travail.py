"""
Main script to parse Code du travail XML files.
Runs section parser first, then article parser with section enrichment.
"""

from pathlib import Path
import json
from parsers.section_parser import SectionParser
from parsers.code_travail_parser import CodeTravailParser


def main():
    """Parse Code du travail: sections first, then articles."""

    # Paths
    base_dir = Path("data/raw/code_travail_LEGITEXT000006072050")
    sections_dir = base_dir / "section_ta"
    articles_dir = base_dir / "article"

    section_mapping_path = Path("data/processed/article_to_section_mapping.json")
    output_path = Path("data/processed/code_travail_articles.jsonl")

    print("="*60)
    print("STEP 1: Parsing section metadata")
    print("="*60)

    section_parser = SectionParser(sections_dir)
    section_mapping = section_parser.save_mapping(section_mapping_path)

    print("\n" + "="*60)
    print("STEP 2: Parsing articles with section enrichment")
    print("="*60 + "\n")

    article_parser = CodeTravailParser(articles_dir, section_mapping)
    articles = article_parser.parse_all_articles(output_path)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total valid articles: {len(articles)}")
    print(f"Articles with section metadata: {sum(1 for a in articles if a.get('section_title'))}")
    print(f"Output saved to: {output_path}")

    # Show sample
    if articles:
        print("\n" + "="*60)
        print("SAMPLE ARTICLE")
        print("="*60)
        sample = next((a for a in articles if a.get('section_title')), articles[0])
        print(json.dumps(sample, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

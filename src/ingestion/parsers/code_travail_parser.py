"""
Parser for Code du travail XML files from Legifrance.
Filters out obsolete (ABROGE) articles and extracts relevant metadata.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime


class CodeTravailParser:
    """Parse Code du travail XML articles and filter obsolete ones."""

    def __init__(self, articles_dir: Path, section_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize parser with path to articles directory.

        Args:
            articles_dir: Path to directory containing article XML files
            section_mapping: Optional dict mapping article_id -> section_title
        """
        self.articles_dir = Path(articles_dir)
        self.section_mapping = section_mapping or {}

    def parse_article(self, xml_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single article XML file.

        Returns None if article is obsolete (ABROGE), otherwise returns dict with:
        - article_id: Unique identifier
        - article_num: Article number (e.g., "L6234-2")
        - etat: Current state (VIGUEUR, MODIFIE, etc.)
        - date_debut: Start date
        - date_fin: End date (if applicable)
        - text: Article text content
        - hierarchy: Structural context (partie, livre, titre, chapitre)
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Extract basic metadata
            article_id = root.find('.//ID').text if root.find('.//ID') is not None else None
            article_num = root.find('.//NUM').text if root.find('.//NUM') is not None else None
            etat = root.find('.//ETAT').text if root.find('.//ETAT') is not None else None

            # Filter out obsolete articles
            if etat == "ABROGE":
                return None

            # Extract dates
            date_debut = root.find('.//DATE_DEBUT').text if root.find('.//DATE_DEBUT') is not None else None
            date_fin = root.find('.//DATE_FIN').text if root.find('.//DATE_FIN') is not None else None

            # Filter out historical versions - keep only currently valid articles
            # date_fin = "2999-01-01" means "currently valid, no end date"
            if date_fin and date_fin != "2999-01-01":
                return None

            # Extract article text
            text_content = ""
            bloc_textuel = root.find('.//BLOC_TEXTUEL/CONTENU')
            if bloc_textuel is not None:
                # Get all text content, stripping HTML tags
                text_content = ET.tostring(bloc_textuel, encoding='unicode', method='text')
                text_content = text_content.strip()

            # Extract hierarchical context
            hierarchy = self._extract_hierarchy(root)

            # Add section title if available
            section_title = self.section_mapping.get(article_id, None)

            return {
                "article_id": article_id,
                "article_num": article_num,
                "etat": etat,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "text": text_content,
                "hierarchy": hierarchy,
                "section_title": section_title,
                "source": "code_travail",
                "obsolete": False
            }

        except Exception as e:
            print(f"Error parsing {xml_path}: {e}")
            return None

    def _extract_hierarchy(self, root) -> Dict[str, str]:
        """Extract hierarchical structure from CONTEXTE section."""
        hierarchy = {}

        contexte = root.find('.//CONTEXTE')
        if contexte is None:
            return hierarchy

        # Look for nested TITRE_TM elements (they represent: Partie, Livre, Titre, Chapitre, Section)
        titre_elements = contexte.findall('.//TITRE_TM')

        for i, titre in enumerate(titre_elements):
            level_name = f"level_{i}"
            titre_text = titre.text.strip() if titre.text else ""

            # Try to identify what kind of division this is
            if "partie" in titre_text.lower():
                hierarchy["partie"] = titre_text
            elif "livre" in titre_text.lower():
                hierarchy["livre"] = titre_text
            elif "titre" in titre_text.lower():
                hierarchy["titre"] = titre_text
            elif "chapitre" in titre_text.lower():
                hierarchy["chapitre"] = titre_text
            elif "section" in titre_text.lower():
                hierarchy["section"] = titre_text
            else:
                hierarchy[level_name] = titre_text

        return hierarchy

    def parse_all_articles(self, output_path: Optional[Path] = None) -> list[Dict[str, Any]]:
        """
        Parse all article XML files and filter obsolete ones.

        Args:
            output_path: If provided, save results as JSONL to this path

        Returns:
            List of valid (non-obsolete) articles
        """
        all_articles = []
        obsolete_count = 0
        error_count = 0

        # Find all XML files in articles directory
        xml_files = list(self.articles_dir.rglob("*.xml"))
        total_files = len(xml_files)

        print(f"Found {total_files} article XML files")
        print("Parsing articles...")

        for i, xml_file in enumerate(xml_files):
            if (i + 1) % 5000 == 0:
                print(f"Processed {i + 1}/{total_files} files...")

            article = self.parse_article(xml_file)

            if article is None:
                obsolete_count += 1
            elif article:
                all_articles.append(article)
            else:
                error_count += 1

        print(f"\nParsing complete!")
        print(f"Valid articles (current versions only): {len(all_articles)}")
        print(f"Filtered out: {obsolete_count} (ABROGE + historical versions)")
        print(f"Errors: {error_count}")

        # Save to JSONL if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                for article in all_articles:
                    f.write(json.dumps(article, ensure_ascii=False) + '\n')

            print(f"Saved to {output_path}")

        return all_articles


if __name__ == "__main__":
    # Example usage
    articles_dir = Path("data/raw/code_travail_LEGITEXT000006072050/article")
    output_path = Path("data/processed/code_travail_articles.jsonl")
    section_mapping_path = Path("data/processed/article_to_section_mapping.json")

    # Load section mapping if available
    section_mapping = {}
    if section_mapping_path.exists():
        print(f"Loading section mapping from {section_mapping_path}")
        with open(section_mapping_path, 'r', encoding='utf-8') as f:
            section_mapping = json.load(f)
        print(f"Loaded {len(section_mapping)} article-to-section mappings\n")
    else:
        print("No section mapping found. Run section_parser.py first for richer metadata.\n")

    parser = CodeTravailParser(articles_dir, section_mapping)
    articles = parser.parse_all_articles(output_path)

    # Print a sample article
    if articles:
        print("\nSample article:")
        print(json.dumps(articles[0], indent=2, ensure_ascii=False))

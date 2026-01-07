"""
Parser for KALI corpus (conventions collectives).
Extracts articles from top 10 conventions by IDCC code.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List, Any
import json


# Top 10 conventions collectives by sector importance
TOP_10_CONVENTIONS = {
    "3248": "Métallurgie (Convention unique)",
    "1486": "Bureaux d'études techniques (Syntec)",
    "1979": "Hôtels, cafés, restaurants (HCR)",
    "1597": "Bâtiment (Ouvriers - plus de 10 sal.)",
    "1090": "Services de l'automobile",
    "2216": "Commerce de détail et de gros à prédominance alimentaire",
    "0016": "Transports routiers",
    "0044": "Industries chimiques",
    "2120": "Banque",
    "0573": "Commerces de gros"
}


class KaliParser:
    """Parse KALI articles from top 10 conventions collectives."""

    def __init__(self, articles_dir: Path, section_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize parser with path to articles directory.

        Args:
            articles_dir: Path to directory containing KALI article XML files
            section_mapping: Optional dict mapping article_id -> section_title
        """
        self.articles_dir = Path(articles_dir)
        self.section_mapping = section_mapping or {}
        self.target_idcc = set(TOP_10_CONVENTIONS.keys())

    def parse_article(self, xml_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single KALI article XML file.

        Returns None if article doesn't belong to target conventions or is obsolete.
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Extract IDCC number from CONTENEUR to filter conventions
            conteneur = root.find('.//CONTENEUR[@nature="IDCC"]')
            if conteneur is None:
                return None

            idcc_num = conteneur.get('num')
            if not idcc_num or idcc_num not in self.target_idcc:
                return None

            # Get convention name
            convention_name = TOP_10_CONVENTIONS.get(idcc_num, f"IDCC {idcc_num}")

            # Extract basic metadata
            article_id = root.find('.//ID').text if root.find('.//ID') is not None else None
            article_num = root.find('.//NUM').text if root.find('.//NUM') is not None else None
            etat = root.find('.//ETAT').text if root.find('.//ETAT') is not None else None

            # Filter out obsolete articles (similar states as Code du travail)
            if etat in ["ABROGE", "PERIME"]:
                return None

            # Extract dates
            date_debut = root.find('.//DATE_DEBUT').text if root.find('.//DATE_DEBUT') is not None else None
            date_fin = root.find('.//DATE_FIN').text if root.find('.//DATE_FIN') is not None else None

            # Filter out historical versions - keep only currently valid articles
            if date_fin and date_fin != "2999-01-01":
                return None

            # Extract article text
            text_content = ""
            bloc_textuel = root.find('.//BLOC_TEXTUEL/CONTENU')
            if bloc_textuel is not None:
                text_content = ET.tostring(bloc_textuel, encoding='unicode', method='text')
                text_content = text_content.strip()

            # Extract hierarchical context (similar to Code du travail)
            hierarchy = self._extract_hierarchy(root)

            # Get convention title from CONTEXTE/TEXTE
            convention_title = None
            texte = root.find('.//CONTEXTE/TEXTE')
            if texte is not None:
                titre_txt = texte.find('.//TITRE_TXT')
                if titre_txt is not None:
                    convention_title = titre_txt.text

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
                "idcc": idcc_num,
                "convention_name": convention_name,
                "convention_title": convention_title,
                "source": "kali",
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

        # KALI uses TITRE_TM elements for structure
        titre_elements = contexte.findall('.//TITRE_TM')

        for i, titre in enumerate(titre_elements):
            if titre.text:
                titre_text = titre.text.strip()
                # Use generic level names since KALI structure varies
                hierarchy[f"level_{i}"] = titre_text

        return hierarchy

    def parse_all_articles(self, output_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Parse all KALI articles from target conventions.

        Args:
            output_path: If provided, save results as JSONL to this path

        Returns:
            List of valid articles from top 10 conventions
        """
        all_articles = []
        filtered_count = 0  # Not in target conventions or obsolete
        error_count = 0
        idcc_counts = {idcc: 0 for idcc in self.target_idcc}

        # Find all XML files
        xml_files = list(self.articles_dir.rglob("*.xml"))
        total_files = len(xml_files)

        print(f"Found {total_files} KALI article XML files")
        print(f"Filtering for top 10 conventions: {', '.join(TOP_10_CONVENTIONS.keys())}")
        print("Parsing articles...")

        for i, xml_file in enumerate(xml_files):
            if (i + 1) % 10000 == 0:
                print(f"Processed {i + 1}/{total_files} files...")

            article = self.parse_article(xml_file)

            if article is None:
                filtered_count += 1
            elif article:
                all_articles.append(article)
                idcc_counts[article['idcc']] += 1
            else:
                error_count += 1

        print(f"\nParsing complete!")
        print(f"Valid articles (current versions from top 10): {len(all_articles)}")
        print(f"Filtered out: {filtered_count} (other conventions + obsolete + historical)")
        print(f"Errors: {error_count}")

        # Show breakdown by convention
        print(f"\nArticles by convention:")
        for idcc, count in sorted(idcc_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  IDCC {idcc} ({TOP_10_CONVENTIONS[idcc]}): {count} articles")

        # Save to JSONL if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                for article in all_articles:
                    f.write(json.dumps(article, ensure_ascii=False) + '\n')

            print(f"\nSaved to {output_path}")

        return all_articles


if __name__ == "__main__":
    # Example usage
    articles_dir = Path("data/raw/kali/kali/global/article")
    output_path = Path("data/processed/kali_articles.jsonl")
    section_mapping_path = Path("data/processed/kali_article_to_section_mapping.json")

    # Load section mapping if available
    section_mapping = {}
    if section_mapping_path.exists():
        print(f"Loading section mapping from {section_mapping_path}")
        with open(section_mapping_path, 'r', encoding='utf-8') as f:
            section_mapping = json.load(f)
        print(f"Loaded {len(section_mapping)} article-to-section mappings\n")
    else:
        print("No section mapping found. Run kali_section_parser.py first for richer metadata.\n")

    parser = KaliParser(articles_dir, section_mapping)
    articles = parser.parse_all_articles(output_path)

    # Print a sample article from each convention
    if articles:
        print("\n" + "="*60)
        print("SAMPLE ARTICLES")
        print("="*60)
        seen_idcc = set()
        for article in articles:
            idcc = article['idcc']
            if idcc not in seen_idcc and len(seen_idcc) < 3:
                seen_idcc.add(idcc)
                print(f"\nIDCC {idcc} - {article['convention_name']}")
                print(f"Article {article['article_num']}")
                print(f"Text preview: {article['text'][:200]}...")

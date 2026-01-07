"""
Parser for Code du travail section metadata files.
Extracts section titles and article groupings.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List
import json


class SectionParser:
    """Parse Code du travail section structure files."""

    def __init__(self, sections_dir: Path):
        """
        Initialize parser with path to sections directory.

        Args:
            sections_dir: Path to directory containing section_ta XML files
        """
        self.sections_dir = Path(sections_dir)

    def parse_section(self, xml_path: Path) -> Dict:
        """
        Parse a single section XML file.

        Returns dict with:
        - section_id: Unique identifier
        - section_title: Section title (e.g., "Paragraphe 3: Modalités particulières...")
        - article_ids: List of article IDs in this section
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            section_id = root.find('.//ID').text if root.find('.//ID') is not None else None
            section_title = root.find('.//TITRE_TA').text if root.find('.//TITRE_TA') is not None else None

            # Extract article IDs from STRUCTURE_TA
            article_ids = []
            structure = root.find('.//STRUCTURE_TA')
            if structure is not None:
                for lien in structure.findall('.//LIEN_ART'):
                    article_id = lien.get('id')
                    if article_id:
                        article_ids.append(article_id)

            return {
                "section_id": section_id,
                "section_title": section_title,
                "article_ids": article_ids
            }

        except Exception as e:
            print(f"Error parsing {xml_path}: {e}")
            return None

    def build_article_to_section_map(self) -> Dict[str, str]:
        """
        Build a mapping from article ID to section title.

        Returns:
            Dict mapping article_id -> section_title
        """
        article_to_section = {}

        xml_files = list(self.sections_dir.rglob("*.xml"))
        total_files = len(xml_files)

        print(f"Found {total_files} section XML files")
        print("Building article-to-section mapping...")

        for i, xml_file in enumerate(xml_files):
            if (i + 1) % 2000 == 0:
                print(f"Processed {i + 1}/{total_files} sections...")

            section = self.parse_section(xml_file)
            if section and section["section_title"]:
                for article_id in section["article_ids"]:
                    # If article appears in multiple sections, keep the first one
                    if article_id not in article_to_section:
                        article_to_section[article_id] = section["section_title"]

        print(f"Mapped {len(article_to_section)} articles to sections")
        return article_to_section

    def save_mapping(self, output_path: Path):
        """Save article-to-section mapping to JSON file."""
        mapping = self.build_article_to_section_map()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        print(f"Saved mapping to {output_path}")
        return mapping


if __name__ == "__main__":
    sections_dir = Path("data/raw/code_travail_LEGITEXT000006072050/section_ta")
    output_path = Path("data/processed/article_to_section_mapping.json")

    parser = SectionParser(sections_dir)
    mapping = parser.save_mapping(output_path)

    # Show sample
    print("\nSample mappings:")
    for article_id, section_title in list(mapping.items())[:5]:
        print(f"{article_id}: {section_title}")

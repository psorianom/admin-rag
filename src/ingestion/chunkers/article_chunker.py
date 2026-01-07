"""
Chunker for Code du travail articles.
Splits long articles (>500 tokens) into semantic chunks.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
import re


class ArticleChunker:
    """Chunk long articles into smaller semantic pieces."""

    def __init__(self, max_tokens: int = 500):
        """
        Initialize chunker.

        Args:
            max_tokens: Target maximum tokens per chunk
        """
        self.max_tokens = max_tokens

    def count_tokens(self, text: str) -> int:
        """Simple token count approximation."""
        return len(text.split())

    def split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs by double newlines or common patterns."""
        # Split by multiple newlines (2 or more)
        paragraphs = re.split(r'\n\s*\n+', text)
        # Also split by numbered lists (1°, 2°, etc.) common in French legal text
        final_paragraphs = []
        for para in paragraphs:
            # Check if paragraph contains numbered points
            if re.search(r'\d+°', para):
                # Split by numbered points
                sub_paras = re.split(r'(\d+°)', para)
                # Recombine number with its content
                current = ""
                for i, part in enumerate(sub_paras):
                    if re.match(r'\d+°', part):
                        if current:
                            final_paragraphs.append(current.strip())
                        current = part
                    else:
                        current += part
                if current:
                    final_paragraphs.append(current.strip())
            else:
                final_paragraphs.append(para.strip())

        return [p for p in final_paragraphs if p]

    def chunk_article(self, article: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a single article if needed.

        Args:
            article: Article dict from JSONL

        Returns:
            List of chunks (each chunk is a dict with metadata + text)
        """
        text = article.get('text', '')
        token_count = self.count_tokens(text)

        # If article is short enough, return as single chunk
        if token_count < self.max_tokens:
            chunk = article.copy()
            chunk['chunk_id'] = f"{article['article_id']}_0"
            chunk['chunk_index'] = 0
            chunk['total_chunks'] = 1
            chunk['is_chunked'] = False
            return [chunk]

        # Article needs chunking
        paragraphs = self.split_into_paragraphs(text)
        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            # If single paragraph is too long, include it anyway (don't split mid-paragraph)
            if para_tokens > self.max_tokens:
                # Flush current chunk if any
                if current_chunk_text:
                    chunks.append('\n\n'.join(current_chunk_text))
                    current_chunk_text = []
                    current_chunk_tokens = 0
                # Add long paragraph as its own chunk
                chunks.append(para)
                continue

            # Check if adding this paragraph would exceed limit
            if current_chunk_tokens + para_tokens > self.max_tokens and current_chunk_text:
                # Flush current chunk
                chunks.append('\n\n'.join(current_chunk_text))
                current_chunk_text = [para]
                current_chunk_tokens = para_tokens
            else:
                # Add to current chunk
                current_chunk_text.append(para)
                current_chunk_tokens += para_tokens

        # Flush remaining
        if current_chunk_text:
            chunks.append('\n\n'.join(current_chunk_text))

        # Create chunk dicts with metadata
        chunk_dicts = []
        for i, chunk_text in enumerate(chunks):
            chunk = article.copy()
            chunk['text'] = chunk_text
            chunk['chunk_id'] = f"{article['article_id']}_{i}"
            chunk['chunk_index'] = i
            chunk['total_chunks'] = len(chunks)
            chunk['is_chunked'] = True
            chunk_dicts.append(chunk)

        return chunk_dicts

    def chunk_all_articles(
        self,
        input_path: Path,
        output_path: Path
    ) -> Dict[str, int]:
        """
        Process all articles from JSONL and output chunked version.

        Args:
            input_path: Input JSONL with articles
            output_path: Output JSONL with chunks

        Returns:
            Stats dict with counts
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_articles = 0
        chunked_articles = 0
        total_chunks = 0

        print("Processing articles...")

        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:

            for line in infile:
                article = json.loads(line)
                total_articles += 1

                chunks = self.chunk_article(article)
                total_chunks += len(chunks)

                if len(chunks) > 1:
                    chunked_articles += 1

                for chunk in chunks:
                    outfile.write(json.dumps(chunk, ensure_ascii=False) + '\n')

                if total_articles % 2000 == 0:
                    print(f"Processed {total_articles} articles...")

        stats = {
            'total_articles': total_articles,
            'articles_chunked': chunked_articles,
            'articles_not_chunked': total_articles - chunked_articles,
            'total_chunks': total_chunks
        }

        print(f"\n" + "="*60)
        print("CHUNKING COMPLETE")
        print("="*60)
        print(f"Total articles processed: {stats['total_articles']}")
        print(f"Articles kept as-is: {stats['articles_not_chunked']} ({stats['articles_not_chunked']/stats['total_articles']*100:.1f}%)")
        print(f"Articles chunked: {stats['articles_chunked']} ({stats['articles_chunked']/stats['total_articles']*100:.1f}%)")
        print(f"Total chunks in output: {stats['total_chunks']}")
        print(f"Saved to: {output_path}")

        return stats


if __name__ == "__main__":
    input_path = Path("data/processed/code_travail_articles.jsonl")
    output_path = Path("data/processed/code_travail_chunks.jsonl")

    chunker = ArticleChunker(max_tokens=500)
    stats = chunker.chunk_all_articles(input_path, output_path)

    # Show a sample chunked article
    print(f"\n" + "="*60)
    print("SAMPLE CHUNKED ARTICLE")
    print("="*60)

    with open(output_path, 'r', encoding='utf-8') as f:
        for line in f:
            chunk = json.loads(line)
            if chunk.get('is_chunked') and chunk.get('chunk_index') == 0:
                print(f"\nArticle {chunk['article_num']} - Split into {chunk['total_chunks']} chunks")
                print(f"Chunk 0 text ({chunker.count_tokens(chunk['text'])} tokens):")
                print(chunk['text'][:300] + "...")
                break

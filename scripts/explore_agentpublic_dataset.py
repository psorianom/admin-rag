"""
Explore AgentPublic/legi dataset to understand Code du travail coverage.

This script streams the dataset without downloading everything to:
1. Count how many Code du travail chunks exist
2. Identify the category labels used
3. Sample a few examples to compare with our processing
"""

from datasets import load_dataset
from collections import Counter
import json
import sys

def explore_dataset(sample_size=None):
    print("Loading AgentPublic/legi dataset in streaming mode...")
    if sample_size:
        print(f"Sampling first {sample_size:,} records for quick exploration.\n")
    else:
        print("Scanning ALL 1.26M records (this will take a few minutes).\n")

    dataset = load_dataset("AgentPublic/legi", streaming=True, split='train')

    # Limit to sample if specified
    if sample_size:
        dataset = dataset.take(sample_size)

    # Tracking
    code_travail_count = 0
    total_count = 0
    categories = Counter()
    titles = Counter()
    sample_examples = []
    code_category_samples = []  # Samples where category='CODE'

    for example in dataset:
        total_count += 1
        category = example.get('category', '')
        categories[category] += 1

        title = example.get('title', '') or example.get('full_title', '')
        if title:
            titles[title] += 1

        # Collect samples where category='CODE' to see what titles look like
        if category == 'CODE' and len(code_category_samples) < 10:
            code_category_samples.append({
                'title': title,
                'full_title': example.get('full_title', '')[:100],
                'chunk_id': example.get('chunk_id')
            })

        # Check if this is Code du travail
        # Filter by category='CODE' AND title contains 'travail'
        is_code = category == 'CODE'
        is_travail = 'travail' in title.lower() if title else False

        if is_code and is_travail:
            code_travail_count += 1

            # Collect first 3 examples
            if len(sample_examples) < 3:
                sample_examples.append({
                    'chunk_id': example.get('chunk_id'),
                    'category': category,
                    'nature': example.get('nature'),
                    'title': example.get('title', '')[:100],
                    'chunk_text': example.get('chunk_text', '')[:200],
                    'chunk_index': example.get('chunk_index'),
                    'status': example.get('status'),
                    'start_date': example.get('start_date'),
                    'end_date': example.get('end_date')
                })

            # Progress updates
            if code_travail_count % 1000 == 0:
                print(f"Progress: {total_count:,} total | {code_travail_count:,} Code du travail found")

    # Results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"\nTotal records scanned: {total_count:,}")
    print(f"Code du travail chunks: {code_travail_count:,}")
    print(f"Percentage: {(code_travail_count/total_count)*100:.2f}%")

    print("\n" + "-"*80)
    print("TOP 20 CATEGORIES:")
    print("-"*80)
    for cat, count in categories.most_common(20):
        print(f"{cat:50s} {count:>10,}")

    print("\n" + "-"*80)
    print("SAMPLE RECORDS WHERE category='CODE':")
    print("-"*80)
    if code_category_samples:
        for i, sample in enumerate(code_category_samples, 1):
            print(f"\n{i}. Title: {sample['title']}")
            print(f"   Full title: {sample['full_title']}")
            print(f"   Chunk ID: {sample['chunk_id']}")
    else:
        print("No records found with category='CODE' in sample")

    print("\n" + "-"*80)
    print("TOP 20 TITLES:")
    print("-"*80)
    for title, count in titles.most_common(20):
        print(f"{title[:70]:70s} {count:>10,}")

    print("\n" + "-"*80)
    print("SAMPLE CODE DU TRAVAIL EXAMPLES:")
    print("-"*80)
    for i, ex in enumerate(sample_examples, 1):
        print(f"\nExample {i}:")
        print(json.dumps(ex, indent=2, ensure_ascii=False))

    # Comparison with our data
    print("\n" + "="*80)
    print("COMPARISON WITH OUR DATA:")
    print("="*80)
    print(f"Our chunks:         11,644")
    print(f"Their chunks:       {code_travail_count:,}")
    print(f"Ratio:              {code_travail_count / 11644:.1f}x")
    print("\nExpected with their chunking (5000 chars, 250 overlap):")
    print("~3-4x more chunks from same content due to longer chunks + overlap")

if __name__ == "__main__":
    # Parse command line argument for sample size
    sample_size = None
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [sample_size]")
            print(f"Example: {sys.argv[0]} 10000  # Sample first 10K records")
            sys.exit(1)

    try:
        explore_dataset(sample_size=sample_size)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

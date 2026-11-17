#!/usr/bin/env python3
"""Verification gate: catch hallucinated skills before they enter the knowledge base.

For each extracted skill, grep substantive keywords from its value
against the raw source text. If none of the skill's nouns/numbers/proper names
appear in the source, the skill is flagged as HALLUCINATED and discarded.

Usage:
  python3 verify_skills.py <source_text_file> <skills_json_file>
  
  skills_json_file: one JSON object per line (category, key, value)
  Outputs: verified_skills.jsonl + hallucinated_skills.jsonl
"""
import sys, json, re

STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
    'should', 'may', 'might', 'must', 'can', 'could', 'in', 'on', 'at',
    'to', 'for', 'of', 'with', 'by', 'from', 'as', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'between', 'under',
    'and', 'but', 'or', 'nor', 'not', 'so', 'yet', 'both', 'either',
    'neither', 'each', 'every', 'all', 'any', 'few', 'more', 'most',
    'other', 'some', 'such', 'no', 'only', 'own', 'same', 'than', 'too',
    'very', 'just', 'because', 'about', 'over', 'this', 'that', 'these',
    'those', 'it', 'its', 'they', 'them', 'their', 'he', 'she', 'his',
    'her', 'who', 'which', 'what', 'when', 'where', 'why', 'how',
    'also', 'if', 'then', 'else', 'there', 'here', 'up', 'out', 'off',
    'down', 'now', 'new', 'use', 'used', 'using', 'one', 'two', 'three',
    'first', 'second', 'third', 'make', 'made', 'get', 'got', 'way',
    'like', 'well', 'back', 'still', 'even', 'much', 'many', 'part',
}

def extract_keywords(value: str) -> set[str]:
    """Extract substantive keywords (nouns, numbers, proper names) from a value."""
    words = re.findall(r'[A-Za-z0-9]+', value)
    keywords = set()
    for w in words:
        low = w.lower()
        if len(low) <= 2:
            continue
        if low in STOP_WORDS:
            continue
        # Keep numbers, capitalized words, and non-trivial words
        if w[0].isupper() or w.isdigit() or len(low) > 4:
            keywords.add(low)
    return keywords

def skill_is_grounded(value: str, source_text: str) -> bool:
    """Check if any substantive keywords from the value appear in the source."""
    keywords = extract_keywords(value)
    if not keywords:
        return True  # Can't verify -> assume grounded
    source_lower = source_text.lower()
    matches = sum(1 for kw in keywords if kw in source_lower)
    # Require at least 2 keyword matches OR 50%+ match rate
    return matches >= 2 or (len(keywords) > 0 and matches / len(keywords) >= 0.5)

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 verify_skills.py <source_text.txt> <skills.jsonl>")
        sys.exit(2)

    with open(sys.argv[1]) as f:
        source_text = f.read()

    verified = []
    hallucinated = []
    
    with open(sys.argv[2]) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                skill = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            value = skill.get('value', '')
            key = skill.get('key', 'unknown')
            
            if skill_is_grounded(value, source_text):
                verified.append(skill)
            else:
                hallucinated.append(skill)
                # Show what was flagged
                kw = extract_keywords(value)
                source_lower = source_text.lower()
                found = [k for k in kw if k in source_lower]
                missing = kw - set(found)
                print(f"HALLUCINATED: {key}")
                print(f"  Value: {value[:120]}...")
                print(f"  Keywords not in source: {sorted(missing)[:8]}")
                print()

    # Write results
    with open('verified_skills.jsonl', 'w') as f:
        for s in verified:
            f.write(json.dumps(s) + '\n')
    with open('hallucinated_skills.jsonl', 'w') as f:
        for s in hallucinated:
            f.write(json.dumps(s) + '\n')

    if verified or hallucinated:
        print(f"Verified: {len(verified)}, Hallucinated: {len(hallucinated)}")
    if hallucinated:
        sys.exit(1)  # Signal that hallucinated skills were found

if __name__ == '__main__':
    main()

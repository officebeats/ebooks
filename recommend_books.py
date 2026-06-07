import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime

# Configurations
BOOKS_JSON_PATH = "books.json"
RECOMMENDATIONS_MD_PATH = "recommendations.md"
RECOMMENDATIONS_JSON_PATH = "recommendations.json"

SEARCH_QUERIES = [
    "artificial intelligence",
    "machine learning",
    "generative AI",
    "large language models",
    "deep learning"
]

def normalize_text(text):
    if not text:
        return ""
    # Lowercase and keep alphanumeric only
    return re.sub(r'[^a-z0-9]', '', text.lower())

def get_normalized_title_variants(title):
    if not title:
        return []
    full_norm = normalize_text(title)
    # Split by colon to get main title without subtitle
    main_title = title.split(':')[0]
    main_norm = normalize_text(main_title)
    
    variants = [full_norm]
    if main_norm != full_norm:
        variants.append(main_norm)
    return variants

def load_owned_titles():
    owned_variants = set()
    if os.path.exists(BOOKS_JSON_PATH):
        try:
            with open(BOOKS_JSON_PATH, 'r', encoding='utf-8') as f:
                db = json.load(f)
                for entry in db.values():
                    title = entry.get("title", "")
                    for var in get_normalized_title_variants(title):
                        owned_variants.add(var)
        except Exception as e:
            print(f"Error reading books.json: {e}")
    return owned_variants

def parse_existing_tally():
    """
    Parses recommendations.md if it exists.
    Returns:
      1. A set of normalized titles that have been checked [x] (already downloaded/bought).
      2. A set of normalized titles that are unchecked [ ] (so we can avoid duplicates).
      3. A list of raw checked lines to carry over/preserve in the tally.
    """
    checked_variants = set()
    unchecked_variants = set()
    checked_raw_lines = []
    
    if os.path.exists(RECOMMENDATIONS_MD_PATH):
        try:
            with open(RECOMMENDATIONS_MD_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    # Match checklist item
                    match = re.match(r'^\s*-\s*\[([ xX])\]\s+(.*)', line)
                    if match:
                        status = match.group(1).lower()
                        content = match.group(2).strip()
                        
                        # Extract title from markdown link e.g. [Title](url)
                        link_match = re.match(r'^\[([^\]]+)\]\(', content)
                        if link_match:
                            title = link_match.group(1)
                        else:
                            title = content.split(' - ')[0]
                        
                        norm_variants = get_normalized_title_variants(title)
                        if status == 'x':
                            for var in norm_variants:
                                checked_variants.add(var)
                            # Keep content for tally preservation (remove trailing comments or details if any)
                            checked_raw_lines.append(content)
                        else:
                            for var in norm_variants:
                                unchecked_variants.add(var)
        except Exception as e:
            print(f"Error reading recommendations.md: {e}")
            
    return checked_variants, unchecked_variants, checked_raw_lines

def parse_publication_date(doc):
    """
    Parses publication year and a best guess YYYY-MM-DD date string.
    Returns (year, date_str).
    """
    year = doc.get("first_publish_year")
    if not year:
        # Fall back to parsing publish_date list
        dates = doc.get("publish_date", [])
        for d in dates:
            match = re.search(r'\d{4}', d)
            if match:
                year = int(match.group(0))
                break
                
    if not year:
        return 0, "0000-00-00"
        
    best_date_str = f"{year:04d}-01-01"
    dates = doc.get("publish_date", [])
    for d in dates:
        # Check YYYY-MM-DD
        match_ymd = re.search(r'(\d{4})-(\d{2})-(\d{2})', d)
        if match_ymd:
            best_date_str = match_ymd.group(0)
            break
        # Check YYYY-MM
        match_ym = re.search(r'(\d{4})-(\d{2})', d)
        if match_ym:
            best_date_str = f"{match_ym.group(1)}-{match_ym.group(2)}-01"
            break
            
    return year, best_date_str

def fetch_open_library_recommendations(query):
    print(f"Querying Open Library for query: '{query}'...")
    encoded = urllib.parse.quote(query)
    url = f"https://openlibrary.org/search.json?q={encoded}&sort=new&limit=40"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'eBooksCatalogApp/1.0 (contact: admin@example.com)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("docs", [])
    except Exception as e:
        print(f"Failed to query Open Library for '{query}': {e}")
        return []

def main():
    current_year = datetime.now().year
    
    print("Loading currently owned titles...")
    owned_variants = load_owned_titles()
    print(f"Loaded {len(owned_variants)} owned title variants.")
    
    print("Parsing existing checklist tally...")
    checked_variants, unchecked_variants, checked_raw_lines = parse_existing_tally()
    print(f"Found {len(checked_variants)} checked and {len(checked_raw_lines)} tally items.")

    # Combine owned and already checked items into exclusion set
    exclusions = owned_variants.union(checked_variants)
    
    all_docs = []
    seen_keys = set()
    seen_normalized_titles = set()
    
    # Query Open Library
    for query in SEARCH_QUERIES:
        docs = fetch_open_library_recommendations(query)
        for doc in docs:
            key = doc.get("key")
            title = doc.get("title")
            
            if not key or not title:
                continue
                
            # Filter out duplicates by Open Library key
            if key in seen_keys:
                continue
                
            # Check English language (if language is present, verify eng is inside)
            languages = doc.get("language", [])
            if languages and "eng" not in languages:
                continue
                
            # Title normalization checks
            title_variants = get_normalized_title_variants(title)
            if not title_variants:
                continue
                
            # Exclude already owned/checked books
            is_excluded = False
            for var in title_variants:
                if var in exclusions:
                    is_excluded = True
                    break
            if is_excluded:
                continue
                
            # Deduplicate titles within recommendations
            is_dup_title = False
            for var in title_variants:
                if var in seen_normalized_titles:
                    is_dup_title = True
                    break
            if is_dup_title:
                continue
                
            # Parse publication year/date
            year, date_str = parse_publication_date(doc)
            
            # Filter out entries with invalid future years
            if year > current_year + 1 or year < 1980:
                continue
                
            # Add to list
            seen_keys.add(key)
            for var in title_variants:
                seen_normalized_titles.add(var)
                
            all_docs.append({
                "title": title,
                "authors": doc.get("author_name", ["Unknown"]),
                "year": year,
                "date": date_str,
                "key": key,
                "subjects": doc.get("subject", [])[:5] # Limit subjects
            })
            
    # Sort recommendations by year and date descending
    all_docs.sort(key=lambda x: (x["year"], x["date"], x["title"]), reverse=True)
    
    # Limit to top 30 recommendations
    top_recommendations = all_docs[:30]
    print(f"Compiled {len(top_recommendations)} top recommendations.")
    
    # Write to recommendations.json
    try:
        with open(RECOMMENDATIONS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(top_recommendations, f, indent=4, ensure_ascii=False)
        print(f"Successfully wrote {RECOMMENDATIONS_JSON_PATH}")
    except Exception as e:
        print(f"Error writing recommendations.json: {e}")
        
    # Write to recommendations.md
    md = "# Book Recommendations & Tally\n\n"
    md += "This document acts as a tracking catalog for new AI and machine learning books you might want to buy or download as EPUB. Reprocessing is automated and will preserve your manually checked-off items.\n\n"
    
    md += "## 🤖 Pending Recommendations\n"
    md += "Here are the top newer releases in AI topics aggregated from Open Library, sorted by release date.\n\n"
    
    if not top_recommendations:
        md += "_No new recommendations found at this time._\n\n"
    else:
        for item in top_recommendations:
            author_str = ", ".join(item["authors"])
            year_str = f" ({item['year']})" if item['year'] else ""
            subjects_str = f" *[Genres: {', '.join(item['subjects'])}]*" if item['subjects'] else ""
            ol_link = f"https://openlibrary.org{item['key']}"
            
            md += f"- [ ] [{item['title']}]({ol_link}) - _by {author_str}_{year_str}{subjects_str}\n"
        md += "\n"
        
    md += "## 💾 Book Tally (Bought/Downloaded)\n"
    md += "Below are the books you have successfully downloaded or purchased. Checked items here are automatically excluded from the recommendations list above when reprocessed.\n\n"
    
    if not checked_raw_lines:
        md += "_No books tallied yet. Check off items in the pending list and reprocess to see them move here!_\n\n"
    else:
        for line in checked_raw_lines:
            # Reformat checked line
            md += f"- [x] {line}\n"
        md += "\n"
        
    md += "## 🔄 Reprocessing Guide\n"
    md += "To refresh the recommendation database and clean up the list while keeping your checked items:\n"
    md += "1. Open a terminal in this directory.\n"
    md += "2. Run the recommendation script:\n"
    md += "   ```bash\n"
    md += "   python recommend_books.py\n"
    md += "   ```\n"
    md += "3. The script will parse this markdown file, preserve all `- [x]` items, filter out currently owned books in `books.json`, fetch new books, and update this file and `recommendations.json` automatically.\n"
    
    try:
        with open(RECOMMENDATIONS_MD_PATH, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"Successfully generated {RECOMMENDATIONS_MD_PATH}")
    except Exception as e:
        print(f"Error writing recommendations.md: {e}")

if __name__ == "__main__":
    main()

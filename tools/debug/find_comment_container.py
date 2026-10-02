from pathlib import Path
from bs4 import BeautifulSoup

html = Path('debug_comment.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Start from root and find divs that contain all three elements
print('=== Looking for comment container from root ===')

# Find all top-level divs
root_divs = soup.find_all('div', recursive=False)
print(f'Found {len(root_divs)} root divs')

# Look for divs containing all three: author, message, timestamp
def find_comment_divs(element, depth=0, max_depth=10):
    if depth > max_depth:
        return []
    
    results = []
    
    if element.name == 'div':
        text = element.get_text()
        has_author = 'Mook Sasii' in text
        has_message = 'ปล่อย 3y สภาพดี' in text or 'มาช่วยซื้อหน่อย' in text
        has_timestamp = 'ชั่วโมง' in text
        
        if has_author and has_message and has_timestamp:
            # Check if this is a minimal container (not too large)
            text_len = len(text)
            if text_len < 500:  # Reasonable size for a single comment
                results.append({
                    'element': element,
                    'depth': depth,
                    'text_length': text_len,
                    'classes': element.get('class', []),
                    'role': element.get('role')
                })
    
    # Recurse into children
    if hasattr(element, 'children'):
        for child in element.children:
            if hasattr(child, 'name') and child.name:
                results.extend(find_comment_divs(child, depth + 1, max_depth))
    
    return results

# Search from root
all_candidates = []
for root_div in root_divs:
    candidates = find_comment_divs(root_div, 0, 15)
    all_candidates.extend(candidates)

print(f'\nFound {len(all_candidates)} candidate comment containers')

# Sort by text length (smaller is better - more specific)
all_candidates.sort(key=lambda x: x['text_length'])

# Show top 3 candidates
for i, candidate in enumerate(all_candidates[:3]):
    print(f'\n=== Candidate {i+1} ===')
    print(f'Depth: {candidate["depth"]}')
    print(f'Text length: {candidate["text_length"]}')
    print(f'Classes: {candidate["classes"][:5]}...')
    print(f'Role: {candidate["role"]}')
    
    elem = candidate['element']
    
    # Try to extract data from this container
    print('\nTrying to extract data:')
    
    # Find author - look for link with /user/ but exclude status indicators
    author_links = elem.find_all('a', href=lambda x: x and '/user/' in x, limit=5)
    author_found = None
    for link in author_links:
        text = link.get_text().strip()
        if text and 'ตัวบ่งชี้' not in text and 'สถานะ' not in text:
            author_found = text
            print(f'  Author: {text}')
            break
    
    if not author_found:
        # Try finding span without link
        author_spans = elem.find_all('span', limit=20)
        for span in author_spans:
            text = span.get_text().strip()
            if text == 'Mook Sasii':
                print(f'  Author (from span): {text}')
                break
    
    # Find message
    message_spans = elem.find_all('span', class_='x193iq5w', limit=2)
    if message_spans:
        print(f'  Message: {message_spans[0].get_text().strip()[:50]}...')
    
    # Find timestamp link
    time_links = elem.find_all('a', href=lambda x: x and 'comment_id' in x, limit=2)
    if time_links:
        time_text = time_links[0].get_text().strip()
        print(f'  Timestamp: {time_text}')
        
        # Extract comment_id
        import re
        match = re.search(r'comment_id=(\d+)', time_links[0].get('href', ''))
        if match:
            print(f'  Comment ID: {match.group(1)}')

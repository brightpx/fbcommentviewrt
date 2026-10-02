from pathlib import Path
from bs4 import BeautifulSoup
import re

html = Path('debug_full_page.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find specific comment ID that failed
target_id = '2106074420815794'
comment_links = soup.find_all('a', href=lambda x: x and f'comment_id={target_id}' in x)

print(f"Found {len(comment_links)} links with comment_id={target_id}")

for i, link in enumerate(comment_links[:1]):
    print(f"\n=== Link {i+1} ===")
    print(f"Link text: {link.get_text().strip()}")
    print(f"Link href: {link.get('href')[:100]}")
    
    # Walk up to find containers
    current = link.parent
    depth = 0
    
    while current and depth < 15:
        if current.name == 'div':
            text = current.get_text()
            text_len = len(text)
            
            # Check for author links
            author_links = current.find_all('a', href=lambda x: x and '/user/' in x)
            
            # Check for message divs
            message_divs = current.find_all('div', dir='auto')
            
            print(f"\nDepth {depth}: div, len={text_len}, author_links={len(author_links)}, message_divs={len(message_divs)}")
            
            if author_links:
                print(f"  Authors found:")
                for a in author_links[:3]:
                    print(f"    - {a.get_text().strip()}")
            
            if message_divs:
                print(f"  Messages found:")
                for m in message_divs[:3]:
                    msg = m.get_text().strip()
                    if msg:
                        print(f"    - {msg[:60]}")
            
            # Stop if we found both
            if author_links and message_divs and 50 < text_len < 1000:
                print(f"\n✓ GOOD CONTAINER at depth {depth}")
                
                # Show the classes
                classes = current.get('class', [])
                print(f"  Classes: {' '.join(classes[:5])}")
                break
        
        current = current.parent
        depth += 1

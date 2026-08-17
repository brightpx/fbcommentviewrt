from pathlib import Path
from bs4 import BeautifulSoup
import re

html = Path('debug_full_page.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find all links with comment_id
comment_links = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
print(f"Found {len(comment_links)} links with comment_id")

# Show first 5
for i, link in enumerate(comment_links[:5]):
    href = link.get('href', '')
    text = link.get_text().strip()
    
    # Extract comment ID
    match = re.search(r'comment_id=(\d+)', href)
    comment_id = match.group(1) if match else 'N/A'
    
    print(f"\n{i+1}. Comment ID: {comment_id}")
    print(f"   Text: {text[:50]}")
    print(f"   Href: {href[:100]}")
    
    # Try to find container
    current = link.parent
    depth = 0
    while current and depth < 10:
        if current.name == 'div':
            text_content = current.get_text()
            text_len = len(text_content)
            if 50 < text_len < 500:
                print(f"   Container found at depth {depth}, length: {text_len}")
                
                # Try to extract author
                author_links = current.find_all('a', href=lambda x: x and '/user/' in x)
                for author_link in author_links:
                    author_text = author_link.get_text().strip()
                    if author_text and len(author_text) > 2 and 'ตัวบ่งชี้' not in author_text:
                        print(f"   Author: {author_text}")
                        break
                
                # Try to extract message
                message_divs = current.find_all('div', dir='auto')
                for msg_div in message_divs:
                    msg_text = msg_div.get_text().strip()
                    if msg_text and 'ชั่วโมง' not in msg_text and 'นาที' not in msg_text:
                        print(f"   Message: {msg_text[:50]}")
                        break
                
                break
        current = current.parent
        depth += 1

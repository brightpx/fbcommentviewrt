from pathlib import Path
from bs4 import BeautifulSoup

html = Path('debug_comment.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find all links
links = soup.find_all('a')
print(f'Total links found: {len(links)}\n')

# Find links with comment_id
print('=== Links with "comment" in href ===')
for idx, link in enumerate(links):
    href = link.get('href', '')
    if 'comment' in href.lower():
        print(f'{idx}: {href[:250]}')
        
print('\n=== Links with "reply" in href ===')
for idx, link in enumerate(links):
    href = link.get('href', '')
    if 'reply' in href.lower():
        print(f'{idx}: {href[:250]}')

# Try to find any data attributes that might contain ID
print('\n=== Checking all divs for data-id or id attributes ===')
all_divs = soup.find_all('div', limit=50)
for div in all_divs:
    div_id = div.get('id')
    if div_id:
        print(f'Found id attribute: {div_id}')
        # Show some text content
        text = div.get_text()[:100].strip()
        if text:
            print(f'  Text: {text}')
        break

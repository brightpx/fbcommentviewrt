from pathlib import Path
from bs4 import BeautifulSoup

html = Path('debug_comment.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find author name
spans = soup.find_all('span')
author_spans = [s for s in spans if s.get_text().strip() == 'Mook Sasii']

if author_spans:
    author_span = author_spans[0]
    print('=== Author Name Structure ===')
    print(f'Text: {author_span.get_text()}')
    print(f'Classes: {author_span.get("class")}')
    print(f'Parent tag: {author_span.parent.name}')
    print(f'Parent classes: {author_span.parent.get("class")}')
    
    # Walk up to find link
    current = author_span
    for i in range(10):
        current = current.parent
        if current and current.name == 'a':
            print(f'\nFound link ancestor at level {i}:')
            print(f'  href: {current.get("href")[:150] if current.get("href") else "None"}')
            print(f'  classes: {current.get("class")}')
            print(f'  role: {current.get("role")}')
            break
    
    # Also check siblings for links
    print('\nChecking parent siblings for links:')
    parent = author_span.parent
    if parent:
        links = parent.find_all('a', limit=3)
        for idx, link in enumerate(links):
            href = link.get('href', '')
            if 'comment' in href or 'reply' in href:
                print(f'  Link {idx}: {href[:150]}')

# Find message text
print('\n=== Message Text Structure ===')
message_spans = [s for s in spans if 'ปล่อย 3y สภาพดี' in s.get_text()]
if message_spans:
    msg_span = message_spans[0]
    print(f'Text: {msg_span.get_text()}')
    print(f'Classes: {msg_span.get("class")}')
    print(f'Parent tag: {msg_span.parent.name}')
    print(f'Parent classes: {msg_span.parent.get("class")}')
    print(f'Parent dir: {msg_span.parent.get("dir")}')

# Find timestamp
print('\n=== Timestamp Structure ===')
time_spans = [s for s in spans if s.get_text().strip() == '12 ชั่วโมง']
if time_spans:
    time_span = time_spans[0]
    print(f'Text: {time_span.get_text()}')
    print(f'Classes: {time_span.get("class")}')
    print(f'Parent tag: {time_span.parent.name}')
    print(f'Parent classes: {time_span.parent.get("class")}')
    
    # Walk up to find link
    current = time_span
    for _ in range(5):
        current = current.parent
        if current.name == 'a':
            print(f'\nFound link ancestor:')
            print(f'  href: {current.get("href")[:100]}')
            print(f'  classes: {current.get("class")}')
            break

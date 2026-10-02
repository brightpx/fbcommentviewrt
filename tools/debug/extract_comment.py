from pathlib import Path
from bs4 import BeautifulSoup

html = Path('debug_comment.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find the smallest div containing all three elements
def find_best_container(element):
    if element.name == 'div':
        text = element.get_text()
        has_author = 'Mook Sasii' in text
        has_message = 'มาช่วยซื้อหน่อย' in text
        has_timestamp = '11 ชั่วโมง' in text
        
        if has_author and has_message and has_timestamp:
            text_len = len(text)
            if 50 < text_len < 300:
                return element
    
    if hasattr(element, 'children'):
        for child in element.children:
            if hasattr(child, 'name') and child.name:
                result = find_best_container(child)
                if result:
                    return result
    return None

# Find container
container = find_best_container(soup)

if container:
    print('=== Found Comment Container ===')
    print(f'Text length: {len(container.get_text())}')
    print(f'Classes: {container.get("class")}')
    print(f'\nFull text:\n{container.get_text()}\n')
    
    # Now extract properly
    print('=== Extracting Data ===')
    
    # 1. Find author name - look for specific pattern
    author_links = container.find_all('a', href=lambda x: x and '/user/' in x)
    for link in author_links:
        text = link.get_text().strip()
        if text and len(text) > 3 and 'ตัวบ่งชี้' not in text:
            print(f'Author: {text}')
            break
    
    # 2. Find message - look for div with dir="auto" that contains actual message
    message_divs = container.find_all('div', dir='auto')
    print(f'\nFound {len(message_divs)} divs with dir="auto"')
    for idx, div in enumerate(message_divs):
        text = div.get_text().strip()
        # Skip if it's just the author name or timestamp
        if text and text != 'Mook Sasii' and 'ชั่วโมง' not in text:
            print(f'{idx}. Message candidate: {text[:100]}')
    
    # 3. Try finding spans with specific class for message
    message_spans = container.find_all('span', class_='x193iq5w')
    print(f'\nFound {len(message_spans)} spans with class x193iq5w')
    for idx, span in enumerate(message_spans):
        text = span.get_text().strip()
        print(f'{idx}. Span text: {text[:100]}')
    
    # 4. Find timestamp link
    time_link = container.find('a', href=lambda x: x and 'comment_id' in x)
    if time_link:
        print(f'\nTimestamp: {time_link.get_text().strip()}')
        
        import re
        match = re.search(r'comment_id=(\d+)', time_link.get('href'))
        if match:
            print(f'Comment ID: {match.group(1)}')
else:
    print('Container not found!')

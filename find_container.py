from pathlib import Path
from bs4 import BeautifulSoup

html = Path('debug_comment.html').read_text(encoding='utf-8')
soup = BeautifulSoup(html, 'html.parser')

# Find the comment link
comment_link = soup.find('a', href=lambda x: x and 'comment_id' in x)
if comment_link:
    print('=== Comment Link Found ===')
    href = comment_link.get('href')
    print(f'Href: {href[:200]}')
    
    # Extract comment_id
    import re
    match = re.search(r'comment_id=(\d+)', href)
    if match:
        comment_id = match.group(1)
        print(f'Comment ID: {comment_id}')
    
    print(f'\nLink text: "{comment_link.get_text().strip()}"')
    print(f'Link classes: {comment_link.get("class")}')
    print(f'Link role: {comment_link.get("role")}')
    
    # Walk up to find the comment container
    print('\n=== Walking up to find comment container ===')
    current = comment_link
    for i in range(15):
        current = current.parent
        if not current:
            break
        
        # Look for divs that might be the comment container
        if current.name == 'div':
            # Check if this div contains both author and message
            text = current.get_text()
            has_author = 'Mook Sasii' in text
            has_message = 'ปล่อย 3y สภาพดี' in text
            has_timestamp = '12 ชั่วโมง' in text
            
            if has_author and has_message:
                print(f'\n✓ Found comment container at level {i}!')
                print(f'  Has author: {has_author}')
                print(f'  Has message: {has_message}')
                print(f'  Has timestamp: {has_timestamp}')
                print(f'  Classes: {current.get("class")}')
                print(f'  Role: {current.get("role")}')
                
                # This is likely the comment container
                # Now find the selectors
                print('\n=== Finding selectors within container ===')
                
                # Find author
                author_link = current.find('a', role='link', href=lambda x: x and '/user/' in x)
                if author_link:
                    author_name = author_link.get_text().strip()
                    print(f'Author from link: {author_name}')
                    print(f'Author link href: {author_link.get("href")[:100]}')
                
                # Find message - look for span with specific classes
                message_span = current.find('span', class_='x193iq5w')
                if message_span:
                    print(f'Message: {message_span.get_text().strip()}')
                    print(f'Message span classes: {message_span.get("class")[:5]}')
                
                # Find timestamp
                time_link = current.find('a', href=lambda x: x and 'comment_id' in x)
                if time_link:
                    time_text = time_link.get_text().strip()
                    print(f'Timestamp from link: {time_text}')
                
                break

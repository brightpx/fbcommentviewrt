"""Analyze where comments come from."""
from bs4 import BeautifulSoup
import re

content = open('debug_full_page.html', encoding='utf-8').read()
soup = BeautifulSoup(content, 'html.parser')

# Find all comment links
all_comment_links = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
print(f'Total comment links: {len(all_comment_links)}\n')

# Find the main post header
post_header = soup.find(string=lambda x: x and 'โพสต์ของ' in x)
print(f'Main post: {post_header}\n')

# Find a good container that includes the post and its comments
# Go up from post_header and find the largest container with 6-7 comments
current = post_header.parent if post_header else None
post_container = None
depth = 0

while current and depth < 20:
    comment_count = len(current.find_all('a', href=lambda x: x and 'comment_id=' in x))
    # Find container with 6-7 comments (the main post)
    if 6 <= comment_count <= 7:
        post_container = current
        print(f'Found post container at depth {depth} with {comment_count} comments')
        break
    depth += 1
    current = current.parent

if post_container:
    # Get comments inside and outside post container
    comments_in_post = post_container.find_all('a', href=lambda x: x and 'comment_id=' in x)
    print(f'\nComments in main post container: {len(comments_in_post)}')
    
    # Find comments outside
    print(f'\nComments OUTSIDE the main post (likely from other posts):')
    for link in all_comment_links:
        if link not in comments_in_post:
            href = link.get('href', '')
            # Find nearby text to identify which post this belongs to
            container = link.find_parent('div')
            nearby_text = container.get_text()[:200] if container else ''
            print(f'  - {href[:80]}...')
            print(f'    Context: {nearby_text[:100]}...\n')

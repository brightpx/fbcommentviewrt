"""Check if all comments are under the correct post."""
from bs4 import BeautifulSoup

content = open('debug_full_page.html', encoding='utf-8').read()
soup = BeautifulSoup(content, 'html.parser')

# Find the post header
post_header = soup.find(string=lambda x: x and 'โพสต์ของ' in x)
print(f'Found post header: {post_header}')

# Traverse up to find container with all comments
current = post_header.parent if post_header else None
depth = 0

while current and depth < 20:
    comment_count = len(current.find_all('a', href=lambda x: x and 'comment_id=' in x))
    if comment_count > 0:
        print(f'Depth {depth}: tag={current.name}, comments={comment_count}, text_len={len(current.get_text())}')
    depth += 1
    current = current.parent

# Check total comments in entire page
all_comments = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
print(f'\nTotal comment links in entire page: {len(all_comments)}')

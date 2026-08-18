from bs4 import BeautifulSoup
import re

content = open('debug_full_page.html', encoding='utf-8').read()
soup = BeautifulSoup(content, 'html.parser')

links = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
print(f'Total comment links: {len(links)}')
print()

for i, link in enumerate(links[:15]):
    href = link.get('href', '')
    print(f'{i+1}. {href[:250]}')
    print()

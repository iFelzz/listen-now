import sys

file_path = 'static/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    html = f.read()

replacements = {
    'Cari judul lagu, artis, atau album...': 'Search for song title, artist, or album...',
    'Ketik judul lagu, nama artis, atau lirik di kotak pencarian di atas.': 'Type a song title, artist name, or lyrics in the search box above.',
    'Didukung oleh': 'Powered by'
}

for indo, eng in replacements.items():
    html = html.replace(indo, eng)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('Done translating remaining text in index.html')

import sys

file_path = 'static/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    html = f.read()

replacements = {
    'Cari lagu dari YouTube dan download sebagai MP3 gratis. Kualitas audio terbaik, cepat dan mudah.': 'Search YouTube and download as free MP3. Best audio quality, fast and easy.',
    'Temukan lagu favoritmu di YouTube, lalu download langsung sebagai MP3 berkualitas tinggi — gratis dan instan.': 'Find your favorite songs on YouTube, then download directly as high-quality MP3 — free and instant.',
    'Cari lagu di YouTube': 'Search songs on YouTube',
    'placeholder=\"Judul lagu, artis, atau link YouTube...\"': 'placeholder=\"Song title, artist, or YouTube link...\"',
    'aria-label=\"Kata kunci pencarian\"': 'aria-label=\"Search keyword\"',
    'aria-label=\"Cari lagu\"': 'aria-label=\"Search songs\"',
    '>Cari Lagu<': '>Search<',
    'aria-label=\"Sedang mencari…\"': 'aria-label=\"Searching…\"',
    '>Sedang mencari lagu…<': '>Searching for songs…<',
    'Mulai cari lagu': 'Start searching',
    'Ketik judul lagu, nama artis, atau paste link YouTube di atas.': 'Type a song title, artist name, or paste a YouTube link above.',
    'Pencarian gagal': 'Search failed',
    '>Terjadi kesalahan. Silakan coba lagi.<': '>An error occurred. Please try again.<',
    'Tidak ada hasil': 'No results found',
    'Coba kata kunci yang berbeda.': 'Try a different keyword.',
    'aria-label=\"Hasil pencarian\"': 'aria-label=\"Search results\"',
    '>Hasil Pencarian<': '>Search Results<',
    '>0 hasil<': '>0 results<',
    'tayangan': 'views',
    'Sedang mencari lagu…': 'Searching for songs…',
    ' hasil': ' results',
    'Terjadi kesalahan saat mencari. Silakan coba lagi.': 'An error occurred while searching. Please try again.',
    'Mengunduh …': 'Downloading …',
    'Mengunduh:': 'Downloading:',
    'Memproses…': 'Processing…',
    'Terlalu banyak permintaan. Tunggu sebentar dan coba lagi.': 'Too many requests. Please wait a moment and try again.',
    'Selesai!': 'Done!',
    'Download selesai:': 'Download complete:',
    'berhasil didownload!': 'downloaded successfully!',
    '> Coba Lagi<': '> Try Again<',
    'Coba lagi download': 'Retry download',
    'Gagal download:': 'Download failed:',
    'Durasi': 'Duration',
    'Download sebagai MP3': 'Download as MP3',
    'Mencari lagu': 'Searching',
    'Memproses...': 'Processing...'
}

for indo, eng in replacements.items():
    html = html.replace(indo, eng)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('Done translating index.html')

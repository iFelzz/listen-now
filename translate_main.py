import sys

file_path = 'main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

replacements = {
    'Hapus file MP3 di downloads/ yang:': 'Delete MP3 files in downloads/ that:',
    '1. Lebih tua dari MAX_AGE_HOURS': '1. Are older than MAX_AGE_HOURS',
    '2. Folder melebihi MAX_STORAGE_MB (hapus file terlama dulu)': '2. Exceed MAX_STORAGE_MB (delete oldest files first)',
    '# 1. Hapus file yang sudah kadaluarsa': '# 1. Delete expired files',
    '# 2. Hapus file terlama jika folder masih terlalu besar': '# 2. Delete oldest files if folder is still too large',
    '\"Cleanup selesai: %d dihapus, folder %.1f MB\"': '\"Cleanup finished: %d deleted, folder size %.1f MB\"',
    '\"Auto-cleanup aktif: max_age=%.0fj, max_size=%.0fMB, interval=%.0f menit\"': '\"Auto-cleanup active: max_age=%.0fh, max_size=%.0fMB, interval=%.0f min\"',
    'Bersihkan nama file dari karakter ilegal Windows/Linux.': 'Clean filename of illegal Windows/Linux characters.',
    'Spasi dipertahankan agar nama file tetap rapi dan mudah dibaca.': 'Spaces are preserved for readability.',
    'Karakter ilegal: \\\\ / * ? : \" < > |': 'Illegal characters: \\\\ / * ? : \" < > |',
    '# Hapus karakter yang tidak valid di nama file Windows/Linux': '# Remove invalid Windows/Linux filename characters',
    '# Hilangkan spasi berlebih di awal/akhir dan kolapskan spasi ganda': '# Strip excess spaces and collapse double spaces',
    '\"Info penggunaan folder downloads/ dan konfigurasi cleanup.\"': '\"Storage usage info for downloads/ and cleanup config.\"',
    '\"Trigger cleanup manual - hapus file kadaluarsa dan cek batas storage.\"': '\"Trigger manual cleanup - delete expired files and check storage limits.\"'
}

for indo, eng in replacements.items():
    code = code.replace(indo, eng)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)
print('Done translating main.py')

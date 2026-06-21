"""
source_pdfs/ klasörünü izler; yeni veya değişen bir PDF düştüğünde otomatik
olarak ingest.py'yi tetikler. Bu, "kendini eğitme" mekanizmasının arka plan
sürümüdür — kullanıcı her yeni makale eklediğinde elle komut çalıştırmaz.

Kullanım:
    python watch_and_ingest.py
    (Ctrl+C ile durdurulur)
"""
import subprocess
import sys
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import config

DEBOUNCE_SECONDS = 3.0


class PdfChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self._pending = False
        self._last_event = 0.0

    def _mark_pending(self, path):
        if not str(path).lower().endswith(".pdf"):
            return
        self._pending = True
        self._last_event = time.monotonic()

    def on_created(self, event):
        self._mark_pending(event.src_path)

    def on_modified(self, event):
        self._mark_pending(event.src_path)

    def on_deleted(self, event):
        self._mark_pending(event.src_path)

    def maybe_run_ingest(self):
        if self._pending and (time.monotonic() - self._last_event) >= DEBOUNCE_SECONDS:
            self._pending = False
            print("\nDeğişiklik algılandı, ingest.py çalıştırılıyor...")
            subprocess.run([sys.executable, str(config.BASE_DIR / "ingest.py")], check=False)


def main():
    handler = PdfChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(config.SOURCE_PDF_DIR), recursive=False)
    observer.start()
    print(f"İzleniyor: {config.SOURCE_PDF_DIR} (Ctrl+C ile durdurun)")

    try:
        while True:
            time.sleep(1)
            handler.maybe_run_ingest()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()

# optik-kaplama-malzeme-arastirma-ajani

Optik kaplama ve malzeme mühendisliği konusunda, kullanıcının topladığı akademik
PDF'lere dayanan bir RAG (Retrieval-Augmented Generation) tabanlı rapor ajanı.

## Önemli not: "Kendini eğitme" ne demek?

Bu sistem gerçek bir model **fine-tuning** işlemi yapmaz. Yeni bir PDF eklendiğinde
model yeniden eğitilmez; bunun yerine PDF işlenip kalıcı bir vektör veritabanına
(ChromaDB) eklenir ve bir sonraki rapor isteğinde otomatik olarak kullanılabilir hale
gelir. "Kendini eğitme" burada **büyüyen bir kanıt tabanı** anlamına gelir — fine-tuning
değil. Bu yaklaşım, üretilen her iddianın somut bir kaynağa (dosya adı + sayfa no)
bağlanmasını sağladığı için fine-tuning'e göre daha doğrulanabilir ve denetlenebilirdir.

## Mimari

İki parça birlikte çalışır:

1. **`academic-research-skills` Claude Code plugin'i** (genel amaçlı; bu repoda değil,
   Claude Code'a kurulur) — rapor yazımı, akran incelemesi ve atıf doğrulama
   (Semantic Scholar + OpenAlex + Crossref ile çapraz kontrol) sağlar.
2. **Bu klasör (``)** — optik kaplama/malzeme bilimi PDF'lerinden oluşan
   özel kanıt tabanı. `report_generator.py`'nin ürettiği taslak, istenirse plugin'in
   Academic Pipeline skill'ine girdi olarak verilebilir.

> **Lisans uyarısı:** `academic-research-skills` reposu CC-BY-NC 4.0 (ticari olmayan
> kullanım) lisansı ile dağıtılıyor. Ticari bir kullanım söz konusuysa bu lisans
> koşulunu değerlendirin.

## Kurulum

### 1. Python bağımlılıkları

```bash
pip install -r requirements.txt
```

### 2. academic-research-skills plugin'i (Claude Code içinde)

```
/plugin marketplace add Imbad0202/academic-research-skills
/plugin install academic-research-skills
```

### 3. API anahtarı

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Repoya hiçbir anahtar yazılmaz; `config.py` bu değeri yalnızca ortam değişkeninden okur.

## Kullanım

### A. Kaynak PDF'leri ekle

Akademik makaleleri `source_pdfs/` klasörüne kopyala.

### B. İlk ingest (veya manuel güncelleme)

```bash
python ingest.py
```

Her PDF için `İşlendi: <dosya> (N parça)` satırı görülmeli. Zaten işlenmiş ve
değişmemiş dosyalar atlanır (hash kontrolü, `data/ingested_manifest.json`).
Vektör veritabanı `data/chroma_db/` altında kalıcı olarak saklanır.

### C. Otomatik izleme (opsiyonel, "kendini eğitme" mekanizması)

```bash
python watch_and_ingest.py
```

`source_pdfs/` klasörü izlenir; yeni bir PDF düştüğünde otomatik olarak `ingest.py`
tetiklenir. Ctrl+C ile durdurulur.

### D. Rapor üret

```bash
python report_generator.py "anti-yansıtıcı kaplamalarda ince film optimizasyonu"
```

Akış:
1. ChromaDB'den konuyla en alakalı pasajlar (varsayılan: en alakalı 12 parça) çekilir.
2. Claude API'ye, "yalnızca verilen kaynaklara dayan, kaynak göster, bilgi yoksa söyle"
   talimatıyla gönderilir.
3. Giriş / Bulgular / Sonuç / Kaynakça bölümlerinden oluşan bir taslak üretilir.
4. Taslak `output/<tarih>_<konu>.pdf` olarak kaydedilir.

Kaynaklarda yeterli bilgi yoksa ajan halüsinasyon yapmaz; "Mevcut kaynaklarda bu
konuda yeterli bilgi bulunmamaktadır." şeklinde açıkça belirtir.

### E. Taslağı academic-research-skills ile derinleştirme (manuel adım)

`report_generator.py`'nin ürettiği taslağı Claude Code içinde Academic Pipeline
skill'ine girdi olarak verebilirsin. Bu entegrasyon otomatik kod ile değil, Claude
Code içinde manuel/komutla tetiklenir:

1. Üretilen PDF/metni Claude Code oturumuna yapıştır veya dosya olarak ver.
2. Academic Pipeline skill'ini başlat (örn. `academic-pipeline` ilgili komutla).
3. Pipeline; atıf doğrulama (citation-existence verification gate), akran incelemesi
   (0-100 rubrik) ve revizyon aşamalarını taslak üzerinde çalıştırır.

### F. Çok ajanlı rapor üretimi (Claude Code Workflow, opsiyonel)

`multi_agent_workflow.js`, `report_generator.py`'nin tek-ajanlı akışı yerine,
Claude Code'un Workflow özelliğiyle çalışan çok ajanlı bir versiyondur:

1. Bir ajan kaynak pasajları çeker (`report_generator.py --sadece-kaynaklar --json`).
2. Üç ayrı ajan paralel/pipeline olarak farklı açılardan (malzeme özellikleri,
   üretim/işleme yöntemleri, optik/IR performansı) bulgu çıkarır — her bulgu
   hangi pasajdan geldiğini (index) belirtir.
3. Her bulgu, kaynak pasajına karşı **adversarial olarak doğrulanır** (ayrı bir
   ajan "bu iddia gerçekten bu pasajda mı yazıyor?" diye sorar; desteklenmeyen
   bulgular rapora girmez).
4. Son bir ajan, yalnızca doğrulanmış bulgulardan Giriş/Bulgular/Sonuç/Kaynakça
   formatında nihai raporu sentezler.

Kullanım (Claude Code içinde):
```
Workflow({ scriptPath: "multi_agent_workflow.js", args: { topic: "<konu>" } })
```
Script içindeki `REPO_DIR` ve python yorumlayıcı yolunu (`python3` / venv yolu)
kendi ortamınıza göre güncelleyin (dosyanın başındaki `const REPO_DIR = ...`
satırı ve `agent()` içindeki bash komutu).

### G. Akademik formatta DOCX/PDF çıktı (academic-paper skill, opsiyonel)

`report_generator.py` veya `multi_agent_workflow.js`'in ürettiği Markdown/metin
taslağı, `academic-paper` skill'inin **format-convert** modu ile gerçek bir
akademik belge formatına (DOCX veya PDF) çevrilebilir. Bu adım Pandoc (DOCX/PDF)
ve isteğe bağlı bir LaTeX dağıtımı (PDF için) gerektirir.

**Gereken araçlar:**
- **Pandoc** — [pandoc.org/installing.html](https://pandoc.org/installing.html)
  (macOS: `brew install pandoc`, Windows: `.msi` yükleyici veya
  `winget install --id JohnMacFarlane.Pandoc`)
- **LaTeX dağıtımı** (sadece PDF için gerekli; DOCX için gerekmez):
  - macOS: `brew install --cask basictex` (admin şifresi gerektirir)
  - Windows: [MiKTeX](https://miktex.org/download) — kurulumda "Install missing
    packages on-the-fly" seçeneğini **Yes** yapın

**Kullanım:**
1. Raporu bir `.md` dosyasına kaydedin (Giriş/Bulgular/Sonuç/Kaynakça başlıklarıyla).
2. Claude Code içinde `academic-paper` skill'ini "Convert to DOCX/PDF via Pandoc"
   talimatıyla çağırın — skill `formatter_agent`'ı devreye girip Pandoc komutunu
   çalıştırır:
   ```bash
   pandoc rapor.md -o rapor.docx
   # PDF için (LaTeX kuruluyken), XeLaTeX motoru ve Türkçe karakter destekleyen bir font ile:
   pandoc rapor.md -o rapor.pdf --pdf-engine=xelatex -V mainfont="Helvetica"
   ```
   Not: `-V lang=tr-TR` (babel) seçeneğini eklemeyin — BasicTeX/temel TeX Live
   dağıtımlarında Türkçe babel dil paketi varsayılan olarak gelmez ve
   `Unknown option 'turkish'` hatasıyla derleme başarısız olur. `mainfont`
   belirtmeden bırakırsanız XeLaTeX varsayılan fontla devam eder, Türkçe
   karakterler (ç, ğ, ı, ö, ş, ü) yine doğru render edilir.
3. Çıktı, `pdf_writer.py`'nin ürettiği basit PDF'den farklı olarak, akademik
   makale formatlama kurallarına (başlık hiyerarşisi, atıf stili dönüşümü vb.)
   uygun bir belge olur.

## Klasör yapısı

```
.
├── README.md
├── requirements.txt
├── config.py
├── ingest.py
├── watch_and_ingest.py
├── report_generator.py
├── pdf_writer.py
├── multi_agent_workflow.js
├── source_pdfs/        (gitignore — kullanıcı PDF'leri)
├── data/                (gitignore — chroma_db/ + ingested_manifest.json)
└── output/              (gitignore — üretilen rapor PDF'leri)
```

## Doğrulama adımları

1. `pip install -r requirements.txt`
2. 2-3 örnek PDF ile `python ingest.py` çalıştırıp ChromaDB'nin
   oluştuğunu ve manifest'in güncellendiğini kontrol et.
3. Aynı klasöre yeni bir PDF ekleyip `watch_and_ingest.py` (veya tekrar `ingest.py`)
   ile yalnızca yeni dosyanın işlendiğini doğrula.
4. `python report_generator.py "<konu>"` çalıştırıp PDF çıktısının
   `output/` altında oluştuğunu ve kaynak gösterdiğini kontrol et.
5. Kaynaklarda olmayan bir konu sorup ajanın halüsinasyon yapmadan "kaynaklarda
   yeterli bilgi yok" dediğini test et.
6. academic-research-skills plugin kurulumunu test edip Academic Pipeline skill'inin
   taslak raporu nasıl işlediğini gözlemle.

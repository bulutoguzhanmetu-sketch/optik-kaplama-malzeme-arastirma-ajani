"""
Verilen bir konu için ChromaDB kanıt tabanından en alakalı pasajları çeker,
Claude API'ye "optik kaplama ve malzeme mühendisi" sistem promptuyla gönderir
ve kaynak gösteren, yapılandırılmış bir taslak rapor üretir.

Kullanım:
    python report_generator.py "<konu>"

Üretilen taslak, istenirse academic-research-skills plugin'inin Academic
Pipeline skill'ine girdi olarak verilip atıf doğrulama + akran inceleme
aşamalarından geçirilebilir (bkz. README.md).
"""
import json
import sys

import chromadb
from anthropic import Anthropic

import config
from pdf_writer import write_report_pdf

SYSTEM_PROMPT = """Sen bir optik kaplama ve malzeme mühendisliği uzmanısın. Görevin, sana \
verilen akademik kaynak pasajlarına dayanarak literatür taramasına dayalı, yüksek bilgi \
doğruluğuna sahip bir rapor taslağı hazırlamaktır.

Kurallar (kesinlikle uyulmalı):
1. SADECE sana verilen kaynak pasajlarındaki bilgiyi kullan. Eğitim verinden veya genel \
bilgiden bilgi EKLEME.
2. Her iddiayı, hangi kaynaktan geldiğini parantez içinde belirterek destekle, örn: \
(Kaynak: dosya_adi.pdf, s. 5).
3. Verilen pasajlarda konuyla ilgili yeterli bilgi yoksa, bunu açıkça söyle: \
"Mevcut kaynaklarda bu konuda yeterli bilgi bulunmamaktadır." Asla halüsinasyon yapma, \
asla kaynaksız teknik veri/sayı üretme.
4. Rapor şu bölümlerden oluşmalı: Giriş, Bulgular, Sonuç, Kaynakça.
5. Kaynakça bölümünde yalnızca sana fiilen verilen kaynak dosyalarını listele.
6. Türkçe ve teknik/akademik bir dille yaz."""


def retrieve_passages(topic, top_k=None):
    top_k = top_k or config.RETRIEVAL_TOP_K
    client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
    try:
        collection = client.get_collection(name=config.COLLECTION_NAME)
    except Exception:
        return []

    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[topic], n_results=min(top_k, collection.count()))

    passages = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        passages.append({"text": doc, "source": meta.get("source", "bilinmeyen"), "page": meta.get("page", "?")})
    return passages


def build_user_message(topic, passages):
    if not passages:
        return (
            f"Konu: {topic}\n\n"
            "Kanıt tabanında bu konuyla ilişkili hiç pasaj bulunamadı. Lütfen yalnızca "
            "kaynaklarda yeterli bilgi bulunmadığını belirten kısa bir rapor üret."
        )

    parts = [f"Konu: {topic}\n\nKaynak pasajlar:\n"]
    for i, p in enumerate(passages, start=1):
        parts.append(f"[{i}] (Kaynak: {p['source']}, s. {p['page']})\n{p['text']}\n")
    parts.append(
        "\nYukarıdaki pasajlara dayanarak, sistem promptundaki kurallara uyan bir rapor taslağı üret."
    )
    return "\n".join(parts)


def generate_report(topic):
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY ortam değişkeni ayarlı değil. "
            "Örn: export ANTHROPIC_API_KEY=\"sk-ant-...\""
        )

    passages = retrieve_passages(topic)
    user_message = build_user_message(topic, passages)

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    report_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    sources = sorted({p["source"] for p in passages})
    return report_text, sources


def main():
    args = sys.argv[1:]
    raw_mode = "--sadece-kaynaklar" in args
    json_mode = "--json" in args
    args = [a for a in args if a not in ("--sadece-kaynaklar", "--json")]

    if not args:
        print('Kullanım: python report_generator.py "<konu>" [--sadece-kaynaklar] [--json]')
        print("  --sadece-kaynaklar : Claude API'ye gitmeden, ChromaDB'den bulunan ham pasajları gösterir.")
        print("  --json             : --sadece-kaynaklar ile birlikte, çıktıyı makine-okur JSON olarak verir.")
        return 1

    topic = " ".join(args)

    if raw_mode and json_mode:
        passages = retrieve_passages(topic)
        indexed = [{"index": i, **p} for i, p in enumerate(passages, start=1)]
        print(json.dumps({"passages": indexed}, ensure_ascii=False))
        return 0

    print(f"Konu: {topic}")
    print("Kanıt tabanından alakalı pasajlar çekiliyor...")

    if raw_mode:
        passages = retrieve_passages(topic)
        if not passages:
            print("Kanıt tabanında bu konuyla ilişkili hiç pasaj bulunamadı.")
            return 0
        for i, p in enumerate(passages, start=1):
            print(f"\n[{i}] Kaynak: {p['source']}, s. {p['page']}\n{p['text']}")
        print(f"\nToplam {len(passages)} pasaj bulundu (API kullanılmadı).")
        return 0

    report_text, sources = generate_report(topic)
    print("\n" + report_text + "\n")

    if sources:
        print(f"Kullanılan kaynaklar: {', '.join(sources)}")
    else:
        print("Uyarı: Hiçbir kaynak pasajı bulunamadı; rapor kaynaksız bir uyarı içeriyor olabilir.")

    output_path = write_report_pdf(topic, report_text)
    print(f"\nPDF kaydedildi: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

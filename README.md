# A.N.K.A — Kişisel Yapay Zeka Asistanı

J.A.R.V.I.S konseptinde, 7/24 çalışan, modüler kişisel asistan.

## Mimari

```
Ses Servisi ─┐                          ┌─ RAG Servisi (Qdrant)
WhatsApp ────┼──► CORE API (FastAPI) ◄──┤
Web/CLI ─────┘    LLM: Gemini           └─ OS Ajanı (onaylı)
                  Olaylar: Redis pub/sub
```

Tüm zekâ Core API'dedir; diğer modüller Core'a WebSocket/HTTP ile bağlanan uydu servislerdir.

## Fazlar

- [x] **Faz 0** — İskelet, docker-compose (Qdrant + Redis + Core)
- [x] **Faz 1** — Core API, Gemini gateway, tool-calling ajan döngüsü
- [ ] **Faz 2** — RAG: kod/doküman indexleme, hybrid arama
- [ ] **Faz 3** — OS kontrolü + güvenlik onay mekanizması
- [ ] **Faz 4** — Sesli iletişim (wake word → STT → TTS)
- [ ] **Faz 5** — WhatsApp otomasyonu (Baileys köprüsü)
- [ ] **Faz 6** — 7/24 sağlamlaştırma, izleme, yedekleme

## Kurulum

```bash
# 1. Ortam degiskenleri
cp .env.example .env
# .env icine GEMINI_API_KEY'ini yaz (https://aistudio.google.com/apikey)

# 2a. Docker ile (onerilen)
docker compose up --build -d

# 2b. Veya lokalde (gelistirme)
cd core
pip install -r requirements.txt
# .env'de REDIS_URL/QDRANT_URL/ANKA_DB_PATH'i localhost'a cevir
uvicorn app.main:app --reload
```

## Test

```bash
# Saglik kontrolu
curl http://localhost:8000/health

# Sohbet (HTTP)
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Saat kac?"}'

# Interaktif CLI (WebSocket)
pip install websockets
python cli.py
```

## Dizin Yapısı

```
core/app/
├── main.py          # FastAPI giris noktasi (HTTP + WebSocket)
├── config.py        # Ayarlar (.env)
├── agent/           # Ajan dongusu (tool-calling loop)
├── llm/             # LLM Gateway (Gemini adapter)
├── tools/           # Arac kayit merkezi + risk siniflari
└── memory/          # Konusma gecmisi (bellek + SQLite)
```

## Güvenlik Modeli

Her araç bir risk sınıfı taşır:

| Sınıf | Davranış |
|---|---|
| `SAFE` | Otomatik çalışır (okuma, listeleme) |
| `WRITE` | Onay gerekir (Faz 3) |
| `DESTRUCTIVE` | Açık onay + audit log (Faz 3) |

Yasak işlemler (disk format, kritik sistem dosyaları) hiç araç olarak tanımlanmaz.

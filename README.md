# DASK UAVT Address Code Crawler

🇹🇷 Türkiye'deki tüm adres kodlarını (UAVT) [DASK Adres Kodu](https://adreskodu.dask.gov.tr) API'sinden çeken Python crawler.

## Özellikler

- **Tam hiyerarşi**: İl → İlçe → Bucak/Köy → Mahalle → Sokak → Bina → İç Kapı (UAVT)
- **Checkpoint desteği**: Crash sonrası kaldığı yerden devam eder
- **Rate limiting**: İstekler arası yapılandırılabilir gecikme
- **Retry logic**: 504 ve bağlantı hatalarında otomatik yeniden deneme
- **Token yönetimi**: Otomatik alma ve yenileme
- **PostgreSQL**: Tüm veriler ilişkisel veritabanında

## Mimari

```
src/
  client/
    dask_client.py    # HTTP client (token, retry, rate limiting)
    html_parser.py    # HTML table parser (sokak, bina, iç kapı)
  models/
    address.py        # Dataclass'lar (City, District, Village, ...)
  repository/
    db.py             # PostgreSQL CRUD (bulk insert, upsert)
    migrations.py     # DDL — tablo oluşturma
  services/
    crawler.py        # Ana crawl logic (hiyerarşik traversal)
    progress.py       # Checkpoint yönetimi (JSON dosyası)
  config.py           # Environment-based configuration
main.py               # CLI entry point
```

## Kurulum

### Gereksinimler

- Python 3.11+
- Docker & Docker Compose (PostgreSQL için)

### Adımlar

```bash
# 1. Repo'yu klonla
git clone https://github.com/hakanbaysal/dask-uavt-crawler.git
cd dask-uavt-crawler

# 2. Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Bağımlılıkları kur
pip install -r requirements.txt

# 4. Environment dosyasını hazırla
cp .env.example .env
# .env dosyasını düzenle (DB şifresi vs.)

# 5. PostgreSQL'i başlat
docker-compose up -d

# 6. Tabloları oluştur
python main.py --migrate
```

## Kullanım

```bash
# Tam crawl (checkpoint'tan devam eder)
python main.py

# Sadece migration çalıştır
python main.py --migrate

# Mevcut durumu göster
python main.py --status

# Checkpoint'u sıfırla (baştan başla)
python main.py --reset
```

### Belirli Şehir Aralığı

`.env` dosyasında:

```env
START_CITY_CODE=34    # Sadece İstanbul'dan başla
END_CITY_CODE=34      # Sadece İstanbul'u crawl et
```

### Yapılandırma

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DASK_BASE_URL` | `https://adreskodu.dask.gov.tr` | API base URL |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `dask_uavt` | Veritabanı adı |
| `DB_USER` | `postgres` | DB kullanıcı |
| `DB_PASSWORD` | `postgres` | DB şifre |
| `REQUEST_DELAY` | `1.0` | İstekler arası bekleme (saniye) |
| `MAX_RETRIES` | `3` | Maksimum yeniden deneme |
| `RETRY_DELAY` | `5.0` | Yeniden deneme arasındaki bekleme |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout (saniye) |
| `LOG_LEVEL` | `INFO` | Log seviyesi (DEBUG/INFO/WARNING/ERROR) |
| `CHECKPOINT_DIR` | `checkpoints` | Checkpoint dosya dizini |

## Testler

```bash
# Testleri çalıştır
pytest

# Coverage ile
pytest --cov=src --cov-report=html

# Belirli test dosyası
pytest tests/test_parser.py -v
```

## Veritabanı Şeması

```
cities ──┐
         ├── districts ──┐
                         ├── villages ──┐
                                       ├── quarters ──┐
                                                      ├── streets ──┐
                                                                    ├── buildings ──┐
                                                                                   ├── sections (UAVT)
```

Her tablo `code` (PRIMARY KEY) ve parent foreign key içerir. `ON CONFLICT` ile upsert yapılır.

## Lisans

MIT

## Yazar

**Hakan Baysal** — [hakanbaysal](https://github.com/hakanbaysal)

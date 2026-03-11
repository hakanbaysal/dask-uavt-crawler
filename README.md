# DASK UAVT Adres Kodu Crawler

Türkiye'deki tüm UAVT (Ulusal Adres Veri Tabanı) adres kodlarını `dask.gov.tr` üzerinden çekip PostgreSQL'de saklayan crawler.

## Yapı

```
src/
  crawler.py       # Ana crawler - hiyerarşik veri çekimi
  captcha.py       # reCAPTCHA v2 çözücü
  db.py            # PostgreSQL bağlantı ve tablo yönetimi
  models.py        # Veri modelleri
config.py          # Ayarlar
requirements.txt   # Bağımlılıklar
docker-compose.yml # PostgreSQL
```

## Hiyerarşi

İl → İlçe → Bucak/Köy → Mahalle → Cadde/Sokak → Bina → İç Kapı (UAVT Kodu)

## API Endpoint'leri (dask.gov.tr)

| Endpoint | Parametre | Dönen Veri |
|---|---|---|
| POST /tr/AddressCode/Cities | - | İller |
| POST /tr/AddressCode/Districts | cityCode | İlçeler |
| POST /tr/AddressCode/Villages | districtCode | Bucak/Köy |
| POST /tr/AddressCode/Quarters | villageCode | Mahalleler |
| POST /tr/AddressCode/Streets | quarterCode | Cadde/Sokak |
| POST /tr/AddressCode/Buildings | streetCode | Binalar |
| POST /tr/AddressCode/IndependentSections | buildingCode | İç Kapılar |

Tüm istekler `__RequestVerificationToken` (CSRF) gerektirir.
İlk istek öncesi reCAPTCHA v2 çözülmesi gerekir.

## reCAPTCHA

- reCAPTCHA v2 (sitekey: `6Levh-8UAAAAADKgSrLuFDo1PNopWkk-Ife5Im8y`)
- Endpoint: `POST /tr/AddressCode/ValidateCaptcha`
- Her session'da bir kez çözülmeli, sonra "showCaptcha" dönene kadar geçerli

## Kurulum

```bash
pip install -r requirements.txt
docker-compose up -d  # PostgreSQL
cp .env.example .env  # Ayarları düzenle
python -m src.crawler
```

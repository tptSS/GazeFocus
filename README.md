# GazeFocus

Webcam ile hangi monitöre baktığınızı algılayıp, fare kullanmadan klavye odağını o
monitördeki pencereye otomatik veren bir Windows programı. Laptop + harici monitör
kullanıp sık sık yanlış pencereye yazanlar için.

## Gereksinimler

- Windows 10/11
- **En az 2 monitör** (tek monitörde anlamsız, program açılmaz)
- Webcam
- Python **3.10, 3.11 veya 3.12** — **3.13 desteklenmiyor** (mediapipe henüz uyumlu değil)
  - Yoksa: <https://www.python.org/downloads/> adresinden Python 3.12 kurun,
    kurulum ekranında **"Add python.exe to PATH"** kutusunu işaretlemeyi unutmayın.

## Kurulum (yeni bir bilgisayarda)

1. **Python'ı kurun** (yukarıdaki gereksinime bakın). Zaten kuruluysa atlayın.
2. **Projeyi indirin**, iki yoldan biriyle:
   - Git ile:
     ```
     git clone https://github.com/tptSS/GazeFocus.git
     ```
   - Git yoksa: GitHub sayfasında yeşil **Code > Download ZIP** butonuna basıp
     indirin, klasörü bir yere çıkartın (`.venv` ve kalibrasyon dosyası ilk
     çalıştırmada otomatik oluşur, repoda yok).
3. Klasöre girip **`baslat.bat`** dosyasına çift tıklayın.
   - İlk çalıştırmada otomatik bir sanal ortam (`.venv`) kurulur ve
     `requirements.txt`'teki bağımlılıklar (mediapipe, opencv, vb.) indirilir —
     internet bağlantısı gerekir, birkaç dakika sürebilir.
   - Kamera izni kapalıysa Windows'un kamera gizlilik ayarları otomatik açılır;
     izin verdiğiniz an program kalibrasyona otomatik geçer.
   - İlk kullanımda otomatik **kalibrasyon ekranı** açılır: her monitörde sırayla
     çıkan noktalara doğal şekilde bakmanız yeterli (ESC ile iptal edebilirsiniz).
4. Kalibrasyon bitince program arka planda çalışmaya başlar; konsolu kapatmayın,
   küçültüp bırakabilirsiniz.

Sonraki çalıştırmalarda `baslat.bat`'a çift tıklamak yeterli — kurulum/kalibrasyon
tekrar istenmez (monitör düzeni değişmediği sürece).

## Kısayollar

| Tuş | İşlev |
|---|---|
| `Ctrl+Alt+G` | Duraklat / devam ettir |
| `Ctrl+Alt+C` | Yeniden kalibre et |
| `Ctrl+Alt+Q` | Çıkış |

## Yönetici olarak açılmış pencereler

Yönetici yetkisiyle açılmış bir pencereye (örn. yönetici olarak çalışan bir
uygulama) odak verebilmesi için GazeFocus'un da yönetici olarak çalıştırılması
gerekir: `baslat.bat`'a sağ tık → **Yönetici olarak çalıştır**.

## Faydalı bayraklar

```
python gaze_focus.py --preview          # kamera önizlemesi + canlı tahmin (doğruluğu kontrol için)
python gaze_focus.py --calibrate        # kalibrasyonu zorla yeniden yap
python gaze_focus.py --camera 1         # birden fazla kameran varsa farklı index dene
python gaze_focus.py --dwell 0.6        # monitör değişimi için gereken bakış süresi (sn)
python gaze_focus.py --type-guard 1.5   # son tuştan sonra bu kadar sn odak değişmesin
```

(`baslat.bat --preview` gibi `baslat.bat`'a da aynı bayraklar eklenebilir.)

## Kalibrasyon verisi nerede tutuluyor?

`%APPDATA%\GazeFocus\calibration.json`. Monitör sayısı/düzeni değişirse program
bunu otomatik fark edip yeniden kalibrasyon ister. Elle silip `--calibrate` ile
de yeniden yapılabilir.

## Bilinen sınırlar

- Sadece monitör seviyesinde çalışır; aynı ekrandaki pencere/sekme ayrımı yapmaz
  (webcam hassasiyeti yetmiyor, bunun için Tobii gibi göz izleyici gerekir).
- Tek monitörde çalışmaz, en az 2 monitör gerekir.

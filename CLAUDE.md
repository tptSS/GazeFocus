# GazeFocus — proje bağlamı

## Amaç
Laptop + harici monitör kullanıyorum. Klavye odağı son tıkladığım pencerede kaldığı için sık sık yanlış yere yazıyorum.
Webcam ile hangi monitöre baktığımı algılayıp, fare kullanmadan klavye odağını o monitördeki pencereye veren bir Windows programı.

## Mevcut durum
- `gaze_focus.py`: çalışır ilk sürüm (Windows, Python 3.10–3.12).
  - MediaPipe Face Mesh: iris oranı + kafa yaw/pitch + yüz konumu -> 6 boyutlu özellik
  - Kalibrasyon: her monitörde 7 nokta, normalize k-NN sınıflandırıcı, `%APPDATA%\GazeFocus\calibration.json`
  - Odak: monitördeki Z-sırasına göre en üstteki pencere, `SetForegroundWindow` (+ AttachThreadInput yedeği)
  - Korumalar: dwell 0.45 sn, son tuştan sonra 1.2 sn odak değişmez, 0.8 sn cooldown, min güven 0.7
  - Kısayollar: Ctrl+Alt+G duraklat, Ctrl+Alt+C kalibre, Ctrl+Alt+Q çıkış
  - Bayraklar: --calibrate, --preview, --camera, --dwell, --type-guard, --cooldown, --min-conf, --smooth
- `requirements.txt`: mediapipe==0.10.14, opencv-python, numpy<2, pynput
- `baslat.bat`: venv kurar, bağımlılıkları yükler, programı başlatır

## Henüz test edilmedi
Gerçek Windows makinede hiç çalıştırılmadı. İlk iş: çalıştır, hataları düzelt, `--preview` ile tahmin doğruluğunu kontrol et.

## Bilinen sınırlar / sonraki adımlar
- Sadece monitör seviyesinde çalışır; aynı ekrandaki pencere/sekme ayrımı yok (webcam hassasiyeti yetmez, Tobii gerekir).
- Yönetici olarak açılmış pencerelere odak için programın da yönetici olarak çalışması gerekir.
- İstenirse: sistem tepsisi simgesi, Windows açılışında otomatik başlatma, PyInstaller ile tek .exe.

## Tercihler
Türkçe iletişim. Doğrudan, production-ready kod; az soru.

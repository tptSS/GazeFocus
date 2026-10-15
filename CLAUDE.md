# GazeFocus — proje bağlamı

## Amaç
Laptop + harici monitör kullanıyorum. Klavye odağı son tıkladığım pencerede kaldığı için sık sık yanlış yere yazıyorum.
Webcam ile hangi monitöre baktığımı algılayıp, fare kullanmadan klavye odağını o monitördeki pencereye veren bir Windows programı.

## Mevcut durum
Gerçek Windows makinede test edildi ve çalışıyor. GitHub: https://github.com/tptSS/GazeFocus

- `gaze_focus.py`:
  - MediaPipe Face Mesh: iris oranı + kafa yaw/pitch + yüz konumu -> 6 boyutlu özellik
  - Kalibrasyon: her monitörde 7 nokta (5 sn geri sayım + ilerleme çubuğu + glow efektli noktalar),
    normalize k-NN sınıflandırıcı, `%APPDATA%\GazeFocus\calibration.json`
  - Klavyeye bakma koruması: kalibrasyonun son adımında "klavyene bak" örnekleri de ayrı bir
    sınıf (KEYBOARD_LABEL=-1) olarak toplanır; bakış o sınıfa benzerse ya da kalibrasyonda hiç
    görülmemiş aşırı bir yöne bakılıyorsa (mesafe eşiği) odak hiçbir monitöre geçmez
  - Aynı ekranda birden fazla pencere (deneysel): her monitör için ayrıca sol/sağ ve üst/alt
    yarıyı ayırt eden bağımsız k-NN'ler (`RegionClassifier`) kalibrasyonun aynı verisinden
    kurulur; pencere seçimi artık `pick_window_for_region` ile pencerenin monitördeki
    örtüşme ORANINA bakarak yapılır (sadece merkez noktası değil — tam ekranı kaplayan bir
    pencere yanlışlıkla "doğru yarıda" sayılmasın diye). Sinyal belirsizse eski davranışa
    (en üstteki pencere) düşer, tam geriye dönük uyumlu
  - Odak: `pick_window_for_region` ile seçilen pencereye `SetForegroundWindow` (+ AttachThreadInput yedeği)
  - Korumalar: dwell 0.45 sn, son tuştan sonra 1.2 sn odak değişmez, 0.8 sn cooldown, min güven 0.7
  - Kısayollar: Ctrl+Alt+G **veya** Ctrl+Alt+F duraklat/devam (oyun için), Ctrl+Alt+C kalibre, Ctrl+Alt+Q çıkış
  - Bayraklar: --calibrate, --preview, --camera, --dwell, --type-guard, --cooldown, --min-conf, --smooth
  - İlk kullanımda Windows kamera izni kapalıysa ayarları otomatik açıp izin verilene kadar bekler
  - stdout/stderr line_buffering=True (dosyaya yönlendirilince loglar geç/gruplu yazılmasın diye)
- `requirements.txt`: mediapipe==0.10.14, opencv-python, numpy<2, pynput
- `baslat.bat`: Python yoksa winget/python.org'dan otomatik kurar, venv kurar, bağımlılıkları
  yükler; kurulum bitince **görünür komut istemi penceresi bırakmadan** (vbs ile gizli launch,
  `_oto_calistir.bat` — gitignore'da, makineye özel) arka planda çalıştırır. Kalibrasyon
  gerekiyorsa o ekranlar (tkinter, ayrı pencere) yine normal görünür.
- `otomatik_baslatmayi_ac.bat` / `_kapat.bat`: Windows açılışında (Startup klasörüne vbs koyarak)
  otomatik, görünmez başlatma. Önce gerçek kalibrasyon var mı diye kontrol eder.
- Çıktı logu: `%APPDATA%\GazeFocus\baslat.log`

## Bilinen sınırlar / sonraki adımlar
- Aynı ekrandaki pencere ayrımı (yukarıda) deneysel — webcam için monitör-arası ayrımdan
  doğası gereği daha zor, tam güvenilir olmayabilir (Tobii gibi özel donanım kadar hassas değil).
- Yönetici olarak açılmış pencerelere odak için programın da yönetici olarak çalışması gerekir.
- İstenirse: sistem tepsisi simgesi, PyInstaller ile tek .exe.

## Tercihler
Türkçe iletişim. Doğrudan, production-ready kod; az soru.

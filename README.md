# GazeFocus

> ⚠️ **Sadece Windows (10/11) için çalışır.** Mac veya Linux'ta çalışmaz —
> başka bir bilgisayara göstermeden önce o bilgisayarın Windows olduğundan
> emin olun.

Bilgisayara bağlı webcam'in izlediği yöne bakarak, hangi monitöre baktığınızı
anlar ve fare kullanmadan klavye yazımını o monitördeki pencereye otomatik
olarak yönlendirir. Laptop + harici monitör kullanıp sık sık yanlış pencereye
yazanlar için yapıldı.

**Hiç bilgisayar/kod bilginiz olmasa bile** aşağıdaki adımları sırayla
uygulayarak kurabilir ve kullanabilirsiniz. Hiçbir şeyi atlamadan, sırayla okuyun.

---

## Önce kontrol edin

- Windows bilgisayar olmalı (Windows 10 veya 11).
- **En az 2 ekran** olmalı (laptop ekranı + harici monitör de sayılır). Tek
  ekranda program hiçbir işe yaramaz, çalıştırmayın.
- Bilgisayarda webcam (kamera) olmalı — laptopun kendi kamerası da olur.
- İnternete bağlı olun (kurulum sırasında bazı dosyalar indirilecek).

---

## 1. ADIM — Programı indirin

1. Tarayıcınızda şu adrese gidin: **https://github.com/tptSS/GazeFocus**
2. Sayfada, sağ üst taraflarda yeşil renkli **"Code"** yazan bir düğme
   göreceksiniz. Ona tıklayın.
3. Açılan küçük pencerede en altta **"Download ZIP"** yazısı var, ona tıklayın.
4. Bilgisayarınıza `GazeFocus-main.zip` adında bir dosya inecek (genelde
   "İndirilenler" / "Downloads" klasörüne iner).

## 2. ADIM — ZIP dosyasını açın (çıkartın)

Bu adım önemli, atlamayın — zip dosyasının **içine girmek** yetmez, dosyaları
**çıkartmanız** gerekiyor:

1. İndirilen `GazeFocus-main.zip` dosyasına **sağ tıklayın**.
2. Açılan menüden **"Tümünü Ayıkla..."** (İngilizce Windows'ta "Extract All...")
   seçeneğine tıklayın.
3. Çıkan pencerede değiştirmeden **"Ayıkla" / "Extract"** düğmesine basın.
4. Şimdi `GazeFocus-main` adında, zip olmayan, normal bir klasör oluşmuş
   olmalı. O klasörü açın.

## 3. ADIM — Programı başlatın

1. Açtığınız klasörün içinde **`baslat.bat`** adında bir dosya göreceksiniz
   (simgesi genelde bir dişli/terminal gibi görünür). **Çift tıklayın.**

2. **Siyah bir pencere (konsol) açılacak ve içinde bir sürü yazı akacak.**
   Bu normaldir, virüs falan değildir — program kendi kendine gerekli
   parçaları indirip kuruyor demektir. **Pencereyi kapatmayın**, bitmesini
   bekleyin. İnternet hızınıza göre bu **birkaç dakika** sürebilir (ilk
   çalıştırmada; sonraki seferlerde anında açılır).

   > Eğer ekranda mavi bir "Windows bilgisayarınızı korudu" uyarısı çıkarsa:
   > **"Daha fazla bilgi"** yazısına, sonra çıkan **"Yine de çalıştır"**
   > düğmesine tıklayın. Bu, programın imzasız/yeni olmasından kaynaklanan
   > normal bir uyarıdır.

3. Kurulum bitince **siyah pencere kendiliğinden kapanır** — bu normaldir,
   program artık arka planda, görünmez şekilde çalışmaya devam ediyor
   demektir (hiçbir zaman "şu an çalışıyorum" diye rahatsız edici bir
   pencere göstermez).

4. Kısa bir süre sonra program kamerayı kullanmak isteyecek. Eğer Windows
   kamera izni kapalıysa, **Ayarlar otomatik açılır** — orada kamera
   erişimini **açık** konuma getirin (bir anahtar/switch görürsünüz).
   Program izni fark edip kendisi devam edecek, başka bir şey yapmanıza
   gerek yok.

## 4. ADIM — Kalibrasyon (programın gözünüzü öğrenmesi)

Kurulum bitince ekranlarınızda otomatik olarak bir **kalibrasyon** ekranı
açılır. Bu, programın "senin gözün şu monitöre bakınca nasıl görünüyor"
öğrendiği kısımdır:

1. Önce kısa bir geri sayım görürsünüz ("3, 2, 1").
2. Sonra ekranda **noktalar** belirir (önce büyük mavi, sonra küçük kırmızı).
   Her nokta çıktığında **sadece o noktaya doğal şekilde bakın**, başınızı
   fazla oynatmadan. Nokta birkaç saniye ekranda kalır, sonra bir sonrakine
   geçer.
3. Bu, sırayla her monitör için tekrarlanır.
4. Bir monitörün kalibrasyonu bitince otomatik diğerine geçer. Hiçbir tuşa
   basmanıza gerek yok, sadece bakın.
5. **En son** ekranda "Şimdi klavyenize bakın" yazısı çıkar — bu adımda
   **ekrana değil, gerçekten klavyenize** bakın, yazı yazıyormuş gibi kafanızı
   doğal şekilde aşağı eğin. Bu sayede program, siz refleks olarak klavyeye
   baktığınızda bunu "monitöre bakma" ile karıştırmayı öğrenir — yani yazarken
   kafanızı klavyeye çevirseniz bile yanlış pencereye geçiş yapmaz.
6. Vazgeçmek isterseniz **ESC** tuşuna basabilirsiniz (program kapanır).

Kalibrasyon bitince program artık **arka planda sessizce çalışmaya** başlar.
Siyah pencereyi **kapatmayın**, isterseniz görev çubuğundan küçültebilirsiniz
— kapatırsanız program da durur.

**Artık kurulum bitti!** Şimdi hangi monitöre bakarsanız, birkaç saniye
içinde klavye yazımı otomatik olarak o monitördeki pencereye geçecek.

---

## Sonraki kullanımlarda ne yapacaksınız?

Kurulumu bir daha yapmanıza gerek yok. İki seçeneğiniz var:

- **Elle başlatma:** Aynı klasöre gidip **`baslat.bat`**'a çift tıklayın.
  (İsterseniz bu dosyaya sağ tıklayıp **"Kısayol oluştur"** diyip o kısayolu
  masaüstüne taşıyabilirsiniz, böylece her seferinde klasörü aramanıza gerek
  kalmaz.)
- **Otomatik başlatma (önerilen):** Aşağıdaki "Windows açılışında otomatik
  başlatma" bölümünü bir kez kurun, bundan sonra hiç dokunmanıza gerek
  kalmaz — bilgisayarı her açtığınızda program kendiliğinden, görünmez
  şekilde arka planda başlar.

### Windows açılışında otomatik başlatma

Kalibrasyonu en az bir kez **gerçekten tamamladıktan sonra** (yukarıdaki 4.
adım), klasördeki **`otomatik_baslatmayi_ac.bat`** dosyasına çift tıklayın.
Bundan sonra bilgisayarınızı her açtığınızda GazeFocus kendiliğinden, hiçbir
pencere açmadan arka planda başlar — hiçbir şey yapmanıza gerek kalmaz.

- Vazgeçmek isterseniz **`otomatik_baslatmayi_kapat.bat`**'a çift tıklayın;
  program artık otomatik başlamaz (yine de `baslat.bat` ile elle
  çalıştırabilirsiniz).
- Otomatik başlarken bir sorun olursa (pencere görmediğiniz için fark
  etmeyebilirsiniz), çıktılar şu dosyaya yazılır:
  `%APPDATA%\GazeFocus\baslat.log`
- **Önemli:** Henüz kalibrasyon yapmadıysanız `otomatik_baslatmayi_ac.bat`
  bunu size söyleyip hiçbir şey yapmadan duracaktır — önce gerçekten
  kalibrasyonu tamamlamanız gerekir, yoksa her açılışta beklenmedik şekilde
  kalibrasyon ekranı karşınıza çıkar.

## Kullanırken bilmeniz gerekenler (kısayollar)

Bu üç tuşa **aynı anda** basarsanız:

| Tuşlar | Ne işe yarar |
|---|---|
| `Ctrl` + `Alt` + `G` **veya** `Ctrl` + `Alt` + `F` | Programı duraklatır / tekrar basınca devam ettirir — **oyun oynarken** bu şekilde kapatıp açabilirsiniz, böylece yanlışlıkla diğer monitöre bakınca oyun küçülmez |
| `Ctrl` + `Alt` + `C` | Kalibrasyonu baştan yapar (doğruluğu kötüyse bunu deneyin) |
| `Ctrl` + `Alt` + `Q` | Programı tamamen kapatır |

## Aynı ekranda iki pencere açıksa (deneysel)

Aynı monitörü ortadan ikiye bölüp iki pencereyi yan yana (veya alt alta,
hatta 4 köşeye) yerleştirdiyseniz, program artık **o monitörün içinde
hangi yarıya/köşeye baktığınızı da** tahmin etmeye çalışır ve odağı doğru
pencereye verir — sadece "hangi monitör" değil, "o monitörün neresi"
sorusuna da cevap arar.

Bu, kalibrasyonda zaten topladığınız verilerle (ekstra adım/süre gerekmez)
otomatik çalışır. Ama **webcam ile bu ayrım, hangi monitöre baktığınızı
ayırt etmekten doğası gereği daha zordur** (CLAUDE.md'de de belirtildiği
gibi) — tam güvenilir olmayabilir. Sinyal belirsizse program güvenli
tarafta kalıp o monitördeki **en son kullandığınız pencereyi** seçer
(eskisi gibi). Daha iyi sonuç için pencereleri gerçekten net bir çizgiyle
(tam yarı yarıya, Windows'un Sol/Sağ yaslama kısayolları gibi) bölün.

---

## Bir şeyler ters giderse

- **Siyah pencere açılır açılmaz kapanıyor:** Bir hata olmuş demektir.
  `baslat.bat`'a tekrar çift tıklayın, bu sefer pencere kapanmadan hemen
  önce ekranda kırmızımsı bir hata yazısı görebilirsiniz, onu okuyun/not
  alın.
- **"En az iki monitör gerekli" yazısı çıkıyor:** Bilgisayara ikinci bir
  ekran bağlı değil demektir, bu programı tek ekranla kullanamazsınız.
- **Program yanlış monitörü algılıyor:** `Ctrl+Alt+C` ile yeniden kalibre
  edin, bu sefer ışığın yüzünüze daha iyi vurduğu, kameraya daha dönük
  oturduğunuz bir anda yapın.
- **Yönetici olarak açılmış bir pencereye (örn. "Yönetici olarak çalıştır"
  ile açılmış bir program) odak vermiyor:** `baslat.bat` dosyasına sağ
  tıklayıp **"Yönetici olarak çalıştır"** ile açmanız gerekir.
- **Kamera izni sorunu çözülmüyor:** Windows arama kutusuna "kamera
  gizlilik ayarları" yazıp açın, "Masaüstü uygulamalarının kameranıza
  erişmesine izin ver" seçeneğinin **açık** olduğundan emin olun.
- **"Kamera görüntüsü tamamen karanlık" uyarısı çıkıyor:** Bazı laptoplarda
  kameranın üzerinde fiziksel bir kapak/slayt vardır — yazılım kamerayı
  "açık" görse bile slayt kapalıysa görüntü simsiyah gelir. Slaytı/kapağı
  açıp tekrar deneyin.

---

## İleri düzey / teknik detaylar

Bu kısım normal kullanım için gerekli değil, meraklısına ve geliştirme için.

### Git ile indirme (ZIP yerine)

```
git clone https://github.com/tptSS/GazeFocus.git
```

### Python otomatik kurulumu nasıl çalışıyor?

`baslat.bat`, bilgisayarda uyumlu bir Python (3.10, 3.11 veya 3.12 — **3.13
desteklenmiyor**, mediapipe henüz uyumlu değil) bulamazsa önce `winget` ile,
o da yoksa python.org'dan doğrudan indirip (yönetici izni istemeden) sessizce
kurar. Her ikisi de başarısız olursa size python.org adresinden elle kurmanızı
söyler.

### Komut satırı bayrakları

```
python gaze_focus.py --preview          # kamera önizlemesi + canlı tahmin (doğruluğu kontrol için)
python gaze_focus.py --calibrate        # kalibrasyonu zorla yeniden yap
python gaze_focus.py --camera 1         # birden fazla kameran varsa farklı index dene
python gaze_focus.py --dwell 0.6        # monitör değişimi için gereken bakış süresi (sn)
python gaze_focus.py --type-guard 1.5   # son tuştan sonra bu kadar sn odak değişmesin
```

`baslat.bat --preview` gibi `baslat.bat`'a da aynı bayraklar eklenebilir.

### Kalibrasyon verisi nerede tutuluyor?

`%APPDATA%\GazeFocus\calibration.json`. Monitör sayısı/düzeni değişirse
program bunu otomatik fark edip yeniden kalibrasyon ister.

### Klavyeye bakma koruması nasıl çalışıyor?

Kalibrasyonun son adımında toplanan "klavyeye bakma" örnekleri ayrı bir sınıf
olarak eğitilir; bakış bu sınıfa en yakınsa (veya kalibrasyonda hiç görülmemiş,
aşırı uçuk bir yöne bakılıyorsa) program hiçbir monitöre odak **geçirmez**,
olduğu pencerede kalır. Bu koruma sadece **yeni kalibrasyonlarda** vardır —
bu özellik eklenmeden önce yapılmış eski bir `calibration.json` dosyanız
varsa, tam korumadan yararlanmak için `Ctrl+Alt+C` ile (veya dosyayı silip)
yeniden kalibre edin.

### Bilinen sınırlar

- Aynı ekrandaki iki pencere arasında ayrım yapmaya çalışır (bkz. yukarıdaki
  "deneysel" bölüm) ama bu, webcam için monitör-arası ayrımdan doğası
  gereği daha zor bir problem (tam hassas göz izleme için Tobii gibi özel
  donanım gerekir) — tam güvenilir olmayabilir, özellikle pencereler tam
  yarı yarıya bölünmemişse.
- Tek monitörde çalışmaz, en az 2 monitör gerekir.

"""
GazeFocus - Baktığın monitördeki pencereye klavye odağını otomatik verir.

Webcam + MediaPipe Face Mesh ile kafa yönü ve iris konumunu okur, kalibrasyonla
hangi monitöre baktığını sınıflandırır, o monitördeki pencereyi öne alır. Aynı
monitörde birden fazla pencere varsa (ör. yan yana iki sekme) bakılan bölgeye
(sol/sağ, üst/alt) göre hangisi olduğunu da ayırt etmeye çalışır (deneysel).

Kısayollar:
  Ctrl+Alt+G veya Ctrl+Alt+F  -> Duraklat / devam (oyun vb. için hızlı kapat/aç)
  Ctrl+Alt+C                 -> Yeniden kalibre et
  Ctrl+Alt+Q                 -> Çıkış

Kullanım:
  python gaze_focus.py                 # kayıtlı kalibrasyon varsa onu kullanır
  python gaze_focus.py --calibrate     # kalibrasyonu zorla
  python gaze_focus.py --preview       # kamera önizlemesi + tahmin (ayar için)
  python gaze_focus.py --camera 1 --dwell 0.5 --type-guard 1.5
"""

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from collections import Counter, deque

if sys.platform != "win32":
    sys.exit("GazeFocus yalnızca Windows'ta çalışır.")

from ctypes import wintypes


def _setup_console_encoding():
    """Pencere başlıkları Türkçe OEM kod sayfasında yazdırılamayınca program çöküyordu.
    line_buffering=True: çıktı bir dosyaya yönlendirildiğinde (ör. otomatik başlatma
    log dosyası) Python'ın print()'leri bellekte biriktirip geç yazmasını önler."""
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, OSError, ValueError):
            try:
                stream.reconfigure(errors="replace", line_buffering=True)
            except Exception:
                pass


_setup_console_encoding()

import cv2
import mediapipe as mp
import numpy as np
from pynput import keyboard

# --------------------------------------------------------------------------- #
# Win32
# --------------------------------------------------------------------------- #
# DPI farkındalığı: monitör/pencere koordinatları fiziksel piksel olsun
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

user32.GetForegroundWindow.restype = wintypes.HWND
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
kernel32.GetConsoleWindow.restype = wintypes.HWND

MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTONEAREST = 2
MOUSEEVENTF_MOVE = 0x0001
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

OWN_PID = os.getpid()


def get_monitors():
    mons = []

    def cb(hmon, _hdc, lprc, _lp):
        r = lprc.contents
        mons.append({"handle": hmon, "rect": [r.left, r.top, r.right, r.bottom]})
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    mons.sort(key=lambda m: (m["rect"][0], m["rect"][1]))
    return mons


def monitor_of(hwnd):
    return user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _is_candidate(hwnd, console_hwnd):
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    if hwnd == console_hwnd:
        return False
    if user32.GetWindowTextLengthW(hwnd) == 0:
        return False
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE):
        return False
    if _class_name(hwnd) in SKIP_CLASSES:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == OWN_PID:
        return False
    cloaked = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return cloaked.value == 0


def candidate_windows_on_monitor(hmon):
    """Z-sırasına göre (en üstteki önce) o monitördeki TÜM aday pencereler."""
    console = kernel32.GetConsoleWindow()
    found = []

    def cb(hwnd, _lp):
        if _is_candidate(hwnd, console) and monitor_of(hwnd) == hmon:
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def topmost_window_on_monitor(hmon):
    """Z-sırasına göre o monitördeki en üstteki (= orada en son kullanılan) pencere."""
    found = candidate_windows_on_monitor(hmon)
    return found[0] if found else None


def get_window_rect(hwnd):
    r = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return [r.left, r.top, r.right, r.bottom]
    return None


def pick_window_for_region(hmon, mon_rect, lr_label, lr_conf, tb_label, tb_conf, min_conf=0.7):
    """Bir monitörde birden fazla pencere varsa (ör. yan yana iki sekme),
    bakılan bölgeye (sol/sağ, üst/alt, ya da ikisi birden = köşe) ekran
    konumu en uygun olanı seçer.

    Eşleşme, pencerenin kendi alanının ne kadarının istenen bölgenin İÇİNDE
    kaldığına (örtüşme oranı) bakılarak yapılır — sadece merkez noktasına
    bakmak, tüm ekranı kaplayan bir pencereyi de yanlışlıkla "doğru yarıda"
    sayabiliyordu (gerçek pencerelerle test edilirken bulundu). Z-sırası
    sadece eşit örtüşmede ince bir tercih sebebi.

    Tek pencere varsa veya bölge sinyali belirsizse, eski davranışa (basitçe
    en üstteki pencere) döner — geriye dönük uyumlu ve her zaman güvenli.
    """
    candidates = candidate_windows_on_monitor(hmon)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    l, t, r, b = mon_rect
    mw, mh = r - l, b - t
    want_left = lr_label == 0 and lr_conf >= min_conf
    want_right = lr_label == 1 and lr_conf >= min_conf
    want_top = tb_label == 0 and tb_conf >= min_conf
    want_bottom = tb_label == 1 and tb_conf >= min_conf

    if not (want_left or want_right or want_top or want_bottom):
        return candidates[0]  # bölge belirsiz, en üstteki pencereyi ver

    # İstenen bölgenin (yarım/çeyrek) monitördeki dikdörtgeni
    rx0, rx1 = l, r
    if want_left:
        rx1 = l + mw / 2
    elif want_right:
        rx0 = l + mw / 2
    ry0, ry1 = t, b
    if want_top:
        ry1 = t + mh / 2
    elif want_bottom:
        ry0 = t + mh / 2

    MIN_OVERLAP = 0.6  # pencerenin en az %60'ı istenen bölgede olmalı
    best, best_score = None, -1.0
    for z_idx, hwnd in enumerate(candidates):
        wr = get_window_rect(hwnd)
        if not wr:
            continue
        wl, wt, wr_, wb = wr
        # Pencerenin monitörle kesişimi (ekran dışına taşan kısımları yok say)
        mx0, my0 = max(wl, l), max(wt, t)
        mx1, my1 = min(wr_, r), min(wb, b)
        win_area = max(0, mx1 - mx0) * max(0, my1 - my0)
        if win_area <= 0:
            continue
        # O kesişimin, istenen bölgeyle kesişimi
        ix0, iy0 = max(mx0, rx0), max(my0, ry0)
        ix1, iy1 = min(mx1, rx1), min(my1, ry1)
        overlap = max(0, ix1 - ix0) * max(0, iy1 - iy0)
        overlap_ratio = overlap / win_area
        if overlap_ratio < MIN_OVERLAP:
            continue
        score = overlap_ratio + 0.05 / (z_idx + 1)  # eşit örtüşmede üst Z-sırası kazanır
        if score > best_score:
            best, best_score = hwnd, score
    return best or candidates[0]


def force_foreground(hwnd):
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    # Sıfır hareketli sanal fare girdisi: Windows'un odak çalma kısıtını açar
    user32.mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0)
    if user32.SetForegroundWindow(hwnd) and user32.GetForegroundWindow() == hwnd:
        return True
    # Yedek yöntem: input kuyruklarını geçici olarak bağla
    cur = kernel32.GetCurrentThreadId()
    tgt = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if tgt:
        user32.AttachThreadInput(tgt, cur, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if tgt:
        user32.AttachThreadInput(tgt, cur, False)
    return user32.GetForegroundWindow() == hwnd


def window_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


# --------------------------------------------------------------------------- #
# Göz / kafa takibi
# --------------------------------------------------------------------------- #
def extract_features(lm):
    """Iris oranları + kafa yönü (yaw/pitch) + yüz konumu -> 6 boyutlu vektör."""
    def p(i):
        return np.array([lm[i].x, lm[i].y], dtype=np.float64)

    def proj(a, b, pt):
        v = b - a
        return float(np.dot(pt - a, v) / (np.dot(v, v) + 1e-9))

    # Yatay iris oranı (iki göz için, görüntüde soldan sağa aynı yön)
    hx = (proj(p(33), p(133), p(468)) + proj(p(362), p(263), p(473))) / 2
    # Dikey iris oranı (üst kapak -> alt kapak)
    vy = (proj(p(159), p(145), p(468)) + proj(p(386), p(374), p(473))) / 2

    left, right, nose = p(234), p(454), p(1)
    mid = (left + right) / 2
    yaw = proj(mid, right, nose)  # burnun yüz merkezine göre yatay sapması

    eyes_mid = (p(33) + p(263)) / 2
    pitch = proj(eyes_mid, p(152), nose)  # göz hattı -> çene ekseninde burun konumu

    return np.array([hx, vy, yaw, pitch, mid[0], mid[1]], dtype=np.float64)


class CameraLost(RuntimeError):
    pass


def _camera_access_denied():
    """Windows kamera gizlilik ayarlarının kapalı olup olmadığına bakar (buluşsal)."""
    import winreg

    paths = [
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"),
    ]
    for hive, path in paths:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, "Value")
                if str(value).strip().lower() == "deny":
                    return True
        except OSError:
            continue
    return False


def _probe_camera(camera_index):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    try:
        if not cap.isOpened():
            return False
        for _ in range(10):
            ok, frame = cap.read()
            if ok and frame is not None:
                return True
            time.sleep(0.1)
        return False
    finally:
        cap.release()


def ensure_camera_access(camera_index, timeout=180):
    """İlk kullanımda kamera izni kapalıysa Windows ayarlarını açar, izin verilene kadar bekler."""
    if _probe_camera(camera_index):
        return  # zaten erişilebilir, bekleme/ayar açma yok

    print("Kamera erişilemiyor.")
    try:
        denied = _camera_access_denied()
    except Exception:
        denied = False
    if denied:
        print("Windows kamera izni kapalı görünüyor.")
    print("Ayarlar açılıyor: Gizlilik ve güvenlik > Kamera "
          "(\"Masaüstü uygulamalarının kameranıza erişmesine izin ver\" açık olmalı).")
    try:
        os.startfile("ms-settings:privacy-webcam")
    except OSError:
        print("Ayarlar otomatik açılamadı; elle: Ayarlar > Gizlilik ve güvenlik > Kamera")

    print(f"İzin verip bu pencereye dönün. Bekleniyor (en fazla {timeout:.0f} sn, ESC/Ctrl+C ile iptal)...")
    deadline = time.monotonic() + timeout
    dots = 0
    while time.monotonic() < deadline:
        if _probe_camera(camera_index):
            print("\nKamera erişimi sağlandı, kalibrasyona geçiliyor.")
            return
        time.sleep(1.5)
        dots = (dots + 1) % 4
        print("\r  bekleniyor" + "." * dots + "   ", end="", flush=True)
    print()
    raise RuntimeError(
        "Kamera izni verilmedi (zaman aşımı). Ayarlar > Gizlilik ve güvenlik > Kamera bölümünden "
        "\"Masaüstü uygulamalarının kameranıza erişmesine izin ver\" seçeneğini açıp programı "
        "tekrar başlatın."
    )


class GazeTracker:
    MAX_READ_FAILURES = 60  # ~2 sn boyunca kare gelmezse kamera gitmiş say

    def __init__(self, camera_index=0):
        self.cap = None
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
            cap = cv2.VideoCapture(camera_index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ok = False
                for _ in range(10):  # ilk kareler bazen bos gelir
                    ok, _frame = cap.read()
                    if ok:
                        break
                    time.sleep(0.1)
                if ok:
                    self.cap = cap
                    break
            cap.release()
        if self.cap is None:
            raise RuntimeError(
                f"Kamera açılamadı (index {camera_index}). Başka bir uygulama kamerayı "
                f"kullanıyor olabilir; farklı bir index için --camera 1 deneyin."
            )
        self.mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.last_frame = None
        self._failures = 0

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            self._failures += 1
            if self._failures >= self.MAX_READ_FAILURES:
                raise CameraLost("Kameradan görüntü alınamıyor (çıkarıldı veya başka bir "
                                 "uygulama tarafından kullanılıyor olabilir).")
            time.sleep(0.03)
            return None
        self._failures = 0
        self.last_frame = frame
        res = self.mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not res.multi_face_landmarks:
            return None
        return extract_features(res.multi_face_landmarks[0].landmark)

    def close(self):
        if self.cap is not None:
            self.cap.release()
        self.mesh.close()


KEYBOARD_LABEL = -1  # "klavyeye/ekran dışına bakılıyor" için ayrılmış özel sınıf


class RegionClassifier:
    """Bir monitörün İÇİNDE sol/sağ ve üst/alt yarısını ayırt eden iki bağımsız
    k-NN. Aynı ekranda yan yana/alt alta iki pencere varsa hangisine bakıldığını
    tahmin etmek için kullanılır. Webcam hassasiyeti monitör-arası ayrımdan daha
    düşük olduğundan bu "best effort" bir katmandır; eksen(ler) belirsizse None
    döner ve çağıran taraf eski (sadece en üstteki pencere) davranışa düşer.
    """

    def __init__(self, lr_X, lr_y, tb_X, tb_y, k=5):
        self.lr = self._fit(lr_X, lr_y, k)
        self.tb = self._fit(tb_X, tb_y, k)

    @staticmethod
    def _fit(X, y, k):
        if len(X) < 2 or len(set(y)) < 2:
            return None
        X = np.asarray(X, dtype=np.float64)
        mu = X.mean(axis=0)
        sd = X.std(axis=0) + 1e-6
        return {
            "X": (X - mu) / sd,
            "y": np.asarray(y, dtype=int),
            "mu": mu,
            "sd": sd,
            "k": min(k, len(y)),
        }

    @staticmethod
    def _predict_axis(fitted, f):
        if fitted is None:
            return None, 0.0
        q = (f - fitted["mu"]) / fitted["sd"]
        d = np.linalg.norm(fitted["X"] - q, axis=1)
        idx = np.argpartition(d, fitted["k"] - 1)[: fitted["k"]]
        label, count = Counter(fitted["y"][idx].tolist()).most_common(1)[0]
        return label, count / fitted["k"]

    def predict(self, f):
        """-> (sol/sağ etiket (0=sol,1=sağ) ya da None, güven,
               üst/alt etiket (0=üst,1=alt) ya da None, güven)"""
        lr_label, lr_conf = self._predict_axis(self.lr, f)
        tb_label, tb_conf = self._predict_axis(self.tb, f)
        return lr_label, lr_conf, tb_label, tb_conf


class MonitorClassifier:
    """Normalize edilmiş k-NN: hangi monitöre bakıldığını oy çokluğuyla bulur.

    İki güvenlik mekanizması var:
      1) Kalibrasyon sırasında hiç görülmemiş, aşırı uçuk bir bakışsa (örn.
         klavyeye bakarken kafanın çok aşağı eğilmesi) mesafe eşiğini aşar ve
         "kararsız" (None) döner, en yakın monitöre zorla atanmaz.
      2) Kalibrasyonda ayrıca "klavyeye bak" örnekleri toplanmışsa (KEYBOARD_LABEL),
         bakış o sınıfa en yakınsa yine None döner — hiçbir monitöre odak geçmez.
    """

    def __init__(self, X, y, k=7, rects=None, regions=None):
        self.rects = rects
        self.regions = regions or {}  # {monitor_index: RegionClassifier}
        X = np.asarray(X, dtype=np.float64)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-6
        self.X = (X - self.mu) / self.sd
        self.y = np.asarray(y, dtype=int)
        self.k = min(k, len(self.y))
        self.max_dist = self._estimate_max_dist()

    def _estimate_max_dist(self):
        """Kalibrasyon noktalarının kendi aralarındaki en uç komşuluk mesafesi
        (leave-one-out). Bunun epeyce ötesindeki bir bakış, hiç kalibre
        edilmemiş bir yöne (örn. telefona bakma) bakıldığı anlamına gelir.

        Bol bir pay bırakılıyor (en uç mesafenin 3 katı): amaç günlük kullanım
        sırasındaki normal gürültüyü (ışık, poz farkı) yanlışlıkla reddetmemek,
        sadece gerçekten alakasız bakışları elemek. Klavyeye bakma durumu zaten
        ayrı bir sınıf (KEYBOARD_LABEL) olarak kalibre edildiği için bu eşikten
        bağımsız şekilde yakalanıyor.
        """
        n = len(self.X)
        k = min(self.k, n - 1)
        if k < 1:
            return float("inf")
        dists = np.empty(n)
        for i in range(n):
            d = np.linalg.norm(self.X - self.X[i], axis=1)
            d[i] = np.inf
            idx = np.argpartition(d, k - 1)[:k]
            dists[i] = d[idx].mean()
        return float(dists.max() * 3 + 1e-6)

    def predict(self, f):
        d = np.linalg.norm(self.X - (f - self.mu) / self.sd, axis=1)
        idx = np.argpartition(d, self.k - 1)[: self.k]
        if d[idx].mean() > self.max_dist:
            return None, 0.0  # kalibrasyonda hiç görülmemiş bir bakış yönü
        neighbor_labels = self.y[idx]
        # Klavye sınıfının KESİN çoğunluk kazanmasını beklemek yetersizdi: ani/kısa
        # bir klavye bakışında komşular karışık çıkıp klavye sinyali "kaybolabiliyordu"
        # (bir monitöre yanlışlıkla geçiş olarak raporlandı). Komşuların önemli bir
        # kısmı klavye sınıfındaysa, kesin çoğunluk olmasa bile temkinli davran.
        if np.mean(neighbor_labels == KEYBOARD_LABEL) >= 0.25:
            return None, 0.0
        label, count = Counter(neighbor_labels.tolist()).most_common(1)[0]
        if label == KEYBOARD_LABEL:
            return None, 0.0  # klavyeye/ekran dışına bakılıyor, odak değişmesin
        return label, count / self.k


# --------------------------------------------------------------------------- #
# Kalibrasyon
# --------------------------------------------------------------------------- #
CALIB_PATH = os.path.join(os.environ.get("APPDATA", "."), "GazeFocus", "calibration.json")
POINTS = [(0.5, 0.5), (0.15, 0.15), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85), (0.5, 0.15), (0.5, 0.85)]
KEYBOARD_SAMPLES = 80
KEYBOARD_DEADLINE = 8.0
MIN_COLLECT_TIME = 1.6  # kamera hızlıysa 25 örnek <2 sn'de toplanıyordu, nokta görünmeden kayboluyordu
DARK_FRAME_THRESHOLD = 18.0  # bu ortalama parlaklığın altı: kamera kapağı/slaytı kapalı olabilir


def _is_dark_frame(frame):
    """Kameranın lens kapağı/slaytı kapalıyken kare neredeyse tamamen siyah gelir
    (normal bir oda ~100+ parlaklık, tam kapalı lens ~0-10 civarı ölçüldü)."""
    return frame is not None and float(frame.mean()) < DARK_FRAME_THRESHOLD


class CalibrationAborted(RuntimeError):
    pass


# Kalibrasyon ekranı renk paleti
_CAL_BG = "#12141a"
_CAL_TEXT = "#eef0f6"
_CAL_MUTED = "#8891a6"
_CAL_ACCENT = "#4da6ff"   # yaklaşan/küçülen nokta
_CAL_FOCUS = "#ff5c7a"    # örnek toplanan nokta
_CAL_WARN = "#ffb020"
_CAL_KBD = "#ffb020"
_CAL_TRACK = "#262a36"    # ilerleme çubuğu zemini


def _hex_to_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _blend(c1, c2, t):
    """c1 -> c2 arası t (0..1) oranında karışım; sahte 'glow' halkaları için."""
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _draw_glow_dot(cv, cx, cy, r, color, bg=_CAL_BG):
    """Düz tek renk yerine, dışa doğru soluklaşan 3 katmanlı yumuşak nokta."""
    for rad, t in ((r * 2.2, 0.82), (r * 1.55, 0.55), (r, 0.0)):
        cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                        fill=_blend(color, bg, t), outline="")


def _draw_progress(cv, w, h, done, total):
    """Ekranın altında ince bir ilerleme çubuğu."""
    if total <= 0:
        return
    bar_w, bar_h, margin = w * 0.3, 5, 28
    x0, y0 = (w - bar_w) / 2, h - margin
    cv.create_rectangle(x0, y0, x0 + bar_w, y0 + bar_h, fill=_CAL_TRACK, outline="")
    frac = max(0.0, min(1.0, done / total))
    if frac > 0:
        cv.create_rectangle(x0, y0, x0 + bar_w * frac, y0 + bar_h, fill=_CAL_ACCENT, outline="")


def calibrate(tracker, monitors, samples_per_point=25, settle=1.1):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    X, y = [], []
    region_raw = {mi: {"lr_X": [], "lr_y": [], "tb_X": [], "tb_y": []} for mi in range(len(monitors))}
    aborted = {"v": False}
    total_steps = len(monitors) * len(POINTS) + 1  # +1: klavye adımı
    done_steps = 0

    def abort(_e=None):
        aborted["v"] = True

    for mi, m in enumerate(monitors):
        l, t, r, b = m["rect"]
        w, h = r - l, b - t
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.geometry(f"{w}x{h}+{l}+{t}")
        win.attributes("-topmost", True)
        win.bind("<Escape>", abort)
        win.focus_force()
        cv = tk.Canvas(win, bg=_CAL_BG, highlightthickness=0)
        cv.pack(fill="both", expand=True)

        # Geri sayım
        for s in (5, 4, 3, 2, 1):
            if aborted["v"]:
                break
            cv.delete("all")
            cv.create_text(
                w // 2, int(h * 0.38), fill=_CAL_MUTED, font=("Segoe UI", 17),
                text=f"Monitör {mi + 1}/{len(monitors)}  •  Noktalara doğal şekilde bak\n"
                     "(kafanı normalde nasıl çeviriyorsan öyle)   —   İptal: ESC",
                justify="center",
            )
            cv.create_text(
                w // 2, int(h * 0.52), fill=_CAL_TEXT, font=("Segoe UI", 54, "bold"),
                text=str(s),
            )
            _draw_progress(cv, w, h, done_steps, total_steps)
            win.update()
            time.sleep(1)
        if aborted["v"]:
            win.destroy()
            break

        for px, py in POINTS:
            if aborted["v"]:
                break
            cx, cy = int(px * w), int(py * h)
            # Küçülen nokta animasyonu (gözün yerleşmesi için)
            t0 = time.monotonic()
            while time.monotonic() - t0 < settle and not aborted["v"]:
                rad = 24 - 15 * (time.monotonic() - t0) / settle
                cv.delete("all")
                _draw_glow_dot(cv, cx, cy, rad, _CAL_ACCENT)
                _draw_progress(cv, w, h, done_steps, total_steps)
                win.update()
                tracker.read()  # kamera tamponunu taze tut
            if aborted["v"]:
                break
            # Örnek toplama: en az MIN_COLLECT_TIME sn sürsün (kamera hızlıysa
            # samples_per_point anında dolup nokta göz açıp kapayana dek kayboluyordu)
            t1 = time.monotonic()
            n, deadline, misses = 0, time.monotonic() + 8, 0
            while ((time.monotonic() - t1 < MIN_COLLECT_TIME or n < samples_per_point)
                   and time.monotonic() < deadline and not aborted["v"]):
                cv.delete("all")
                _draw_glow_dot(cv, cx, cy, 9, _CAL_FOCUS)
                if misses > 15:
                    if _is_dark_frame(tracker.last_frame):
                        warn_txt = "Kamera görüntüsü tamamen karanlık - kameranızdaki kapağı/slaytı açın"
                    else:
                        warn_txt = "Yüz algılanmıyor - kameraya dönük ve aydınlık olun"
                    cv.create_text(w // 2, int(h * 0.9), fill=_CAL_WARN, font=("Segoe UI", 18),
                                   text=warn_txt)
                _draw_progress(cv, w, h, done_steps, total_steps)
                win.update()
                f = tracker.read()
                if f is not None:
                    X.append(f.tolist())
                    y.append(mi)
                    n += 1
                    # Aynı anda: bu monitörün İÇİNDE sol/sağ, üst/alt sınıfları
                    if px < 0.5:
                        region_raw[mi]["lr_X"].append(f.tolist()); region_raw[mi]["lr_y"].append(0)
                    elif px > 0.5:
                        region_raw[mi]["lr_X"].append(f.tolist()); region_raw[mi]["lr_y"].append(1)
                    if py < 0.5:
                        region_raw[mi]["tb_X"].append(f.tolist()); region_raw[mi]["tb_y"].append(0)
                    elif py > 0.5:
                        region_raw[mi]["tb_X"].append(f.tolist()); region_raw[mi]["tb_y"].append(1)
                else:
                    misses += 1
            if n < samples_per_point // 2:
                print(f"  ! Monitör {mi + 1} noktasında yüz az algılandı ({n} örnek).")
            done_steps += 1
        win.destroy()
        if aborted["v"]:
            break

    # Klavyeye bakma durumunu da öğret: böylece yazarken refleks olarak
    # klavyeye bakınca yanlışlıkla bir monitöre odak geçmesin.
    if not aborted["v"]:
        l0, t0, r0, b0 = monitors[0]["rect"]
        w0, h0 = r0 - l0, b0 - t0
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.geometry(f"{w0}x{h0}+{l0}+{t0}")
        win.attributes("-topmost", True)
        win.bind("<Escape>", abort)
        win.focus_force()
        cv = tk.Canvas(win, bg=_CAL_BG, highlightthickness=0)
        cv.pack(fill="both", expand=True)

        for s in (5, 4, 3, 2, 1):
            if aborted["v"]:
                break
            cv.delete("all")
            cv.create_text(
                w0 // 2, int(h0 * 0.38), fill=_CAL_KBD, font=("Segoe UI", 18, "bold"),
                text="Son adım: Şimdi EKRANA DEĞİL, klavyenize bakın",
                justify="center",
            )
            cv.create_text(
                w0 // 2, int(h0 * 0.46), fill=_CAL_MUTED, font=("Segoe UI", 15),
                text="(yazı yazıyormuş gibi, kafanızı doğal şekilde aşağı eğin)   —   İptal: ESC",
                justify="center",
            )
            cv.create_text(
                w0 // 2, int(h0 * 0.58), fill=_CAL_TEXT, font=("Segoe UI", 54, "bold"),
                text=str(s),
            )
            _draw_progress(cv, w0, h0, done_steps, total_steps)
            win.update()
            time.sleep(1)

        if not aborted["v"]:
            t1 = time.monotonic()
            n, deadline, misses = 0, time.monotonic() + KEYBOARD_DEADLINE, 0
            while ((time.monotonic() - t1 < MIN_COLLECT_TIME or n < KEYBOARD_SAMPLES)
                   and time.monotonic() < deadline and not aborted["v"]):
                cv.delete("all")
                if misses > 15 and _is_dark_frame(tracker.last_frame):
                    txt = "Kamera görüntüsü tamamen karanlık - kameranızdaki kapağı/slaytı açın"
                else:
                    txt = "Klavyenize bakmaya devam edin..."
                cv.create_text(
                    w0 // 2, h0 // 2, fill=_CAL_KBD, font=("Segoe UI", 20, "bold"),
                    text=txt,
                    justify="center",
                )
                _draw_progress(cv, w0, h0, done_steps, total_steps)
                win.update()
                f = tracker.read()
                if f is not None:
                    X.append(f.tolist())
                    y.append(KEYBOARD_LABEL)
                    n += 1
                else:
                    misses += 1
            if n < KEYBOARD_SAMPLES // 2:
                print(f"  ! Klavye bakışı için az örnek toplandı ({n}).")
        done_steps += 1
        win.destroy()

    root.destroy()

    if aborted["v"]:
        raise CalibrationAborted("Kalibrasyon iptal edildi (ESC).")
    if len(set(y)) < 2:
        raise RuntimeError(
            "Kalibrasyon başarısız: en az iki monitör için yüz verisi gerekli. "
            "Kamera görüşünü ve ışığı kontrol edip --preview ile deneyin."
        )

    regions = {
        mi: RegionClassifier(d["lr_X"], d["lr_y"], d["tb_X"], d["tb_y"])
        for mi, d in region_raw.items()
    }

    rects = [m["rect"] for m in monitors]
    os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
    tmp = CALIB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"rects": rects, "X": X, "y": y, "regions": region_raw,
                   "created": time.strftime("%Y-%m-%d %H:%M:%S")}, fh)
    os.replace(tmp, CALIB_PATH)
    print(f"Kalibrasyon kaydedildi: {CALIB_PATH} ({len(X)} örnek)")
    return MonitorClassifier(X, y, rects=rects, regions=regions)


def load_calibration(monitors):
    if not os.path.exists(CALIB_PATH):
        return None
    try:
        with open(CALIB_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if data.get("rects") != [m["rect"] for m in monitors]:
        print("Monitör düzeni değişmiş, yeniden kalibrasyon gerekiyor.")
        return None
    if not data.get("X") or len(set(data.get("y", []))) < 2:
        print("Kayıtlı kalibrasyon bozuk, yeniden kalibrasyon gerekiyor.")
        return None
    regions = {}
    for mi_str, d in data.get("regions", {}).items():
        try:
            regions[int(mi_str)] = RegionClassifier(d["lr_X"], d["lr_y"], d["tb_X"], d["tb_y"])
        except (KeyError, ValueError, TypeError):
            continue
    print(f"Kayıtlı kalibrasyon yüklendi ({data.get('created', '?')}).")
    return MonitorClassifier(data["X"], data["y"], rects=data["rects"], regions=regions)


# --------------------------------------------------------------------------- #
# Ana döngü
# --------------------------------------------------------------------------- #
class State:
    def __init__(self):
        self.last_key = 0.0
        self.paused = False
        self.quit = False
        self.recalibrate = False


def start_keyboard(state):
    def on_press(_key):
        state.last_key = time.monotonic()

    def toggle():
        state.paused = not state.paused
        print("Duraklatıldı." if state.paused else "Devam ediyor.")

    def recal():
        state.recalibrate = True

    def quit_():
        state.quit = True

    # Not: pynput'ta Listener/GlobalHotKeys zaten daemon=True ile başlar; kwarg
    # olarak geçmek kwargs döngüsünde callback sanılıp sarmalanıyordu.
    keyboard.Listener(on_press=on_press).start()
    hk = keyboard.GlobalHotKeys({
        "<ctrl>+<alt>+g": toggle,
        "<ctrl>+<alt>+f": toggle,  # oyun oynarken hızlı aç/kapat için G ile ayni islev
        "<ctrl>+<alt>+c": recal,
        "<ctrl>+<alt>+q": quit_,
    })
    hk.start()


def run(args):
    monitors = get_monitors()
    if len(monitors) < 2:
        sys.exit("En az iki monitör gerekli.")
    print(f"{len(monitors)} monitör bulundu: " + ", ".join(str(m['rect']) for m in monitors))

    first_run = args.calibrate or not os.path.exists(CALIB_PATH)
    if first_run:
        try:
            ensure_camera_access(args.camera)
        except RuntimeError as exc:
            sys.exit(str(exc))

    try:
        tracker = GazeTracker(args.camera)
    except RuntimeError as exc:
        sys.exit(str(exc))

    # Bazı laptoplarda kameranın üstünde fiziksel bir kapak/slayt vardır; kamera
    # yazılımsal olarak "açık" görünür ama görüntü tamamen karanlık gelir.
    for _ in range(5):
        tracker.read()
    if _is_dark_frame(tracker.last_frame):
        print("UYARI: Kamera görüntüsü tamamen karanlık görünüyor. Kameranızın "
              "üzerinde fiziksel bir kapak/slayt varsa açık olduğundan emin olun.")

    clf = None if args.calibrate else load_calibration(monitors)
    if clf is None:
        try:
            clf = calibrate(tracker, monitors)
        except CalibrationAborted:
            tracker.close()
            sys.exit("Kalibrasyon iptal edildi, kalibrasyon olmadan çalışamaz.")

    state = State()
    start_keyboard(state)
    print("Çalışıyor. Ctrl+Alt+G/F duraklat | Ctrl+Alt+C kalibre | Ctrl+Alt+Q çıkış")

    ema = None
    history = deque(maxlen=args.smooth)
    region_history = deque(maxlen=4)  # bölge (sol/sağ, üst/alt) sinyalini hafifçe yumuşat
    candidate, since = None, 0.0
    last_switch = 0.0       # SADECE monitör değişimlerinde güncellenir
    last_region_switch = 0.0  # SADECE aynı monitördeki pencere değişimlerinde güncellenir
    REGION_COOLDOWN = 0.35   # monitör-içi pencere geçişleri için çok daha kısa bekleme

    try:
        while not state.quit:
            if state.recalibrate:
                state.recalibrate = False
                monitors = get_monitors()
                try:
                    clf = calibrate(tracker, monitors)
                except CalibrationAborted:
                    print("Yeniden kalibrasyon iptal edildi, önceki kalibrasyon kullanılıyor.")
                ema, candidate = None, None
                history.clear()
                region_history.clear()

            if state.paused:
                time.sleep(0.1)
                continue

            f = tracker.read()
            label, conf = None, 0.0
            if f is not None:
                ema = f if ema is None else 0.5 * f + 0.5 * ema
                label, conf = clf.predict(ema)

            if args.preview and tracker.last_frame is not None:
                frame = tracker.last_frame.copy()
                txt = "yuz yok" if label is None else f"Monitor {label + 1}  guven {conf:.2f}"
                cv2.putText(frame, txt, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                cv2.imshow("GazeFocus preview", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

            if label is None or conf < args.min_conf:
                candidate = None
                region_history.clear()
                continue

            history.append(label)
            label = Counter(history).most_common(1)[0][0]

            now = time.monotonic()
            if label != candidate:
                candidate, since = label, now
                region_history.clear()  # yeni monitöre geçince eski bölge geçmişi geçersiz
                continue
            if now - since < args.dwell:
                continue
            if now - state.last_key < args.type_guard:
                continue  # yazarken asla odak değiştirme

            # Monitör listesini her seferinde taze al (handle'lar değişebilir)
            current = get_monitors()
            if label >= len(current):
                continue
            target = current[label]["handle"]
            target_rect = current[label]["rect"]

            # Aynı monitörde birden fazla pencere varsa (ör. yan yana iki sekme),
            # bakılan bölgeye (sol/sağ, üst/alt) göre hangisi oldugunu da tahmin et.
            # Tek kareye değil, son birkaç karenin çoğunluk oyuna bakılır (titremeyi azaltır).
            lr_label = lr_conf = tb_label = tb_conf = None
            region_clf = clf.regions.get(label) if clf.regions else None
            if region_clf is not None:
                region_history.append(region_clf.predict(ema))
                lr_votes = [r[0] for r in region_history if r[0] is not None and r[1] >= args.min_conf]
                tb_votes = [r[2] for r in region_history if r[2] is not None and r[3] >= args.min_conf]
                if lr_votes:
                    lr_label, lr_conf = Counter(lr_votes).most_common(1)[0][0], 1.0
                if tb_votes:
                    tb_label, tb_conf = Counter(tb_votes).most_common(1)[0][0], 1.0

            hwnd = pick_window_for_region(
                target, target_rect, lr_label, lr_conf, tb_label, tb_conf, args.min_conf
            )
            if not hwnd:
                continue

            fg = user32.GetForegroundWindow()
            if fg == hwnd:
                continue  # zaten doğru pencerede

            # Monitör değişiyorsa tam koruma (dwell zaten yukarıda sağlandı);
            # aynı monitörde sadece pencere değişiyorsa çok daha kısa bir
            # bekleme yeterli — ikisi AYRI zamanlayıcılarla takip edilir, biri
            # diğerini "sıcak" tutup geciktirmesin diye (ör. hızlı sol/sağ
            # geçişleri yapıp sonra başka monitöre bakınca o geçiş gecikmesin).
            same_monitor_as_before = fg and monitor_of(fg) == target
            if same_monitor_as_before:
                if now - last_region_switch < REGION_COOLDOWN:
                    continue
                last_region_switch = now
            else:
                if now - last_switch < args.cooldown:
                    continue
                last_switch = now

            ok = force_foreground(hwnd)
            print(f"[{time.strftime('%H:%M:%S')}] Monitör {label + 1} -> "
                  f"{window_title(hwnd)[:60]!r} {'OK' if ok else 'BAŞARISIZ'}")
    except KeyboardInterrupt:
        pass
    except CameraLost as exc:
        print(f"Kamera kayboldu: {exc}")
    finally:
        tracker.close()
        if args.preview:
            cv2.destroyAllWindows()
        print("Kapatıldı.")


def main():
    ap = argparse.ArgumentParser(description="Bakılan monitöre otomatik klavye odağı")
    ap.add_argument("--camera", type=int, default=0, help="Kamera index (varsayılan 0)")
    ap.add_argument("--calibrate", action="store_true", help="Kalibrasyonu yeniden yap")
    ap.add_argument("--preview", action="store_true", help="Kamera önizlemesi göster")
    ap.add_argument("--dwell", type=float, default=0.45, help="Geçiş için bakış süresi (sn)")
    ap.add_argument("--type-guard", type=float, default=1.2,
                    help="Son tuştan sonra bu kadar sn odak değişmez")
    ap.add_argument("--cooldown", type=float, default=0.8, help="İki geçiş arası min. süre (sn)")
    ap.add_argument("--min-conf", type=float, default=0.7, help="Min. sınıflandırma güveni (0-1)")
    ap.add_argument("--smooth", type=int, default=7, help="Çoğunluk oyu pencere boyu (kare)")
    run(ap.parse_args())


if __name__ == "__main__":
    main()

"""
GazeFocus - Baktığın monitördeki pencereye klavye odağını otomatik verir.

Webcam + MediaPipe Face Mesh ile kafa yönü ve iris konumunu okur, kalibrasyonla
hangi monitöre baktığını sınıflandırır, o monitördeki en üstteki pencereyi öne alır.

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


def topmost_window_on_monitor(hmon):
    """Z-sırasına göre o monitördeki en üstteki (= orada en son kullanılan) pencere."""
    console = kernel32.GetConsoleWindow()
    found = []

    def cb(hwnd, _lp):
        if _is_candidate(hwnd, console) and monitor_of(hwnd) == hmon:
            found.append(hwnd)
            return False  # ilk bulunan yeterli
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else None


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


class MonitorClassifier:
    """Normalize edilmiş k-NN: hangi monitöre bakıldığını oy çokluğuyla bulur.

    İki güvenlik mekanizması var:
      1) Kalibrasyon sırasında hiç görülmemiş, aşırı uçuk bir bakışsa (örn.
         klavyeye bakarken kafanın çok aşağı eğilmesi) mesafe eşiğini aşar ve
         "kararsız" (None) döner, en yakın monitöre zorla atanmaz.
      2) Kalibrasyonda ayrıca "klavyeye bak" örnekleri toplanmışsa (KEYBOARD_LABEL),
         bakış o sınıfa en yakınsa yine None döner — hiçbir monitöre odak geçmez.
    """

    def __init__(self, X, y, k=7, rects=None):
        self.rects = rects
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
        label, count = Counter(self.y[idx].tolist()).most_common(1)[0]
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


class CalibrationAborted(RuntimeError):
    pass


def calibrate(tracker, monitors, samples_per_point=25, settle=0.9):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    X, y = [], []
    aborted = {"v": False}

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
        cv = tk.Canvas(win, bg="#111111", highlightthickness=0)
        cv.pack(fill="both", expand=True)

        # Kısa geri sayım
        for s in (3, 2, 1):
            if aborted["v"]:
                break
            cv.delete("all")
            cv.create_text(
                w // 2, h // 2, fill="white", font=("Segoe UI", 26),
                text=f"Monitör {mi + 1}/{len(monitors)}\n\nNoktalara doğal şekilde bak "
                     f"(kafanı normalde nasıl çeviriyorsan öyle)\n\nİptal: ESC\n\n{s}",
                justify="center",
            )
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
                rad = 28 - 18 * (time.monotonic() - t0) / settle
                cv.delete("all")
                cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill="#3aa0ff", outline="")
                win.update()
                tracker.read()  # kamera tamponunu taze tut
            if aborted["v"]:
                break
            # Örnek toplama
            n, deadline, misses = 0, time.monotonic() + 8, 0
            while n < samples_per_point and time.monotonic() < deadline and not aborted["v"]:
                cv.delete("all")
                cv.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill="#ff4d4d", outline="")
                if misses > 15:
                    cv.create_text(w // 2, int(h * 0.9), fill="#ffcc55", font=("Segoe UI", 18),
                                   text="Yüz algılanmıyor - kameraya dönük ve aydınlık olun")
                win.update()
                f = tracker.read()
                if f is not None:
                    X.append(f.tolist())
                    y.append(mi)
                    n += 1
                else:
                    misses += 1
            if n < samples_per_point // 2:
                print(f"  ! Monitör {mi + 1} noktasında yüz az algılandı ({n} örnek).")
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
        cv = tk.Canvas(win, bg="#111111", highlightthickness=0)
        cv.pack(fill="both", expand=True)

        for s in (3, 2, 1):
            if aborted["v"]:
                break
            cv.delete("all")
            cv.create_text(
                w0 // 2, h0 // 2, fill="white", font=("Segoe UI", 26),
                text="Son adım: Şimdi EKRANA DEĞİL, klavyenize bakın\n"
                     "(yazı yazıyormuş gibi, kafanızı doğal şekilde aşağı eğin)\n\n"
                     f"İptal: ESC\n\n{s}",
                justify="center",
            )
            win.update()
            time.sleep(1)

        if not aborted["v"]:
            n, deadline, misses = 0, time.monotonic() + KEYBOARD_DEADLINE, 0
            while n < KEYBOARD_SAMPLES and time.monotonic() < deadline and not aborted["v"]:
                cv.delete("all")
                cv.create_text(
                    w0 // 2, h0 // 2, fill="#ff8844", font=("Segoe UI", 20),
                    text="Klavyenize bakmaya devam edin...",
                    justify="center",
                )
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
        win.destroy()

    root.destroy()

    if aborted["v"]:
        raise CalibrationAborted("Kalibrasyon iptal edildi (ESC).")
    if len(set(y)) < 2:
        raise RuntimeError(
            "Kalibrasyon başarısız: en az iki monitör için yüz verisi gerekli. "
            "Kamera görüşünü ve ışığı kontrol edip --preview ile deneyin."
        )

    rects = [m["rect"] for m in monitors]
    os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
    tmp = CALIB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"rects": rects, "X": X, "y": y,
                   "created": time.strftime("%Y-%m-%d %H:%M:%S")}, fh)
    os.replace(tmp, CALIB_PATH)
    print(f"Kalibrasyon kaydedildi: {CALIB_PATH} ({len(X)} örnek)")
    return MonitorClassifier(X, y, rects=rects)


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
    print(f"Kayıtlı kalibrasyon yüklendi ({data.get('created', '?')}).")
    return MonitorClassifier(data["X"], data["y"], rects=data["rects"])


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
    candidate, since = None, 0.0
    last_switch = 0.0

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
                continue

            history.append(label)
            label = Counter(history).most_common(1)[0][0]

            now = time.monotonic()
            if label != candidate:
                candidate, since = label, now
                continue
            if now - since < args.dwell:
                continue
            if now - state.last_key < args.type_guard:
                continue  # yazarken asla odak değiştirme
            if now - last_switch < args.cooldown:
                continue

            # Monitör listesini her seferinde taze al (handle'lar değişebilir)
            current = get_monitors()
            if label >= len(current):
                continue
            target = current[label]["handle"]
            fg = user32.GetForegroundWindow()
            if fg and monitor_of(fg) == target:
                continue

            hwnd = topmost_window_on_monitor(target)
            if hwnd:
                ok = force_foreground(hwnd)
                last_switch = now
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


import os
import json
import functools
import shutil
import uuid
import random
import string
import platform
from kivy.app import App
from kivy.utils import platform as kivy_platform
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.properties import (StringProperty, NumericProperty,
                              ListProperty, BooleanProperty, ObjectProperty)
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.scatter import Scatter
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.graphics import (Color, Rectangle, RoundedRectangle, Line, Ellipse, Rotate,
                           PushMatrix, PopMatrix,
                           StencilPush, StencilUse, StencilUnUse, StencilPop)

# ---------------------------------------------------------------------------
if os.name == "nt":
    Window.size = (380, 760)

# --- BUGFIX 2: رفتار کیبورد نرم‌افزاری روی اندروید ---
# بدون این تنظیم، در بعضی دستگاه‌ها کیبورد روی فیلد ورودی می‌افتد یا اصلاً
# فوکوس/باز شدن کیبورد به‌درستی انجام نمی‌شود.
# چیدمان صفحه‌ی لاگین داخل ScrollView عمودی است و فیلدها می‌توانند نزدیک پایین
# صفحه باشند؛ "below_target" صفحه را دقیقاً تا جایی بالا می‌برد که فیلد هدف
# بالای کیبورد قرار بگیرد (برخلاف "pan" که کل پنجره را بدون توجه به هدف
# می‌لغزاند و در فرم‌های بلند باعث پریدن چیدمان می‌شود).
if kivy_platform == "android":
    Window.softinput_mode = "below_target"
    Window.keyboard_anim_args = {"d": 0.2, "t": "out_quart"}

# ---------------------------------------------------------------------------
# BUGFIX 1: شکل‌دهی حروف فارسی (reshape) + جهت‌دهی دوسویه (bidi)
# دو مرحله کاملاً از هم جدا شده‌اند تا بتوان هرکدام را مستقل تست/لاگ کرد.
# arabic_reshaper به‌صورت پیش‌فرض فایل default-config.ini را از داخل بسته
# می‌خواند؛ این فایل در build با python-for-android معمولاً حذف می‌شود و
# reshape() روی دستگاه exception می‌دهد. پس یک نمونه با کانفیگ صریحِ درون‌کد
# می‌سازیم تا هیچ وابستگی‌ای به فایل خارجی نداشته باشیم.
_RESHAPE_AVAILABLE = False
_reshaper = None
_RESHAPE_ERROR = ""
try:
    from arabic_reshaper import ArabicReshaper  # type: ignore
    _reshaper = ArabicReshaper(configuration={
        'delete_harakat': False,
        'support_ligatures': True,
        'use_unshaped_instead_of_isolated': False,
    })
    _reshaper.reshape("\u0644\u062d\u0638\u0647")  # smoke-test روی خود دستگاه
    _RESHAPE_AVAILABLE = True
except Exception as _e:  # ImportError یا خطای کانفیگ
    _RESHAPE_ERROR = f"{type(_e).__name__}: {_e}"
    _reshaper = None
    # تلاش دوم: API ماژولی (اگر فایل کانفیگ سرجایش باشد)
    try:
        import arabic_reshaper as _ar_mod  # type: ignore
        _ar_mod.reshape("\u0644\u062d\u0638\u0647")

        class _ModuleReshaper:
            @staticmethod
            def reshape(t):
                return _ar_mod.reshape(t)

        _reshaper = _ModuleReshaper()
        _RESHAPE_AVAILABLE = True
        _RESHAPE_ERROR += " | fallback=module-level reshape OK"
    except Exception as _e2:
        _RESHAPE_ERROR += f" | fallback failed: {type(_e2).__name__}: {_e2}"

_BIDI_AVAILABLE = False
_BIDI_ERROR = ""
try:
    from bidi.algorithm import get_display  # type: ignore
    get_display("\u0644\u062d\u0638\u0647")  # smoke-test
    _BIDI_AVAILABLE = True
except Exception as _e:
    _BIDI_ERROR = f"{type(_e).__name__}: {_e}"

    def get_display(t):  # type: ignore
        return t


@functools.lru_cache(maxsize=4000)
def _reshape_step(text: str) -> str:
    """مرحله‌ی ۱ — چسباندن حروف. خطا را قابل مشاهده در logcat می‌کند."""
    if not text or not _RESHAPE_AVAILABLE or _reshaper is None:
        return text
    try:
        return _reshaper.reshape(text)
    except Exception as e:
        print(f"[FA][reshape][ERROR] {type(e).__name__}: {e}")
        return text


@functools.lru_cache(maxsize=4000)
def _bidi_step(text: str) -> str:
    """مرحله‌ی ۲ — بازچینی دوسویه. خطا را قابل مشاهده در logcat می‌کند."""
    if not text or not _BIDI_AVAILABLE:
        return text
    try:
        return get_display(text)
    except Exception as e:
        print(f"[FA][bidi][ERROR] {type(e).__name__}: {e}")
        return text


# TODO: remove after debug — لاگ تشخیصی وضعیت reshape/bidi روی دستگاه
print(f"[FA][diag] platform={kivy_platform} "
      f"_RESHAPE_AVAILABLE={_RESHAPE_AVAILABLE} reshape_err={_RESHAPE_ERROR or 'none'} "
      f"_BIDI_AVAILABLE={_BIDI_AVAILABLE} bidi_err={_BIDI_ERROR or 'none'}")
try:
    _t = "\u0644\u062d\u0638\u0647\u200c\u0633\u0627\u0632"
    print("[FA][diag] raw     :", [hex(ord(c)) for c in _t])
    print("[FA][diag] reshaped:", [hex(ord(c)) for c in _reshape_step(_t)])
    print("[FA][diag] bidi    :", [hex(ord(c)) for c in _bidi_step(_reshape_step(_t))])
except Exception as _e:
    print(f"[FA][diag][ERROR] {_e}")

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

try:
    from plyer import camera as plyer_camera
    from plyer import filechooser as plyer_filechooser
    _PLYER_AVAILABLE = True
except ImportError:
    _PLYER_AVAILABLE = False

try:
    from kivy.core.clipboard import Clipboard
    _CLIPBOARD_AVAILABLE = True
except ImportError:
    _CLIPBOARD_AVAILABLE = False


def fa(text: str) -> str:
    """BUGFIX 1: هر مرحله جداگانه و با لاگ خطای قابل مشاهده اجرا می‌شود."""
    if not text:
        return text
    return _bidi_step(_reshape_step(text))


# ---------------------------------------------------------------------------
# مسیرها
# ---------------------------------------------------------------------------
# --- مسیر داده‌ی کاربر (قابل نوشتن، وابسته به پلتفرم) ---
def _resolve_save_dir() -> str:
    if kivy_platform == "android":
        try:
            from android.storage import app_storage_path  # type: ignore
            return app_storage_path()
        except Exception:
            return os.path.join(os.path.expanduser("~"), "LahzeSaz")
    return r"C:\Users\User\Documents\python files\Lahze saz"

SAVE_DIR = _resolve_save_dir()
try:
    os.makedirs(SAVE_DIR, exist_ok=True)
except Exception:
    pass

# --- مسیر asset ثابت اپ (تصاویر رابط کاربری، همراه با کد بسته‌بندی می‌شود) ---
# --- مسیر asset ثابت اپ (تصاویر رابط کاربری، همراه با کد بسته‌بندی می‌شود) ---
# مسیرهای احتمالی پوشه‌ی assets: اول کنار main.py (حالت پکیج/APK)، سپس مسیر
# توسعه روی ویندوز کاربر.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ASSETS_CANDIDATES = [
    os.path.join(_APP_DIR, "assets"),
    r"C:\Users\User\Documents\python files\Lahze saz\assets",
]
ASSETS_DIR = next((p for p in _ASSETS_CANDIDATES if os.path.isdir(p)), _ASSETS_CANDIDATES[0])

_FONTS_CANDIDATES = [
    os.path.join(_APP_DIR, "fonts"),
    r"C:\Users\User\Documents\python files\Lahze saz\fonts",
]
FONTS_DIR = next((p for p in _FONTS_CANDIDATES if os.path.isdir(p)), _FONTS_CANDIDATES[0])

SAVE_FILE = os.path.join(SAVE_DIR, "user_data.json")
# app_settings.json حذف شد: هیچ فایل تنظیماتی بیرون از پوشه‌های اکانت
# نوشته نمی‌شود؛ «آخرین مسیر انتخابی» فقط در حافظه‌ی همین اجرا نگه‌داری می‌شود.
DEVICE_FILE = os.path.join(SAVE_DIR, "device_id.txt")

# ---------------------------------------------------------------------------
# مدیریت مرکزی مسیر تصاویر و فونت
# ---------------------------------------------------------------------------
# نگاشت «کلید منطقی -> اسم دقیق فایل روی دیسک». اسم فایل‌ها دقیقاً همان چیزی است
# که در پوشه‌ی assets وجود دارد (با همان حروف‌نویسی، حتی اگر غلط املایی داشته
# باشد). اگر کاربر محتوای فایل را عوض کند اما اسمش را نگه دارد، در اجرای بعدی
# به‌طور خودکار همان فایل جدید بارگذاری می‌شود؛ نیازی به تغییر کد نیست.
ASSET_FILES = {
    "accept":          "accept.png",
    "action":          "action.png",
    "back":            "back.png",
    "boy":             "boy.png",
    "camera":          "camera.png",
    "camping":         "camping.png",
    "cooking":         "cooking.png",
    "copy":            "copy.png",
    "eye":             "eye.png",
    "eye_open":        "eye-open.png",
    "garbage":         "garbage.png",
    "girl":            "girl.png",
    "home":            "home.png",
    "log_out":         "log-out.png",
    "painting":        "painting.png",
    "question":        "question.png",   # اسم واقعی فایل روی دیسک همین است (بدون u)
    "random":          "random.png",
    "setting":         "setting.png",
    "square":          "square.png",
    "note":            "note.png",
    "sun":             "sun.png",
    "moon":            "moon.png",
}

_MISSING_ASSETS_LOGGED = set()

def resolve_asset(key: str) -> str:
    """مسیر کامل یک asset را برمی‌گرداند.
    اگر فایل وجود نداشت، رشته‌ی خالی برمی‌گرداند (تا Kivy کرش نکند) و یک بار
    در کنسول هشدار می‌دهد.
    """
    name = ASSET_FILES.get(key)
    if not name:
        return ""
    path = os.path.join(ASSETS_DIR, name)
    if os.path.exists(path):
        return path
    if key not in _MISSING_ASSETS_LOGGED:
        _MISSING_ASSETS_LOGGED.add(key)
        print(f"[assets] هشدار: فایل پیدا نشد -> {path}")
    return ""

# ثابت‌های سازگار با بقیه‌ی کد (همه از resolve_asset استفاده می‌کنند)
BOY_IMAGE              = resolve_asset("boy")
GIRL_IMAGE             = resolve_asset("girl")
EYE_IMAGE              = resolve_asset("eye")
EYE_OPEN_IMAGE         = resolve_asset("eye_open")
CAMERA_IMAGE           = resolve_asset("camera")
SETTING_IMAGE          = resolve_asset("setting")
LOGOUT_IMAGE           = resolve_asset("log_out")
GARBAGE_IMAGE          = resolve_asset("garbage")     # آیکون حذف اکانت
QUESTION_IMAGE         = resolve_asset("question")    # آیکون راهنما (علامت سوال)
PAINTING_IMAGE         = resolve_asset("painting")
ACTION_IMAGE           = resolve_asset("action")
COOKING_IMAGE          = resolve_asset("cooking")
CAMPING_IMAGE          = resolve_asset("camping")
HOME_IMAGE             = resolve_asset("home")
COPY_IMAGE             = resolve_asset("copy")
BACK_IMAGE             = resolve_asset("back")
RANDOM_IMAGE           = resolve_asset("random")
CHECKBOX_EMPTY_IMAGE   = resolve_asset("square")
CHECKBOX_CHECKED_IMAGE = resolve_asset("accept")
NOTE_IMAGE             = resolve_asset("note")

MEMORIES_DIR = os.path.join(SAVE_DIR, "memories")
AVATAR_DIR = os.path.join(SAVE_DIR, "avatars")

UPLOAD_URL = "https://example.com/upload"
MAX_UPLOAD_SIZE = 300 * 1024

# ---------------------------------------------------------------------------
# فونت فارسی
# ---------------------------------------------------------------------------
# اسم واقعی فایل فونت روی دیسک کاربر: Vazirmatn-Regular.ttf
# ابتدا پوشه‌ی fonts کنار main.py (برای پکیج/APK)، سپس مسیر توسعه روی ویندوز.
FONT_FILE_NAME = "Vazirmatn-Regular.ttf"
_FONT_CANDIDATES = [
    os.path.join(FONTS_DIR, FONT_FILE_NAME),
    os.path.join(_APP_DIR, "fonts", FONT_FILE_NAME),
    r"C:\Users\User\Documents\python files\Lahze saz\fonts\Vazirmatn-Regular.ttf",
]
FONT_PATH = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)

if FONT_PATH:
    try:
        LabelBase.register(name="Vazir", fn_regular=FONT_PATH, fn_bold=FONT_PATH)
        APP_FONT = "Vazir"
    except Exception as e:
        print(f"[font] ثبت فونت فارسی با خطا مواجه شد: {e} -> استفاده از Roboto")
        APP_FONT = "Roboto"
else:
    print("[font] هشدار: فایل فونت فارسی پیدا نشد. مسیرهای بررسی‌شده:")
    for _p in _FONT_CANDIDATES:
        print(f"        - {_p}")
    print("        -> برنامه با فونت پیش‌فرض (Roboto) ادامه می‌دهد.")
    APP_FONT = "Roboto"

# ---------------------------------------------------------------------------
# فونت اختصاصی «دفترچه خاطرات» — BHoma (با Fallback به فونت اصلی)
# ---------------------------------------------------------------------------
BHOMA_FILE_NAME = "BHoma.ttf"
_BHOMA_CANDIDATES = [
    os.path.join(FONTS_DIR, BHOMA_FILE_NAME),
    os.path.join(FONTS_DIR, "Bhoma.ttf"),
    os.path.join(FONTS_DIR, "bhoma.ttf"),
    os.path.join(_APP_DIR, "fonts", BHOMA_FILE_NAME),
    r"C:\Users\User\Documents\python files\Lahze saz\fonts\BHoma.ttf",
]
BHOMA_PATH = next((p for p in _BHOMA_CANDIDATES if os.path.exists(p)), None)
if BHOMA_PATH:
    try:
        LabelBase.register(name="BHoma", fn_regular=BHOMA_PATH, fn_bold=BHOMA_PATH)
        DIARY_FONT = "BHoma"
        print(f"[font] BHoma registered: {BHOMA_PATH}")
    except Exception as e:
        print(f"[font] ثبت فونت BHoma با خطا مواجه شد: {e} -> استفاده از فونت اصلی")
        DIARY_FONT = APP_FONT
else:
    print("[font] هشدار: BHoma.ttf پیدا نشد؛ دفترچه با فونت اصلی نمایش داده می‌شود.")
    DIARY_FONT = APP_FONT

Window.clearcolor = (0.97, 0.97, 0.98, 1)

# ---------------------------------------------------------------------------
# تم‌ها
# ---------------------------------------------------------------------------
THEME_PINK = {
    "bg": (0.99, 0.92, 0.93, 1), "accent": (0.86, 0.60, 0.68, 1),
    "accent_soft": (0.86, 0.60, 0.68, 0.18), "card_border": (1, 0.82, 0.86, 0.6),
    "title": (0.75, 0.45, 0.55, 1), "input_bg": (0.97, 0.93, 0.94, 1),
    "window_bg": (0.97, 0.94, 0.95, 1), "bubble1": (0.93, 0.86, 0.95, 1),
    "bubble2": (0.86, 0.93, 0.90, 1), "gender_sel": (1, 0.85, 0.90, 1),
    "gender_brd_sel": (0.85, 0.55, 0.65, 1), "avatar_ring": (0.82, 0.55, 0.65, 1),
    "cat_sub": (0.55, 0.5, 0.52, 1),
}

THEME_BLUE = {
    "bg": (0.91, 0.95, 0.99, 1), "accent": (0.42, 0.66, 0.87, 1),
    "accent_soft": (0.42, 0.66, 0.87, 0.18), "card_border": (0.72, 0.87, 1.00, 0.6),
    "title": (0.28, 0.50, 0.75, 1), "input_bg": (0.93, 0.96, 0.99, 1),
    "window_bg": (0.93, 0.96, 0.99, 1), "bubble1": (0.82, 0.91, 0.98, 1),
    "bubble2": (0.80, 0.90, 0.95, 1), "gender_sel": (0.82, 0.91, 0.98, 1),
    "gender_brd_sel": (0.42, 0.66, 0.87, 1), "avatar_ring": (0.42, 0.66, 0.87, 1),
    "cat_sub": (0.45, 0.55, 0.68, 1),
}

# تم پیش‌فرض سفید (وقتی جنسیت هنوز انتخاب نشده)
THEME_WHITE = {
    "bg": (0.98, 0.98, 0.99, 1), "accent": (0.55, 0.58, 0.65, 1),
    "accent_soft": (0.55, 0.58, 0.65, 0.18), "card_border": (0.85, 0.85, 0.88, 0.7),
    "title": (0.25, 0.25, 0.28, 1), "input_bg": (0.95, 0.95, 0.97, 1),
    "window_bg": (0.97, 0.97, 0.98, 1), "bubble1": (0.93, 0.93, 0.96, 1),
    "bubble2": (0.90, 0.90, 0.93, 1), "gender_sel": (0.94, 0.94, 0.97, 1),
    "gender_brd_sel": (0.55, 0.58, 0.65, 1), "avatar_ring": (0.55, 0.58, 0.65, 1),
    "cat_sub": (0.50, 0.50, 0.55, 1),
}

# --- نسخه‌های تیره (تم مشکی) --------------------------------------------
# رنگ جنسیتی (accent/title/gender_sel/gender_brd_sel/avatar_ring) دقیقاً همان
# نسخه‌ی روشن می‌ماند؛ فقط رنگ‌های خنثی تیره می‌شوند.
THEME_PINK_DARK = {
    "bg": (0.09, 0.08, 0.09, 1), "accent": THEME_PINK["accent"],
    "accent_soft": (0.86, 0.60, 0.68, 0.22), "card_border": (0.30, 0.24, 0.27, 0.7),
    "title": THEME_PINK["title"], "input_bg": (0.16, 0.14, 0.16, 1),
    "window_bg": (0.07, 0.06, 0.07, 1), "bubble1": (0.16, 0.13, 0.17, 1),
    "bubble2": (0.13, 0.16, 0.15, 1), "gender_sel": THEME_PINK["gender_sel"],
    "gender_brd_sel": THEME_PINK["gender_brd_sel"],
    "avatar_ring": THEME_PINK["avatar_ring"],
    "cat_sub": (0.72, 0.68, 0.70, 1),
}

THEME_BLUE_DARK = {
    "bg": (0.07, 0.09, 0.11, 1), "accent": THEME_BLUE["accent"],
    "accent_soft": (0.42, 0.66, 0.87, 0.22), "card_border": (0.22, 0.28, 0.35, 0.7),
    "title": THEME_BLUE["title"], "input_bg": (0.13, 0.16, 0.19, 1),
    "window_bg": (0.06, 0.07, 0.09, 1), "bubble1": (0.12, 0.17, 0.22, 1),
    "bubble2": (0.11, 0.15, 0.19, 1), "gender_sel": THEME_BLUE["gender_sel"],
    "gender_brd_sel": THEME_BLUE["gender_brd_sel"],
    "avatar_ring": THEME_BLUE["avatar_ring"],
    "cat_sub": (0.68, 0.74, 0.82, 1),
}

# معادل تیره‌ی THEME_WHITE (وقتی هنوز جنسیت انتخاب نشده)
THEME_BLACK = {
    "bg": (0.08, 0.08, 0.09, 1), "accent": (0.62, 0.65, 0.72, 1),
    "accent_soft": (0.62, 0.65, 0.72, 0.20), "card_border": (0.25, 0.25, 0.28, 0.7),
    "title": (0.92, 0.92, 0.94, 1), "input_bg": (0.15, 0.15, 0.17, 1),
    "window_bg": (0.06, 0.06, 0.07, 1), "bubble1": (0.14, 0.14, 0.17, 1),
    "bubble2": (0.12, 0.12, 0.15, 1), "gender_sel": (0.20, 0.20, 0.23, 1),
    "gender_brd_sel": (0.62, 0.65, 0.72, 1), "avatar_ring": (0.62, 0.65, 0.72, 1),
    "cat_sub": (0.70, 0.70, 0.75, 1),
}

# ---------------------------------------------------------------------------
# پالت خنثی (neutral) — پس‌زمینه‌ها، متن‌های عمومی، بوردرها و کارت‌ها
# رنگ‌های برندی/جنسیتی (accent, gender_sel, gender_brd_sel, avatar_ring) و
# رنگ تگ‌های دسته‌بندی ایده‌ها عمداً اینجا نیستند و دست‌نخورده می‌مانند.
# ---------------------------------------------------------------------------
NEUTRAL_LIGHT = {
    "surface": (1.00, 1.00, 1.00, 1.00),
    "surface_92": (1.00, 1.00, 1.00, 0.92),
    "surface_soft": (1.00, 1.00, 1.00, 0.55),
    "surface_glass": (1.00, 1.00, 1.00, 0.28),
    "glass_grey": (0.55, 0.55, 0.58, 0.32),
    "glass_border": (1.00, 1.00, 1.00, 0.55),
    "text_primary": (0.35, 0.30, 0.32, 1.00),
    "text_secondary": (0.55, 0.50, 0.52, 1.00),
    "text_body": (0.48, 0.38, 0.40, 1.00),
    "text_strong": (0.23, 0.13, 0.16, 1.00),
    "text_hint": (0.65, 0.60, 0.62, 1.00),
    "border": (0.85, 0.85, 0.88, 0.70),
    "divider": (0.80, 0.78, 0.80, 0.45),
    "avatar_inner": (0.96, 0.93, 0.94, 1.00),
    "dialog_bg": (0.20, 0.20, 0.23, 0.98),
    "dialog_border": (0.45, 0.45, 0.50, 0.80),
    "dialog_text": (0.95, 0.95, 0.96, 1.00),
    "paper": (1.00, 0.99, 0.93, 1.00),
    "paper_line": (0.80, 0.72, 0.50, 0.55),
    "paper_text": (0.25, 0.20, 0.18, 1.00),
    "paper_sub": (0.55, 0.45, 0.30, 1.00),
    "info_male": (0.88, 0.94, 1.00, 1.00),
    "info_female": (1.00, 0.92, 0.95, 1.00),
}

NEUTRAL_DARK = {
    "surface": (0.15, 0.15, 0.17, 1.00),
    "surface_92": (0.14, 0.14, 0.16, 0.94),
    "surface_soft": (0.24, 0.24, 0.27, 0.75),
    "surface_glass": (0.30, 0.30, 0.34, 0.35),
    "glass_grey": (0.30, 0.30, 0.34, 0.40),
    "glass_border": (1.00, 1.00, 1.00, 0.16),
    "text_primary": (0.93, 0.93, 0.95, 1.00),
    "text_secondary": (0.74, 0.72, 0.75, 1.00),
    "text_body": (0.82, 0.79, 0.81, 1.00),
    "text_strong": (0.96, 0.96, 0.97, 1.00),
    "text_hint": (0.62, 0.60, 0.63, 1.00),
    "border": (0.35, 0.35, 0.40, 0.70),
    "divider": (1.00, 1.00, 1.00, 0.12),
    "avatar_inner": (0.18, 0.17, 0.19, 1.00),
    "dialog_bg": (0.12, 0.12, 0.14, 0.98),
    "dialog_border": (0.38, 0.38, 0.43, 0.80),
    "dialog_text": (0.94, 0.94, 0.96, 1.00),
    "paper": (0.15, 0.14, 0.12, 1.00),
    "paper_line": (0.45, 0.40, 0.28, 0.55),
    "paper_text": (0.93, 0.91, 0.86, 1.00),
    "paper_sub": (0.72, 0.66, 0.52, 1.00),
    "info_male": (0.13, 0.16, 0.21, 1.00),
    "info_female": (0.20, 0.14, 0.17, 1.00),
}

# کلیدهایی که به‌صورت پراپرتیِ اپ (app.theme_<key>) هم در KV در دسترس‌اند
NEUTRAL_KEYS = tuple(NEUTRAL_LIGHT.keys())


def neutral(key, dark=None):
    """رنگ خنثیِ متناظر با حالت روشن/تیره را برمی‌گرداند."""
    if dark is None:
        try:
            _app = App.get_running_app()
            dark = bool(_app.dark_mode) if _app else False
        except Exception:
            dark = False
    pal = NEUTRAL_DARK if dark else NEUTRAL_LIGHT
    return tuple(pal.get(key, NEUTRAL_LIGHT.get(key, (1, 1, 1, 1))))


# ---------------------------------------------------------------------------
# دسته‌بندی‌ها
# ---------------------------------------------------------------------------
CATEGORIES = [
    {"id": "active",   "title": " هیجانی و فعال",          "subtitle": "اکشن و پرانرژی",   "emoji": "🔥", "icon": ACTION_IMAGE,   "color": (1, 0.78, 0.70, 1)},
    {"id": "creative", "title": " خلاقانه و هنری",          "subtitle": "تجربه‌های جدید",    "emoji": "🎨", "icon": PAINTING_IMAGE, "color": (0.85, 0.78, 0.95, 1)},
    {"id": "nature",   "title": " طبیعت‌گردی ",   "subtitle": "آرامش و هوای پاک", "emoji": "🌿", "icon": CAMPING_IMAGE,  "color": (0.75, 0.88, 0.78, 1)},
    {"id": "food",     "title": "سفره دو نفره",                "subtitle": "خوشمزه و گپ‌زدنی", "emoji": "🍽️", "icon": COOKING_IMAGE,  "color": (1, 0.87, 0.70, 1)},
    {"id": "home",     "title": "دیت‌های خانگی",         "subtitle": "دنج و صمیمی",      "emoji": "🏠", "icon": HOME_IMAGE,     "color": (0.80, 0.87, 0.93, 1)},
    {"id": "diary",    "title": "دفترچه خاطرات",           "subtitle": "یادداشت‌های شخصی تو", "emoji": "📓", "icon": NOTE_IMAGE,             "color": (0.98, 0.94, 0.80, 1), "min_age": 15, "max_age": 20},
]

# ---------------------------------------------------------------------------
# داده‌ی ایده‌ها (اضافه‌شده از نسخه‌ی Flet)
# هر کلید با id موجود در CATEGORIES تطبیق دارد:
#   active=هیجانی، creative=خلاقانه، food=سفره، nature=طبیعت، home=خانگی
# هر تگ: (متن، رنگ پس‌زمینه RGBA، رنگ متن RGBA)
# ---------------------------------------------------------------------------
TAG_EXCITING = ("هیجانی", (0.992, 0.910, 0.878, 1), (0.753, 0.251, 0.125, 1))
TAG_SPORT    = ("ورزشی",  (0.992, 0.910, 0.878, 1), (0.753, 0.251, 0.125, 1))
TAG_CALM     = ("آرامش‌بخش", (0.898, 0.961, 0.918, 1), (0.180, 0.478, 0.314, 1))
TAG_COMPETE  = ("رقابتی", (0.992, 0.910, 0.878, 1), (0.753, 0.251, 0.125, 1))
TAG_DUO      = ("دونفره", (0.961, 0.898, 0.961, 1), (0.478, 0.188, 0.565, 1))
TAG_ART      = ("هنری",   (0.961, 0.898, 0.961, 1), (0.478, 0.188, 0.565, 1))
TAG_CREATIVE = ("خلاقانه",(0.961, 0.898, 0.961, 1), (0.478, 0.188, 0.565, 1))
TAG_ROMANTIC = ("رمانتیک",(0.992, 0.910, 0.878, 1), (0.753, 0.251, 0.125, 1))
TAG_ADVENT   = ("ماجراجویانه", (0.992, 0.910, 0.878, 1), (0.753, 0.251, 0.125, 1))

def _t_time(txt): return (txt, (0.929, 0.949, 1.0, 1), (0.251, 0.376, 0.690, 1))
def _t_cost(txt): return (txt, (1.0, 0.976, 0.902, 1), (0.565, 0.376, 0.125, 1))

# ---- تگ‌های بازه‌ی سنی (به هر ایده اضافه می‌شه تا کاربر بدونه ایده مال چه سنیه) ----
TAG_AGE_15_20 = ("۱۵ تا ۲۰ سال", (0.86, 0.95, 0.88, 1), (0.18, 0.49, 0.20, 1))
TAG_AGE_20_25 = ("۲۰ تا ۲۵ سال", (0.86, 0.93, 1.00, 1), (0.10, 0.40, 0.78, 1))
TAG_AGE_25_30 = ("۲۵ تا ۳۰ سال", (1.00, 0.91, 0.78, 1), (0.68, 0.38, 0.05, 1))
TAG_AGE_30_35 = ("۳۰ تا ۳۵ سال", (0.96, 0.86, 0.95, 1), (0.55, 0.10, 0.45, 1))
TAG_AGE_20_PLUS = ("از ۲۰ سال به بالا", (0.92, 0.90, 0.99, 1), (0.30, 0.20, 0.65, 1))

def _tag_ideas(ideas, age_tag):
    """یک کپی از هر ایده می‌سازه و تگ بازه‌ی سنی رو بهش اضافه می‌کنه."""
    out = []
    for it in ideas:
        new = dict(it)
        new["tags"] = list(it.get("tags", [])) + [age_tag]
        out.append(new)
    return out


# ---------------------------------------------------------------------------
# ایده‌های «هیجانی و فعال» بر اساس بازه‌ی سنی کاربر
# هر بازه، علاوه بر ایده‌های بازه‌های قبلی، ایده‌های اختصاصی خودش رو هم داره.
# ---------------------------------------------------------------------------
ACTIVE_15_20 = [
    {"title": "اتاق فرار (Escape Room)",
     "desc": "با هم معما حل کنید و قبل از اتمام وقت راه فرار رو پیدا کنید. عالی برای کار تیمی! قبلش با هم یک تم انتخاب کنید (جنایی، فانتزی، ترسناک) و توافق کنید که در حل معماها هر کدوم روی یه چیز تمرکز کنید تا سرعت‌تون بره بالا و کل تجربه یه بازی گروهیِ واقعی بشه، نه یه رقابت خشک.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_EXCITING, _t_time("۱.۵ ساعت"), _t_cost("متوسط")]},
    {"title": "کارتینگ و پینت‌بال",
     "desc": "یه روز پر آدرنالین با سرعت و رقابت دوستانه. خنده و هیجان تضمینی. قبل از شروع یه شرط‌بندی کوچیک بذارید — بازنده باید هزینه‌ی شام یا بستنیِ بعدش رو حساب کنه — تا انگیزه‌ی رقابت و خنده چند برابر بشه و بعدِ بازی هم یه ادامه‌ی خوش‌مزه داشته باشید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_EXCITING, TAG_COMPETE, _t_cost("متوسط")]},
    {"title": "دوچرخه‌سواری یا اسکیت دونفره",
     "desc": "یه مسیر دلخواه بچینید، هدفون بذارید و کنار هم رکاب بزنید یا اسکیت کنید. قبلش یه مسیر حلقه‌ای انتخاب کنید که وسطش یه کافه یا نیمکت باشه، تا وسط رکاب زدن یه توقف کوتاه برای نوشیدنی خنک و عکس‌گرفتن داشته باشید و مسیر فقط ورزش نباشه.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_SPORT, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "شهربازی (سانس شب)",
     "desc": "چراغ‌های رنگی، ترن هوایی و جیغ‌های خنده‌دار. شب شهربازی یه جور جادو داره. سعی کنید حتماً چرخ و فلک رو آخرِ همه سوار بشید؛ وقتی چراغ‌های شهر از بالا برق می‌زنن و نور رنگیِ ترن‌ها هنوز کنارتونه، اون چند دقیقه‌ی آروم می‌شه یکی از رمانتیک‌ترین قسمتای شب.",
     "border": (0.345, 0.537, 0.800, 1), "fav": True,
     "tags": [TAG_EXCITING, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    {"title": "صخره‌نوردی / بولدرینگ",
     "desc": "یه تجربه‌ی جدید که به اعتماد و کمک همدیگه نیاز داره. تنِ آدم گرم می‌شه. حتماً یه مربی کنارتون باشه و کفش و طناب استاندارد قرض بگیرید. نکته‌ی جذابش اینه که وقتی یکی‌تون از دیوار بالا می‌ره، اون یکی از پایین راهنمایی می‌کنه و همین گفت‌وگو کلی اعتماد بین‌تون می‌سازه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_SPORT, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "عکاسی از هم",
     "desc": "هر کدوم یه ساعت عکاسِ اون یکی باشید. آخرش یه گالری کوچیک دونفره دارید. یه تم مشخص انتخاب کنید (مثلاً «سکوت»، «رنگ زرد»، «خنده») و در طول ساعت‌تون فقط با همون تم عکس بگیرید؛ در آخر مجموعه‌ای دارید که واقعاً حس و روحیه‌ی همدیگه رو حکایت می‌کنه.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "دیتِ سکون (The Slow Date)",
     "desc": "برید کتابخونه‌ی ملی یا یه موزه‌ی خلوت. یه ساعت حق ندارید حرف بزنید؛ فقط نگاه و یادداشت. دفترچه و مداد ببرید و در آن یک ساعتِ بی‌کلام، هر چیزی که دیدید و توجه‌تون رو جلب کرد بنویسید یا اسکچ بزنید؛ آخر جلسه دفترچه‌هاتون رو با هم عوض کنید و کشف کنید هر کدوم چی دیده.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, _t_time("۱ ساعت+"), _t_cost("رایگان")]},
    {"title": "سینما ماشین / سینمای نیمه‌شب",
     "desc": "لپ‌تاپ، پتو، چیپس و پفک. ماشین رو یه جای دنج پارک کنید و فیلم خفن ببینید. قبلش با هم لیست کوتاهی از سه فیلم بسازید و رأی‌گیری کنید، تا انتخاب فیلم خودش تبدیل به یه بازیِ کوچیک بشه. آجیل و ترموس چای هم فراموش نشه.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "منتقد هنری در گالری",
     "desc": "برید گالری مستقل یا شو‌روم مبل وینتیج. نقش دو منتقدِ سرسخت رو بازی کنید. در نقش منتقد، بعد از هر اثر بین ۳۰ ثانیه تا یک دقیقه تحلیل تخیلی و مبالغه‌آمیز بدید (حتی اگه بی‌سواد باشید نسبت به هنر) — این بازی هم خنده‌داره هم بی‌سر و صدا بهتون یاد می‌ده به جزئیات هنر دقت کنید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "خرید متقابل کتاب",
     "desc": "هر کدوم یواشکی یه کتاب برای روحیه‌ی اون یکی بخرید و کادو کنید. قانونش این باشه که کتاب رو نباید بر اساس علاقه‌ی خودتون انتخاب کنید، بلکه بر اساس چیزی که فکر می‌کنید طرفِ مقابل الان بهش نیاز داره؛ در پشت جلد هم یه یادداشت کوتاه دست‌نویس بذارید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "چالش خوراکی شانسی",
     "desc": "هایپرمارکت، چشم بسته، با راهنماییِ طرف مقابل یه خوراکی شانسی بردارید و با هم بخورید! هرکس فقط بودجه‌ی محدود مثلاً پنجاه هزار تومنی داره و بعد از خرید، در ماشین یا روی یه نیمکت با چشم بسته اولین گاز رو می‌زنید و باید فقط با طعم حدس بزنید طرف چی خریده.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ADVENT, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "یادگاریِ دست‌ساز",
     "desc": "پیاده‌روی کنید و یه یادگاریِ رایگان (برگ، سنگ، حلقه‌ی علف) برای هم پیدا کنید. می‌تونید در انتها یه جعبه‌ی چوبی یا شیشه‌ای کوچیک بردارید و یادگاری‌ها رو با تاریخ همون روز درش بذارید تا هر بار که بازش می‌کنید عطر و حس اون پیاده‌روی برگرده.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CREATIVE, TAG_CALM, _t_cost("رایگان")]},
    {"title": "پلی‌لیست مشترک و قدم‌زنی",
     "desc": "یه فیش دو کاناله یا هر کدوم یه ایرپاد. یه مسیر قشنگ، بدون حرف، فقط موزیک. قبل از شروع، هر کدوم پنج آهنگ اضافه کنید و شرط این باشه که در طول قدم زدن نه کسی رد کنه و نه ولوم رو کم — این‌جوری با موزیک همدیگه هم آشنا می‌شید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت+"), _t_cost("رایگان")]},
    {"title": "کاستومایز کردن یه آیتم ساده",
     "desc": "دو تا ماگ سفید یا قاب گوشی بی‌رنگ بخرید و با ماژیک ضدآب برای هم نقاشی کنید. قانون شوخِ کار اینه که تا آخر نباید طرح خودتون رو نشون بدید؛ در آخر هم‌زمان رو کنید و اون که خنده‌دارتر یا تمیزتر شده جایزه‌ی کوچیکی می‌گیره — مثلاً یه بستنی بعدش.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("ارزان")]},
    {"title": "گم شدنِ انتخابی با سکه",
     "desc": "سر هر چهارراه سکه بندازید: شیر راست، خط چپ. ببینید به کدوم کافه‌ی پنهان می‌رسید. قانون بازی این باشه که تنها یک نجات (Life) دارید: یک بار در کل مسیر می‌تونید سکه رو نادیده بگیرید و مسیرِ خودتون رو انتخاب کنید؛ بقیه‌اش رو باید به شانس بسپرید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ADVENT, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "دیتِ «یادش بخیر»",
     "desc": "پفک حلقه‌ای، شکلات سیگاری، نوشمک. روی نیمکت پارک از سوتی‌های بچگی بگید. قبلش هر کدوم یه لیست ۵تایی از خوراکی‌های بچگی‌تون بنویسید و در دیت با هم مقایسه‌شون کنید؛ خواهید دید چقدر آدم‌ها با اسم یه شکلاتِ ساده به دورانِ عجیبی از ذهن‌شون پرت می‌شن.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CALM, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "سفر تا آخرین ایستگاه",
     "desc": "سوار یه خط اتوبوس یا مترو که نرفتید بشید و تا آخرین ایستگاه برید کشف کنید. در طول مسیر قانون این باشه که در هر ایستگاه یه چیز جدید در مورد طرف مقابل کشف کنید — یه سؤالی که هرگز نپرسیده بودید. وقتی رسیدید انتها، برای برگشت با تاکسی برنگردید؛ همون خط رو دوباره سوار بشید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "کتاب‌گردی و فالِ صفحه‌ای",
     "desc": "تو راسته‌ی کتاب‌فروش‌ها چشم‌بسته یه کتاب بردارید و یه صفحه به نیت دیت بخونید. قبل از باز کردن کتاب، یه سؤالِ واقعی از زندگی‌تون در دل بگیرید و بعد صفحه رو باز کنید و اولین جمله‌ی چشمِ چپ رو بلند بخونید؛ حتی اگه به سؤال ربطی نداشته باشه، تفسیرش خودش کلی مکالمه می‌سازه.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ART, _t_time("۱ ساعت"), _t_cost("رایگان")]},
]

ACTIVE_20_25_EXTRA = [
    {"title": "تیراندازی یا تیر و کمان",
     "desc": "باشگاه تیراندازی برید؛ یاد گرفتن یه مهارت جدید کنار هم با رقابتی شیک و پر تمرکز. قبلش با مربی یه راند تمرینی برید و بعدش خط شرطی رو بذارید: هر تیرِ ده‌امتیازی معادل یک جواب صادقانه به یک سؤالِ سختیه که پارتنر می‌پرسه.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_COMPETE, TAG_SPORT, _t_cost("متوسط")]},
    {"title": "امتحان یه ورزش جدید",
     "desc": "بدمینتون، اسکواش، تنیس یا هر چیزی که تا حالا نکردید. اولین تجربه با هم! تنها قانونش این باشه که هیچ‌کدوم قبلش سرچ نکنه یا آموزش نبینه، تا هر دو در یه سطحِ ناشیانه‌ی خنده‌دار شروع کنید و کل تجربه با کلی سوتی و عکس گرفتن پیش بره.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_cost("متوسط")]},
    {"title": "چالش لباس پرو برای مهمونی خیالی",
     "desc": "پاساژ شیک. برای هم ریسکی‌ترین استایل رو انتخاب کنید، پرو کنید و عکس بگیرید. یه سناریوی مهمونی خیالی بسازید (مثلاً «افتتاحیه‌ی هنری در پاریس») و بر اساسِ همون تم، طرف مقابل باید لباس‌های ریسکی انتخاب کنه. پرو کردن‌ها رو حتماً با یه ژست خنده‌دار عکس بگیرید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "ساندویچ کثیفِ ساعت ۱ بامداد",
     "desc": "ولوم رپ یا متال بالا، فلافل و بندریِ شبانه روی کاپوت ماشین. بی‌خیال کثیف شدن! قسم بخورید که تا آخر شب اسنپ یا تپسی نمی‌گیرید و اگه ماشین کارت شارژ نداشت، پیاده تا نزدیک‌ترین ساندویچی می‌رید. کل ماجرا در نبود پرستیژ اجرا می‌شه.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "شکار گرافیتی‌های پنهان",
     "desc": "کوچه‌های پشت پاساژها و دیوارهای حاشیه‌ی اتوبان. عکاسی استریت و کژوال. قبلش یه لیست از پنج ادعای هنری در ذهن‌تون داشته باشید («خشم»، «تنهایی»، «شادی»، «طنز»، «سیاسی») و برای هر گرافیتیِ پیداکرده رأی بدید کدوم دسته‌بندی بهش می‌خوره؛ در انتها یه کلاژِ عکسی از کارها بسازید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, _t_time("۳ ساعت"), _t_cost("رایگان")]},
    {"title": "سفر در زمان با مجلات قدیمی",
     "desc": "دکه‌ی روزنامه‌ی قدیمی یا دست‌دوم‌فروشی. مجله‌ی نایاب پیدا کنید و قاب کنید. مجله‌ای پیدا کنید که به دهه‌ی تولد یکی از شماها برگرده. کنار قهوه بشینید و آگهی‌ها، سرمقاله‌ها و جدولش رو با هم بخونید — عجیبه که چقدر لحن نوشتاری اون زمان با حالا فرق داره.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "لانژ بالای شهر و چراغ‌های شب",
     "desc": "بام‌های دنج یا تراس‌های رو به شهر. جاز ملایم و تماشای حرکت چراغ‌ها. یه ماک‌تیل انتخاب کنید که هر دو تا حالا نچشیده باشید و بازیِ این باشه که بعد از هر جرعه، یه چیزی درباره‌ی شهر که پایین‌تون هست و هرگز به هم نگفته بودید بگید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    {"title": "کشفِ کتاب‌فروشی دست‌دوم",
     "desc": "راسته‌ی کتاب‌فروش‌های قدیمی، حراجی‌ها. دنبال یه نسخه‌ی نایاب بگردید. قبل از رفتن، هر کدوم اسم یه نویسنده رو مخفی روی کاغذ بنویسید و شرطش این باشه که تا آخر روز حتماً یه کتاب از اون نویسنده در راسته پیدا کنید — این جستجو خودش تبدیل به یه ماجراجویی می‌شه.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "پادکست در جاده‌ی شبانه",
     "desc": "اتوبان خلوت، یه پادکست جنایی/تاریخی. آخرش کلی بحث و تحلیل دارید. قبل از شنیدن، هر کدوم یه پیش‌بینی درباره‌ی پایان قصه بنویسه و بره در داشبورد بذاره؛ در انتهای پادکست بازش کنید و ببینید کدوم‌تون بیشتر به واقعیت نزدیک بوده.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, TAG_ADVENT, _t_cost("ارزان")]},
    {"title": "توریستِ ناشناس در شهر خودت",
     "desc": "وانمود کنید مسافرید؛ دوربین گردن، استایل توریستی و کشفِ جاهای کلیشه‌ایِ شهر. واقعاً از یه توریست بپرسید «what's a must-see here?» و بر اساس جوابش برنامه بچینید. لهجه‌ی توریستی صحبت کنید و از پلیس آدرس بپرسید — کل روز شبیه یه فیلم کمدی می‌شه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, TAG_ADVENT, _t_time("۴ ساعت")]},
]

ACTIVE_25_30_EXTRA = [
    {"title": "اسپا و ماساژ دونفره",
     "desc": "یه ساعت ماساژ ریلکسی با نور ملایم و عود. ریست کاملِ هفته‌ی کاری. قبلش گوشی‌ها رو در قفسه‌ی ورودی بذارید تحویل بگیرید و شرط این باشه که تا آخرِ سانس کسی به گوشی دست نمی‌زنه — این بخشِ ساده در واقع سخت‌ترین بخشِ دیته.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_CALM, TAG_ROMANTIC, _t_cost("گران")]},
    {"title": "کمپینگ پرمیوم (Glamping)",
     "desc": "یه شب کلبه‌ی چوبیِ مدرن. گوشی‌ها تو سبد دربسته. آتیش، ستاره و گفتگو. یه آیین شبانه بذارید: قبل از خواب، هر کدوم یه چیزی از سالِ گذشته که ازش سپاسگزارید و یه چیزی که براش تلاش می‌کنید بگید. اون تاریکی و صدای طبیعت باعث می‌شه حرفا خیلی صادقانه‌تر در بیاد.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ADVENT, _t_time("۱ شب"), _t_cost("گران")]},
    {"title": "کلبه‌نشینی در طبیعت",
     "desc": "سوئیت دنج حاشیه‌ی روستا. کباب، صدای طبیعت، بدون حواس‌پرتیِ دیجیتال. صبح که بیدار شدید، بدون گوشی و بدون ساعت، فقط با نور خورشید صبحونه بخورید و بعد یه پیاده‌رویِ کوتاه به یه نقطه‌ی بی‌اسم برید — همون جایی که هیچ نقشه‌ای نشونش نمی‌ده.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, _t_time("۱ شب"), _t_cost("متوسط")]},
]

ACTIVE_30_35_EXTRA = [
    {"title": "شبِ وینیل و گرامافون",
     "desc": "کافه‌ای با آرشیو صفحه‌های قدیمی پیدا کنید. جاز، بلوز و گفتگوهای عمیق. یه دهه رو انتخاب کنید (مثلاً ۷۰) و فقط صفحه‌های همون دهه رو بشنوید. هر آهنگ رو تا آخر گوش بدید — این تجربه‌ای‌ست که در شرایط اسپاتیفای/شافل ازش محرومید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("متوسط")]},
    {"title": "گالری مبل، دیزاین و عتیقه",
     "desc": "شو‌روم‌های دیزاین داخلی. بین خطوط مدرن و عتیقه‌ها از سلیقه‌ی آینده‌تون بگید. قانون بازی این باشه که هر کدوم باید یه تیکه انتخاب کنه که فکر می‌کنه پارتنر بعدها می‌خرتش، و در پایانِ روز رأی‌ها رو رو کنید — کشفِ سلیقه‌ی همدیگه از این بازیِ ساده در میاد.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("رایگان")]},
    {"title": "ورکشاپ خصوصی باریستا",
     "desc": "یه سانس خلوت با باریستای حرفه‌ای. دم‌آوریِ موج سوم یا ساختن ماک‌تیل. اجازه بدید باریستا یه دم‌آوریِ V60 یا Aeropress نشون بده و بعد شما هم امتحان کنید. مقایسه‌ی دم‌آوریِ خودتون با نمونه‌ی باریستا خودش نصف لذت این تجربه‌ست.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("متوسط")]},
    {"title": "گلخانه‌ی استوایی و باغبانی",
     "desc": "گلخانه‌ی مسقفِ خارج شهر. یه گلدون کمیاب بخرید که مسئولیتش با هردوتونه. قبل از خرید، برای گیاه یه اسم انتخاب کنید و توافق کنید یه دفترچه‌ی مراقبت نگه دارید که هر کدوم به نوبت آبیاری و رشد گیاه رو در اون ثبت کنید.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "ساعت ۶ صبح در سکوت طبیعت",
     "desc": "قبل از بیدار شدن شهر بزنید به جاده. املتِ هیزمی، چای آتیشی، سکوت مطلق. قبلش شب رو هر دو زود بخوابید، آلارم رو یه ساعت قبل از طلوع تنظیم کنید و در جاده حرف نزنید — بعضی صبح‌ها فقط با سکوت زیبا می‌شن.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, _t_time("۴ ساعت"), _t_cost("ارزان")]},
    {"title": "اتاق نمک یا اسپا تعاملی",
     "desc": "یه سانس خصوصیِ اتاق نمک. اکسیژن خالص، نور ملایم و ریستِ کاملِ مغز. چون در اتاق نمک نمی‌شه با گوشی وارد شد، از قبل تصمیم بگیرید در اون ۴۵ دقیقه فقط تنفس عمیق کنید یا در ذهن‌تون به یه سؤال فکر کنید — بعدش جواب‌ها رو با هم مقایسه کنید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CALM, _t_time("۱ ساعت"), _t_cost("گران")]},
]


# ---------------------------------------------------------------------------
# ایده‌های «خلاقانه و هنری» بر اساس بازه‌ی سنی کاربر (تجمعی، عین «هیجانی و فعال»)
# ---------------------------------------------------------------------------
CREATIVE_15_20 = [
    {"title": "بوم مشترک تو پارک",
     "desc": "یه بوم متوسط، چند رنگ گواش و دو قلم‌مو؛ پارک دنج. نوبتی روی بوم خط بزنید تا یه تابلوی دو نفره‌ی بامزه خلق بشه. قانون این باشه که هر کدوم فقط سی ثانیه فرصت داره روی بوم کار کنه و بعد جای خودش رو با پارتنر عوض کنه — همین محدودیت زمانی باعث می‌شه هیچ‌کدوم نتونید کنترلِ کامل تابلو رو بگیرید و نتیجه واقعاً مشترک بشه.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "چالش دوربین یک‌بارمصرف",
     "desc": "یه پولاروید یا دوربین آنالوگ بگیرید؛ کلاً ۱۲ شات. تو محله‌ی قدیمی یا بازارچه از هم خفن‌ترین فریم‌ها رو شکار کنید. قانونش این باشه که فقط شش تا از دوازده شات رو خودتون بگیرید و بقیه رو باید از عابرها بخواید. تنوعِ نگاهِ آدم‌های دیگه به شما فوق‌العاده جالب می‌شه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "کافه‌ی سفال یا موزاییک",
     "desc": "تو کافه‌های متریال‌دار، هر کدوم یه ماگ سفالی برای اون یکی رنگ کنید؛ تا آخر کار طرح همدیگه رو نبینید! در طول ساعت‌های کار، یه پارتیشنِ ساده (مثلاً یه دستمال) بین‌تون بذارید تا هیچ‌کدوم کار طرف مقابل رو نبینه؛ لحظه‌ی رونمایی در انتها بهترین قسمت شبه.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "کلاژ ژورنال در کافه",
     "desc": "دفترچه‌ی کرافت + مجله‌های قدیمی + چسب و قیچی. عکس و کلمه‌هایی که یاد همدیگه می‌اندازتتون رو بچسبونید. برای هر صفحه یه احساس (مثلاً «امید»، «دلتنگی»، «شور») در نظر بگیرید و بعد فقط تصاویری بچسبونید که به اون حس نزدیکه — کلاژ در نهایت تبدیل به یه دفتر خاطراتِ تصویریِ مشترک می‌شه.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, TAG_CALM, _t_cost("ارزان")]},
    {"title": "ساخت دستبند و پین",
     "desc": "خرازی برید؛ نخ، مهره، خمیر هوا‌خشک. برای هم دستبند ست یا پین مگنتیِ بامزه بسازید و رنگ کنید. با هم شرط ببندید که بدون نگاه کردن به گوگل، فقط با ذوق خودتون بسازید. حروف اول اسم یا یه علامت شخصی (مثل یه ستاره‌ی کوچک) رو داخل طرح جاسازی کنید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "تای‌دایِ لباس قدیمی",
     "desc": "تیشرت یا هودی سفیدِ قدیمی + رنگ پارچه. با گره زدن و ریختن رنگ، طرحِ مارپیچ و رنگین‌کمونی خفن بسازید. قبلش دستکش پلاستیکی و یه سفره‌ی نایلونی آماده کنید تا وسط دیت درگیر تمیزکاری نشید. برای هر لباس دو تا سه رنگ استفاده کنید و برای گرهش از کش استفاده کنید تا مارپیچ تمیزتری در بیاد.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, TAG_ART, _t_cost("ارزان")]},
    {"title": "پلی‌لیست کپسول زمان",
     "desc": "وویس‌رکوردِ گوشی رو روشن کنید؛ از هم سوال‌های جالب بپرسید. بعدش یه پلی‌لیست مشترک از آهنگ‌های خاطره‌ساز بسازید. سؤال‌ها رو از قبل هر کدوم روی کاغذ بنویسید و در یه کاسه بریزید؛ به‌ نوبت از کاسه بردارید تا کسی نتونه سؤالِ راحت انتخاب کنه. فایل صوتی نهایی رو با یه اسم و تاریخ روی گوشی هر دوتون ذخیره کنید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("رایگان")]},
    {"title": "ساخت تراریوم کوچک",
     "desc": "یه شیشه‌ی مربای تمیز، خاک، سنگ‌ریزه‌ی رنگی و چند ساکولنت. باغ مینیاتوری دو نفره بکارید و تزیین کنید. ترتیبِ لایه‌ها مهمه: پایین سنگ‌ریزه‌ی درشت برای زهکشی، بعد یک لایه‌ی نازک کربن فعال، بعد خاک، و بعد ساکولنت‌ها. در آخر دو تا سه سنگ تزئینی و یه فیگورِ کوچیک بذارید تا داستان تراریوم رو کامل کنه.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("ارزان")]},
    {"title": "قابِ گل خشک‌شده",
     "desc": "تو پیاده‌روی گل‌های وحشی و برگ‌های پاییزی جمع کنید؛ بین دو شیشه‌ی یه قاب عکس بچینید و قاب کنید. گل‌ها رو حداقل دو روز قبل بین صفحات یه کتاب سنگین بذارید تا کاملاً پرس و خشک بشن. موقع چسبوندن از چسب مایعِ خیلی کم استفاده کنید تا از پشت شیشه دیده نشه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_ROMANTIC, _t_cost("ارزان")]},
    {"title": "بازسازی اولین دیت",
     "desc": "همون کافه، همون لباس، همون سفارش. خاطرات اون روز رو مرور کنید و دقیقاً تو همون زاویه یه عکس جدید بگیرید. قبلش دقیق یادداشت کنید که اون روز چه لباسی، چه سفارشی، چه ساعتی و در چه صحبتی بودید — بعد بازسازی رو حتی‌الامکان به همون شکل انجام بدید. عکس رو دقیقاً از همون زاویه‌ی اول ثبت کنید و کنار عکس اول قاب کنید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "تست کورکورانه‌ی طعم‌ها",
     "desc": "چشم‌های هم رو ببندید و تکه‌های پنیر، شکلات، میوه یا سس مختلف بدید بچشه و حدس بزنه. خنده تضمینی! برای هیجانِ بیشتر، بعضی از تکه‌ها رو تعمداً «فِیک» بذارید (مثلاً پنیرِ گیاهی به جای پنیر معمولی) و ببینید طرف چقدر تشخیص می‌ده. هر خطا معادل یه امتیازِ خنده‌داره.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
]

CREATIVE_20_25_EXTRA = [
    {"title": "بُرد چوبی مزه (شارکوتری)",
     "desc": "یه تخته‌ی چوبی + پنیر، انگور، کراکر، شکلات تلخ. هدف فقط چیدمانِ پینترستیه؛ هنرِ ترکیب رنگ و بافت. قانون چیدمانِ حرفه‌ای اینه که رنگ‌ها رو کنار هم متضاد بذارید (زردِ پنیرِ چدار کنار قرمزِ گوجه، سفیدِ موزارلا کنار سیاهِ زیتون). قبل از سرو، تخته رو ۳۰ دقیقه تحویلِ دمای اتاق بدید تا طعم پنیرها آزاد بشه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("متوسط")]},
    {"title": "ورک‌شاپ تافتینگ",
     "desc": "با تفنگِ کاموا روی بوم پارچه‌ای، یه دیوارکوبِ پشمیِ نرم با طرح کاراکتر یا قلب بسازید. ترندِ خفن. قبل از رفتن، یه اسکچِ ساده از طرحی که می‌خواید (قلب، اسم، شکل حیوان) روی گوشی داشته باشید. رنگ‌های کاموا رو حداکثر سه‌تا انتخاب کنید تا نتیجه تمیز در بیاد و بعد از تکمیل، پشتش رو با چسبِ پارچه سیل کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("گران")]},
    {"title": "عکاسی از فضاهای متروکه",
     "desc": "کاروانسرا یا عمارتِ تاریخیِ خلوت. با بازیِ نور و سایه از هم پرتره‌های هنری و نوستالژیک ثبت کنید. حتماً کفشِ راحت بپوشید، چراغ‌قوه ببرید و اجازه‌ی ورود رو از قبل چک کنید. برای پرتره‌ها از نور طبیعی که از پنجره‌ی شکسته می‌آد استفاده کنید — کنتراستِ نور و سایه در این فضاها هدیه‌ی رایگانِ عکاسیه.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ART, _t_time("۳ ساعت"), _t_cost("رایگان")]},
    {"title": "خرید لباس وینتیج برای هم",
     "desc": "سه‌شنبه‌بازار یا تاناکورا. ۳۰ دقیقه و بودجه‌ی محدود؛ بهترین اوت‌فیتِ پینترستی رو برای پارتنرت انتخاب کن. قانون کار اینه که پارتنر باید همون لباس رو در مغازه پرو کنه و بدون قضاوت، ده دقیقه در آینه راه بره. حتی اگه در نهایت نخرید، تجربه‌اش خودش کلی خنده و کشف داره.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, TAG_ADVENT, _t_cost("متوسط")]},
    {"title": "ساخت عطر اختصاصی دو نفره",
     "desc": "کارگاهی که اسانس‌ها (وانیل، چوب، رز، مرکبات) رو خودت ترکیب می‌کنی. یه فرمول کاملاً مخصوصِ خودتون. قبل از تصمیم نهایی، در طول کارگاه بین نُت‌های بالا (مرکبات و ادویه‌های سبک)، میانه (گل و ادویه) و پایه (چوب، مشک، وانیل) توازن ایجاد کنید. اسم عطر باید یه واژه‌ی ساخته‌ی هردوی‌تون باشه که در هیچ‌کجای دنیا معنی نده.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("گران")]},
    {"title": "تفسیر شعر و موسیقی وینتیج",
     "desc": "اسپیکر باکیفیت + آلبوم‌های جاز یا کلاسیک. کتاب حافظ یا شاملو بردارید و نوبتی برای هم بخونید. برای هر شعری که خوندید، بعدش سکوت بذارید — سی ثانیه هیچ‌کدوم حرف نزنید تا شعر ته‌نشین بشه. بعد نظر بدید. این سکوت‌ها بخشی از تجربه‌ست.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("رایگان")]},
    {"title": "سینماکلوپ خانگی با تمِ کارگردان",
     "desc": "یه کارگردانِ سبک‌دار (نولان، تارانتینو، وس اندرسون) انتخاب؛ اتاق رو هم‌تم کنید، بعد فیلم تحلیل کنید. قبل از شب، پروفایلِ کارگردان رو مرور کنید (پنج فیلم اصلی، سبک نور، امضاهای بصری) و بعد در حین دیدن بازیِ «شکار امضا» بگذارید — هر کس اول نشانه‌ی کارگردان رو دید، امتیاز می‌گیره.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "نقاشی روی شیشه (ویترای)",
     "desc": "ورق شیشه + دورگیر مشکی + رنگ ویترای شفاف. یه پنجره‌ی رنگیِ کوچیک بسازید که با عبور نور برقصه. قبلش طرح روی کاغذ بکشید و بعد شیشه رو روش بذارید تا از پشت خطوط رو کپی کنید. برای دورگیری از تیوپِ کانتور استفاده کنید و منتظر بمونید کاملاً خشک بشه، بعد رنگ‌ها رو پر کنید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
]

CREATIVE_25_30_EXTRA = [
    {"title": "تست قهوه‌ی تخصصی (Cupping)",
     "desc": "کافه‌ی موج سوم با رویداد کاپینگ. عطر، اسیدیته و نت‌های طعمیِ قهوه‌های مختلف رو یاد بگیرید تشخیص بدید. در جلسه‌ی کاپینگ سعی کنید حداقل سه اوریجینِ متفاوت (اتیوپی، برزیل، کلمبیا) رو کنار هم بچشید تا تفاوت‌های اسیدیته و بادی رو حس کنید. یه دفترچه ببرید و برای هر قهوه سه واژه‌ی توصیفی بنویسید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "ورک‌شاپ تراریوم بزرگ یا موس‌وال",
     "desc": "یه اکوسیستمِ بسته‌ی شیشه‌ای یا تابلوی خزه‌ایِ حرفه‌ای بسازید؛ یه اثر هنریِ زنده برای خونه. موس‌وال طوری طراحی می‌شه که سایه‌های خزه و اسپاگنوم مثل تپه‌های کوچیک از دیوار بزنه بیرون. قبل از شروع در ذهن‌تون یه چشم‌انداز طبیعی رو تصور کنید (مثلاً جنگل بارونی) و ازش الهام بگیرید.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_CREATIVE, TAG_ART, _t_cost("گران")]},
    {"title": "تئاتر مستقل یا اجرای فرم",
     "desc": "یه تئاتر تجربی یا نمایشگاهِ مفهومی. شیک لباس بپوشید و بعدش لایه‌های زیرینِ اثر رو با هم نقد کنید. بعد از اجرا، به‌جای بحث در همون سالن، به یه کافه‌ی نزدیک برید و در قالب یه بازی نوبتی، سه چیز که فهمیدید و یه چیز که هنوز براتون مبهمه رو با هم به اشتراک بذارید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    {"title": "آشپزی بین‌المللی با مواد ناشناخته",
     "desc": "یه غذای هندی/مکزیکی/فرانسوی انتخاب؛ ادویه‌های جدید بخرید، موسیقیِ همون کشور بذارید و بپزید. برای اصالت بیشتر، حتی ظرفِ سرو رو هم متناسبِ فرهنگ انتخاب کنید — مثلاً برای غذای هندی از ظروف مسی، برای مکزیکی از سرامیک رنگی. حالا انگار واقعاً در یه کوچه‌ی خارجی نشستید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, TAG_ADVENT, _t_cost("متوسط")]},
    {"title": "شبِ طراحی ویژن‌برد",
     "desc": "یه بُرد چوب‌پنبه‌ای + پرینتر و مجلات. تصاویرِ خونه‌ی رویایی، سفرها و اهدافِ مشترک رو بچسبونید. بورد رو به سه بخش تقسیم کنید: «یک سال آینده»، «پنج سال آینده»، «رویاهای دور». هر بخش رنگ زمینه‌ی متفاوتی داشته باشه. بعد از تکمیل، بورد رو یه جای دیدنی بذارید تا هر روز ببینیدش.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("ارزان")]},
    {"title": "کارگاهِ اکسسوریِ چرم",
     "desc": "اصولِ برش و دوختِ چرم رو یاد بگیرید. برای هم جاکارتی یا جلد پاسپورت با حروف اول اسمِ همدیگه بسازید. چرم گیاهی (Veg Tan) رو انتخاب کنید که با گذشتِ زمان رنگش عمیق‌تر می‌شه. برای دوخت از تکنیک Saddle Stitch با دو سوزن استفاده کنید — این دوخت به‌عمداً کندتره ولی محکم‌تر از هر ماشین‌دوزیه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "کارگاهِ پختِ نان حجیم",
     "desc": "سوردو، باگتِ فرانسوی یا فوکاچیا. رویِ فوکاچیا رو با سبزیجات و گوجه مثل یه تابلوی نقاشی تزیین کنید. سوردو حداقل ۲۴ ساعت زمانِ تخمیر می‌خواد؛ اگه سرِ کلاس رفتید، از استاد استارتر رو با خودتون خونه ببرید و پرورشش رو ادامه بدید تا در خونه هم بشه بار دوم بپزید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
]

CREATIVE_30_35_EXTRA = [
    {"title": "پینت‌اند‌سیپ (Paint & Sip)",
     "desc": "دو بومِ نقاشی + اکریلیک + موکتیل‌های دست‌ساز. جازِ ملایم پخش کنید و بدون مهارتِ خاصی فقط رنگ بپاشید. مربی معمولاً یه اثر رفرنس (مثلاً «شب پرستاره‌ی» ون‌گوگ) رو گام‌به‌گام آموزش می‌ده. سعی کنید تعمداً به تابلوی خودتون سبک شخصی اضافه کنید تا در انتها دو تابلوی متفاوت داشته باشید.",
     "border": (0.608, 0.427, 0.816, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("متوسط")]},
    {"title": "شب‌نشینیِ گالریِ شبانه",
     "desc": "افتتاحیه‌ی گالری‌های بزرگ یا حراجی آثار هنری. لباسِ نیمه‌رسمی، قدم زدن بینِ آثار و گفت‌وگوی فرهنگی. قبل از رفتن، در سایت گالری اسم‌های هنرمندان رو ببینید و بعد یه بازی بذارید: باید حدس بزنید کدوم اثر متعلق به کدوم هنرمنده. تفاوتِ سبک‌ها این‌جوری برای‌تون قابلِ لمس می‌شه.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ART, _t_time("۳ ساعت"), _t_cost("گران")]},
    {"title": "کارگاهِ جواهراتِ ظریف",
     "desc": "نقره/برنج رو با راهنماییِ استادکار ببُرید و حرارت بدید؛ برای هم یه انگشترِ مینیمال یا پلاکِ خاص بسازید. برای انگشترهای ست، حروف اول اسم همدیگه یا یه تاریخ کوچیک (مثلاً روز آشنایی) رو در داخلش حکاکی کنید تا فقط خودتون از وجودش خبر داشته باشید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("گران")]},
    {"title": "باغ‌گردیِ تخصصی + اسکچ",
     "desc": "گلخانه‌ی استوایی یا باغ گیاه‌شناسی. دفترچه ببرید و با مداد طرح‌های خطیِ ساده از برگ‌های عجیب بکشید. برای اسکچ، مداد HB و یه پاک‌کن نرم ببرید. لازم نیست کارتون عالی باشه؛ خط‌های ساده و سریع بهتر از رنگ‌آمیزیِ ناتمومه. هر برگ رو با یه عبارتِ کوتاه توصیف کنید (مثلاً «ضخیم، نرم، بوی نم»).",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_ART, _t_cost("ارزان")]},
    {"title": "سفالگری با چرخِ مدرن",
     "desc": "پشتِ چرخِ سفالگری بشینید و یه گلدون یا کاسه شکل بدید؛ تو جلساتِ بعد لعاب‌کاری کنید و توی کوره بپزید. اولین کاسه یا گلدون شما احتمالاً کج و ناقصه — اونا رو بندازید. جادو در دومین و سومین تلاش اتفاق می‌افته وقتی حس چرخِ سفال زیر انگشت‌تون آشنا می‌شه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CALM, _t_cost("متوسط")]},
]


def get_creative_ideas(age):
    """ایده‌های «خلاقانه و هنری» — همه‌ی بازه‌های سنی برای همه نمایش داده می‌شه،
    و کنار هر ایده تگ بازه‌ی سنیِ مربوطه می‌خوره."""
    return (_tag_ideas(CREATIVE_15_20, TAG_AGE_15_20)
            + _tag_ideas(CREATIVE_20_25_EXTRA, TAG_AGE_20_25)
            + _tag_ideas(CREATIVE_25_30_EXTRA, TAG_AGE_25_30)
            + _tag_ideas(CREATIVE_30_35_EXTRA, TAG_AGE_30_35))



def age_bucket(age):
    """تعیین بازه‌ی سنی کاربر: 15-20, 20-25, 25-30, 30-35"""
    try:
        a = int(age)
    except Exception:
        a = 20
    if a < 20:
        return "15_20"
    if a < 25:
        return "20_25"
    if a < 30:
        return "25_30"
    return "30_35"


def get_active_ideas(age):
    """ایده‌های «هیجانی و فعال» — همه‌ی بازه‌های سنی برای همه نمایش داده می‌شه،
    و کنار هر ایده تگ بازه‌ی سنیِ مربوطه می‌خوره."""
    return (_tag_ideas(ACTIVE_15_20, TAG_AGE_15_20)
            + _tag_ideas(ACTIVE_20_25_EXTRA, TAG_AGE_20_25)
            + _tag_ideas(ACTIVE_25_30_EXTRA, TAG_AGE_25_30)
            + _tag_ideas(ACTIVE_30_35_EXTRA, TAG_AGE_30_35))



# ---------------------------------------------------------------------------
# ایده‌های «سفره دو نفره» بر اساس بازه‌ی سنی کاربر (تجمعی)
# ---------------------------------------------------------------------------
FOOD_15_20 = [
    {"title": "چالش پیتزای خانگی با نان آماده",
     "desc": "به جای درگیر شدن با خمیر، نان‌های پیتزای آماده (یا نان پیتا) بخرید. سس کچاپ، پنیر پیتزا، پپرونی، قارچ اسلایس‌شده و ذرت را روی میز بچینید. چالش این است که هرکس باید با چیدمان مواد روی نان، یک صورتک بامزه، طرح یک حیوان یا حروف اول اسم پارتنرش را بسازد. در نهایت پیتزاها را در فر یا تابه بگذارید تا پنیر آب شود و داغ‌داغ میل کنید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "مینی‌دونات یا پنکیک‌های رنگی",
     "desc": "مایه پنکیک را با آرد، شیر، تخم‌مرغ و شکر درست کنید. مایه را در تابه داغ بریزید تا پنکیک‌های کوچک و گرد قالب بخورند. جذابیت اصلی این دیت در بخش تزیین است: نوتلا یا شکلات تخته‌ای را بن‌ماری (ذوب) کنید، توت‌فرنگی‌ها را برش بزنید و با ترافل‌های رنگی، پنکیک‌ها را طبقه به طبقه روی هم بچینید و تزیین کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, _t_time("۱.۵ ساعت"), _t_cost("ارزان")]},
    {"title": "تولدِ یک نوشیدنی (ماکتیل بار)",
     "desc": "یک پیشخوان کوچک در آشپزخانه درست کنید. چند مدل آبمیوه (مثل انار، پرتقال و آناناس)، یک بطری سودا (آب گازدار)، شربت سن‌ایچ نعنا یا آلبالو، همراه با لیموترش تازه و برگ‌های نعنا بخرید. با مخلوط کردن لایه‌ای این مواد و اضافه کردن یخ فراوان، سعی کنید یک نوشیدنی لایه‌لایه و جدید اختراع کنید و برای اختراع‌تان یک اسم دو‌نفره بگذارید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "فرنچ‌توست شبانه",
     "desc": "نان تست معمولی یا نان باگت شیری را بردارید. در یک کاسه، تخم‌مرغ را با کمی شیر، دارچین و وانیل هم بزنید. نان‌ها را چند ثانیه در این مایه قرار دهید تا جذبش شود، سپس در تابه با کمی کره سرخ کنید تا طلایی و برشته شوند. در آخر روی آن پودر قند بپاشید و با عسل یا شکلات داغ داغ بخورید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "اسنک‌بار و کلاب‌ساندویچ چالش سرعت",
     "desc": "تمام مواد اولیه مثل ژامبون، پنیر ورقه‌ای گودا، کاهو، گوجه، چیپس خلالی و سس‌ها را روی میز کار بچینید. تایمر گوشی را روی ۲ دقیقه بگذارید. هرکس باید در این زمان کم، یک ساندویچ سه طبقه (کلاب) با چیدمان منظم درست کند، آن را به صورت مثلثی برش بزند و با چوب‌کبریت فیکس کند. کسی که ساندویچش تمیزتر و طبقاتش محکم‌تر باشد برنده است.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_COMPETE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "سیب‌زمینی سرخ‌کرده با پنیر غرق‌شده",
     "desc": "سیب‌زمینی‌ها را به صورت خلال‌های درشت خرد کنید، کمی بجوشانید و بعد سرخ کنید تا کاملاً کرانچی شوند. در یک تابه کوچک، کمی کره را با آرد تفت دهید، شیر اضافه کنید و بعد از غلیظ شدن، کلی پنیر چدار رنده‌شده درونش بریزید تا سس پنیر زرد و کشسانی درست شود. سیب‌زمینی‌ها را در ظرف بزرگ بریزید و سس داغ را روی آن خالی کنید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "تزیین کاپ‌کیک‌های آماده",
     "desc": "اگر فر ندارید، ۶ عدد کاپ‌کیک ساده و وانیلی از قنادی بخرید. در خانه با هم خامه قنادی را با همزن بزنید تا فرم بگیرد و به آن رنگ خوراکی (مثلاً صورتی یا آبی) اضافه کنید. خامه را داخل قیف و ماسوره بریزید و چالش این است که چه کسی می‌تواند زیباترین و تمیزترین گل یا طرح خامه را روی کاپ‌کیک‌ها بزند.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("ارزان")]},
]

# سنین 20 تا 25 — این بازه فقط ایده‌های اختصاصیِ خودش رو می‌بینه (ایده‌های 15-20 نمایش داده نمی‌شن)
FOOD_20_25 = [
    {"title": "پاستا آلفردو با سس دست‌ساز",
     "desc": "یک نفر مرغ‌ها را به صورت مکعبی خرد کرده و با سیر و فلفل سیاه مرینیت کند و دومی قارچ‌ها را ورقه‌ای بزند. مرغ و قارچ را تفت دهید. پاستا پنه را بجوشانید. برای سس، خامه صبحانه را با کمی شیر و شیره قارچ و کلی پنیر پارمسان مخلوط کنید تا غلیظ شود. پاستا را درون سس بیندازید تا طعم‌ها به خورد هم بروند. یک دیت کلاسیک و همیشه محبوب.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۱.۵ ساعت"), _t_cost("متوسط")]},
    {"title": "چالش سوشی خانگی",
     "desc": "برنج کته نرم درست کنید. جلبک نوری، آووکادو، خیار قلمی و فیله مرغ سوخاری یا کراب بخرید. جلبک را روی حصیر مخصوص سوشی بگذارید، برنج را پهن کنید و مواد را نواری وسط آن بچینید. چالش اصلی و خنده‌دار دیت، رول کردن محکم جلبک است که باز نشود. در نهایت با یک چاقوی تیز برش بزنید و با سس سویا میل کنید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CREATIVE, TAG_COMPETE, _t_cost("متوسط")]},
    {"title": "چالش غذاهای ایرانی",
     "desc": "به انتخاب خودتون یکی از غذاهای ایرانی رو با هم دیگه بپزید و نوش جان کنید. برای شروع یه غذای ایرانیِ نسبتاً وقت‌گیر رو انتخاب کنید — مثلاً قورمه‌سبزی یا خورشِ فسنجون. یکی از شما مسئول سرخ کردنِ سبزی یا کوبیدنِ گردو باشه و اون یکی مسئولِ گوشت و لپه. برای برنج، از قبل تصمیم بگیرید ایرانیِ ته‌دیگ‌دار می‌پزید یا شفته‌پلوی سریع. برای بازیِ رقابتی، مادر یا مادربزرگ یکی‌تون رو زنگ بزنید تا سرِ پخت راهنمایی‌تون کنه — این تماس در حین آشپزی نصف لذتِ کاره. در آخر سفره‌ی سنتی ایرانی رو با نون سنگک و سبزی خوردنِ تازه پهن کنید و بذارید عطر زعفرون و ادویه فضای خونه رو پر کنه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "وافل و کرپ فرانسوی",
     "desc": "مایه کرپ (آرد، شیر، تخم‌مرغ، کمی وانیل و شکر) را درست کنید. یک تابه نچسب را چرب کنید و لایه خیلی نازکی از مایه را کف تابه پخش کنید تا سریع بپزد. کرپ‌ها را که آماده کردید، وسط آن‌ها نوتلا بکشید، موز و توت‌فرنگی بگذارید و آن را به صورت مثلثی تا کنید. روی آن را با سس شکلات و پودر پسته دیزاین کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱.۵ ساعت"), _t_cost("ارزان")]},
    {"title": "سالاد بار مدرن (سالاد سزار اصل)",
     "desc": "یک دیت آشپزی سبک اما نیازمند جزئیات. نان‌های تست را مکعبی خرد کنید و با روغن زیتون و سیر در فر برشته کنید (کِروتون). فیله‌های مرغ را مرینیت و سوخاری یا گریل کنید. کاهو رسمی را درشت خرد کنید. اوج هنر این دیت درست کردن سس سزار است: ترکیب مایونز، سس خردل، سیر رنده‌شده، آب لیموترش تازه، پنیر پارمسان و فلفل سیاه فراوان.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, _t_time("۱.۵ ساعت"), _t_cost("متوسط")]},
    {"title": "تاکو مکزیکی با نان ترتیلا",
     "desc": "گوشت چرخ‌کرده را با پیاز، فلفل دلمه‌ای، رب و ادویه‌های تند (پاپریکا و فلفل قرمز) تفت دهید. نان‌های کوچک ترتیلا یا پیتا را به صورت هلال درون فر بگذارید تا خشک و کرانچی شوند. حالا داخل نان‌ها را با مایه گوشت، کاهوی ریزشده، ذرت، پنیر رنده‌شده و یک سالسای تند (گوجه و پیاز خردشده) پر کنید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ADVENT, _t_time("۱.۵ ساعت"), _t_cost("متوسط")]},
    {"title": "بیکینگِ کوکی‌های شکلاتی نرم",
     "desc": "کره هم‌دمای محیط را با شکر قهوه‌ای و سفید هم بزنید، تخم‌مرغ و آرد و بکینگ‌پودر را اضافه کنید تا خمیر نرمی به دست آید. شکلات تخته‌ای را به تکه‌های بزرگ خرد کنید و داخل خمیر بریزید. گلوله‌های خمیری را با فاصله روی سینی فر بچینید. راز این کوکی این است که نباید زیاد در فر بماند؛ باید وقتی خارج می‌شود وسطش شل باشد تا بعد از خنک شدن نرم و کشسان بماند.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, _t_time("۱.۵ ساعت"), _t_cost("ارزان")]},
    {"title": "لازانیای کلاسیک تنوری",
     "desc": "مایه گوشتی شبیه ماکارونی اما غلیظ‌تر درست کنید. یک سس بشامل عالی هم بسازید (تفت دادن آرد در کره، اضافه کردن شیر گرم و جوز هندی تا غلیظ شدن). کف ظرف پیرکس سس بشامل بزنید، یک لایه ورقه لازانیا، مایه گوشت، سس بشامل و پنیر پیتزا بریزید. این کار را ۴ طبقه تکرار کنید و طبقه آخر را غرق در پنیر کنید تا در فر طلایی شود.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "شیک‌ها و گلاسه‌های پینترستی",
     "desc": "لبه لیوان‌های بلند را به شکلات ذوب‌شده آغشته کنید و در پودر بیسکویت لوتوس یا ترافل بگردانید تا لبه لیوان تزیین شود. درون مخلوط‌کن، بستنی وانیلی یا شکلاتی، کمی شیر و موز یا مغز گردو و نوتلا بریزید و میکس کنید. شیک را داخل لیوان‌ها ریخته، رویش را با خامه فرم‌گرفته، بیسکویت کامل و یک اسلایس موز دیزاین کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, _t_time("۱ ساعت"), _t_cost("ارزان")]},
]

FOOD_25_30_EXTRA = [
    {"title": "استیک گوشت با سس قارچ و پوره سیب‌زمینی",
     "desc": "گوشت راسته یا فیله گوساله را با روغن زیتون، سیر له شده و رزماری مرینیت کنید. تابه چدنی را بگذارید تا کاملاً داغ و دودی شود. استیک را داخل تابه بیندازید و تکنیک Basting (ریختن کره ذوب‌شده و سیر با قاشق روی گوشت در حال پخت) را اجرا کنید. گوشت را بعد از پخت ۵ دقیقه استراحت دهید. در این فاصله پوره سیب‌زمینی نرم را با کره و شیر و سس قارچ غلیظ آماده کنید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("گران")]},
    {"title": "پخت نان فوکاچیای ایتالیایی با تزیین هنری",
     "desc": "خمیرمایه، آرد، آب و روغن زیتون فراوان را مخلوط کنید تا خمیر لطیفی به دست آید. خمیر را کف سینی پهن کنید و اجازه دهید استراحت کند تا حباب بزند. با انگشت روی خمیر حفره ایجاد کنید. حالا بخش هنری دیت آغاز می‌شود: با استفاده از نصف گوجه گیلاسی‌ها، ساقه رزماری، پرهای پیاز بنفش و زیتون سیاه، یک تابلوی نقاشی از گل و درخت روی سطح خمیر خلق کنید و بعد بپزید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "راتاتویی فرانسوی",
     "desc": "این دیت نیاز به حوصله و دقت دارد. ابتدا یک سس غلیظ از گوجه‌فرنگی پخته، سیر، پیاز و فلفل دلمه‌ای میکس‌شده درست کنید و کف ظرف پیرکس بریزید. حالا بادمجان، کدو سبز و گوجه‌فرنگی‌های هم‌قطر را به صورت ورقه‌های کاملاً نازک خرد کنید. این ورقه‌ها را به صورت یکی‌درمیان و کاملاً قرینه و حلزونی، از دور ظرف به سمت مرکز بچینید. رویش روغن زیتون بریزید و با کاغذ روغنی در فر بپزید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "چالش مرغ شکم‌پُر یا اکبرجوجه",
     "desc": "یک مرغ کوچک یا جوجه کامل تهیه کنید. برای داخل شکم مرغ، پیاز داغ درست کنید و به آن مغز گردوی خردشده، زرشک، رب انار ملس، آلو و ادویه اضافه کنید. مواد را داخل شکم مرغ پر کرده و با نخ و سوزن آشپزی بدوزید. پوست مرغ را به زعفران و کره آغشته کنید و در فر بگذارید تا آرام‌آرام مغزپخت و پوستش کاملاً طلایی و کرانچی شود.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    {"title": "سوپ‌های غلیظ کرمی (سوپ کدو حلوایی)",
     "desc": "تکه‌های کدو حلوایی، سیب‌زمینی، پیاز و سیر را با روغن زیتون و ادویه‌ها (جوز هندی و زنجبیل) در فر رست (کبابی) کنید تا کاراملی شوند. سپس آن‌ها را با آب مرغ داخل قابلمه بریزید تا بپزند. در نهایت کل مواد را با گوشت‌کوب برقی کاملاً پوره و مخملی کنید و کمی خامه بزنید. این سوپ شیک را با نان سیر برشته دست‌ساز سرو کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CALM, _t_time("۱.۵ ساعت"), _t_cost("متوسط")]},
    {"title": "پاستای چرخ‌کرده دستی (Fresh Pasta)",
     "desc": "چالش بزرگ آشپزی! به ازای هر ۱۰۰ گرم آرد، یک تخم‌مرغ اضافه کنید. خمیر را با دست آن‌قدر ورز دهید تا کاملاً منسجم و لطیف شود. خمیر را با وردنه روی میز آن‌قدر پهن کنید تا مثل کاغذ نازک شود. خمیر را رول کرده و با چاقو به صورت نوارهای یک‌اندازه (فتوچینی) برش بزنید. این پاستای تازه فقط ۳ دقیقه نیاز به جوشیدن دارد و طعمش با پاستای شرکتی زمین تا آسمان فرق می‌کند.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, TAG_ART, _t_cost("متوسط")]},
    {"title": "جوجه کباب حلزونی یا کباب تابه مدرن",
     "desc": "فیله‌های مرغ را به صورت نوارهای بلند برش بزنید. آن‌ها را با زعفران فراوان، آب لیموترش، سس خردل، روغن زیتون و پیاز خلال‌شده مرینیت کنید. بعد از چند ساعت، نوارها را مثل حلزون رول کنید و به سیخ‌های چوبی بکشید. سیخ‌ها را در تابه چدنی با کمی کره تفت دهید و در کنار گوجه و فلفل کبابی و برنج زعفرانی قالبی سرو کنید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "تدارک یک چاشتِ فینگرفودی برای دیت شبانه",
     "desc": "برای یک دیت پر از تنوع، چند مدل فینگرفود مینیاتوری درست کنید. مثلاً نان‌های تست را قالب گرد بزنید، رویش سالاد الویه بگذارید و با زیتون تزیین کنید (کاناپه الویه). یا تارت‌های آماده نمکی بخرید و داخلش را با سالاد اندونزی پر کنید. درست کردن رول‌های کوچک کالباس و پنیر گودا با نان لواش هم گزینه سوم است.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_ART, TAG_ROMANTIC, _t_cost("متوسط")]},
    {"title": "پختن کیک ردولوت یا چیزکیک نیویورکی",
     "desc": "چیزکیک نیویورکی (پخته‌شده) نیاز به دقت بالایی دارد. ابتدا بیسکویت دایجستف را پودر و با کره مخلوط کنید و کف قالب کمربندی پرس کنید. برای مایه چیزکیک، پنیر خامه‌ای، خامه قنادی، تخم‌مرغ، وانیل و کمی آرد را هم بزنید و روی کراست بیسکویتی بریزید. قالب را در حمام آب گرم (قرار دادن قالب در یک سینی آب) در فر بپزید تا چیزکیک شما بدون ترک و کاملاً لطیف آماده شود.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "غذاهای دریایی (ماهی سالمون با سس لیمو و شوید)",
     "desc": "فیله‌های سالمون را با نمک، فلفل سیاه و کمی آب لیمو آغشته کنید. آن‌ها را از سمت پوست داخل تابه با روغن زیتون گریل کنید تا پوستش کاملاً کرانچی شود. برای سس روی ماهی، کره را ذوب کنید، سیر رنده‌شده را تفت دهید، آب لیموترش تازه، خامه و مقدار زیادی شوید تازه خردشده اضافه کنید. سالمون را در بشقاب چیده و سس را روی آن بریزید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت"), _t_cost("گران")]},
    {"title": "ته‌چین مرغ و بادمجان قالبی",
     "desc": "مرغ را بپزید و ریش‌ریش کنید. بادمجان‌ها را ورقه‌ای سرخ کنید. برنج آبکش‌شده را با مخلوط ماست چکیده، زرده تخم‌مرغ، زعفران غلیظ دم‌کرده و کره ذوب‌شده مخلوط کنید. کف قالب‌های کوچک مافین یا یک قابلمه کوچک را چرب کنید. یک لایه برنج زعفرانی، یک لایه مرغ و بادمجان و دوباره برنج بریزید و با پشت قاشق کاملاً فشرده کنید تا بعد از پخت، ته‌چین‌های قالبی و شیک داشته باشید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("متوسط")]},
]

FOOD_30_35_EXTRA = [
    {"title": "پخت نان ترش خانگی (Sourdough)",
     "desc": "این دیت نیاز به برنامه‌ریزی از روز قبل دارد. کار با استارتر (مخمر طبیعی)، ورز دادن خمیر با تکنیک Stretch and Fold (کشیدن و تا کردن خمیر در فواصل ۳۰ دقیقه‌ای) یک کار کاملاً مدیتیشن‌گونه و آرامش‌بخش دو‌نفره است. در نهایت خمیر را در قابلمه چدنی داغ (Dutch Oven) می‌پزید. لحظه‌ای که درِ قابلمه را برمی‌دارید و نانِ پف‌کرده و کرانچی را می‌بینید، اوج لذت این دیت است.",
     "border": (0.788, 0.502, 0.376, 1), "fav": True,
     "tags": [TAG_CALM, TAG_ART, _t_cost("متوسط")]},
    {"title": "سالمون گریل با سس کره لیمویی و مارچوبه",
     "desc": "مارچوبه‌ها را با روغن زیتون، نمک و سیر در تابه گریل تفت دهید تا کمی نرم اما ترد بمانند. سالمون ارگانیک را با سسِ کره، آب لیموترش تازه، رنده پوست لیمو (Zest) و کمی عسل گریل کنید. هنر اصلی در Plating (چیدمان بشقاب) است: مارچوبه‌ها را کف بشقاب به صورت موازی بچینید، فیله سالمون را روی آن قرار دهید و با قاشق سس زلالِ کره و لیمو را دور بشقاب خط بکشید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("گران")]},
    {"title": "غذاهای گیاهی مدرن (برگر کینوا)",
     "desc": "کینوا را بپزید و با سیب‌زمینی پخته، پیازچه خردشده، پودر سوخاری، ادویه‌ها و یک عدد تخم‌مرغ مخلوط کنید تا منسجم شود. همبرگرهای کینوا را قالب بزنید و گریل کنید. به جای نان‌های معمولی، از نان‌های چاودار یا هفت‌غله استفاده کنید و برگر را با سس آووکادوی دست‌ساز (گواکاموله)، برگ‌های اسفناج جوان و گوجه خشک چیدمان کنید. یک شام کاملاً لوکس و سلامت‌محور.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "استیک ریب‌آی با کره سبزیجات (Herb Butter)",
     "desc": "ابتدا کره سبزیجات را درست کنید: کره نرم را با جعفری، گشنیز، رزماری خردشده، سیر له شده و کمی نمک مخلوط کنید، روی پلاستیک رول کنید و در فریزر بگذارید تا سفت شود. استیک ریب‌آی (با رگه‌های چربی عالی) را در تابه چدنی به میزان مدیوم-رِئر (Medium-Rare) بپزید. به محض اینکه استیک را در بشقاب گذاشتید، یک حلقه از آن کره سبزیجات سرد را روی استیک داغ بگذارید تا آرام‌آرام ذوب شود و طعم جادویی به گوشت بدهد.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۱.۵ ساعت"), _t_cost("گران")]},
    {"title": "پخت خوراک میگو با سس سیر و گشنیز (مدیترانه‌ای)",
     "desc": "یک دیت سریع اما بسیار لوکس. میگوهای پاک‌شده و خشک‌شده را آماده کنید. در یک تابه وسیع، مقدار زیادی کره و روغن زیتون بریزید. ۴ حبه سیر له شده را تفت دهید تا عطرش بلند شود، سپس میگوها را اضافه کنید. میگوها فقط باید ۳ الی ۴ دقیقه تفت بخورند تا سفت نشوند. در دقیقه آخر، آب یک لیموترش تازه و حجم زیادی گشنیز ساطوری‌شده اضافه کنید و با نان باگت داغ سرو کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت"), _t_cost("گران")]},
    {"title": "دیتِ «دلمه برگ مو» مینیاتوری",
     "desc": "پختن دلمه یک کار تیمی طولانی و آرامش‌بخش است که فضا را برای ساعت‌ها گفتگو باز می‌کند. مایه دلمه را با برنج نیم‌دانه، لپه پخته، گوشت چرخ‌کرده و سبزی دلمه فراوان درست کنید. چالش دو‌نفره این است که برگ‌های مو را به ظریف‌ترین شکل ممکن و به صورت مدادی یا بقچه‌ای‌های خیلی کوچک بپیچید و مرتب کف قابلمه بچینید و با چاشنی سرکه و شیره (یا رب گوجه و لیمو) دم بگذارید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "پاستا با سس پستو دست‌ساز در هاون",
     "desc": "استفاده از مخلوط‌کن را فراموش کنید؛ راز یک سس پستوی اصیل، سابیدن مواد در هاون سنگی است. با هم برگ‌های ریحان تازه، سیر، مغز گردو یا صنوبر، و نمک دریا را در هاون بکوبید تا خمیر شود. سپس روغن زیتون فوق‌بکر و پنیر پارمسان رنده‌شده را اضافه کنید تا سس یکدست شود. پاستای ترجیحاً فتوچینی را بپزید و این سس خنک و معطر را با پاستای داغ مخلوط کنید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "سوپ پیاز فرانسوی کلاسیک",
     "desc": "پیازها را به صورت خلال‌های نازک خرد کنید. راز این سوپ، تفت دادن پیازها با کره روی شعله ملایم به مدت ۴۰ دقیقه است تا قند پیاز کاملاً آزاد و قهوه‌ای‌رنگ (کاراملی) شود. سپس کمی آرد، آب گوشت (استاک) و چاشنی بزنید تا غلیظ شود. سوپ را در کاسه‌های سفالی بریزید، یک تکه نان باگت تست‌شده روی سوپ بگذارید و رویش را با پنیر گرویر یا گودا پر کنید و در فر بگذارید تا پنیر آب و برشته شود.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "کیک هویج و گردو با سس کرم‌چیز",
     "desc": "یک دیت عصرانه پاییزی و گرم. هویج‌ها را ریز رنده کنید. آرد، شکر، تخم‌مرغ، روغن، گردوی خردشده و مقدار زیادی دارچین و جوز هندی را مخلوط کنید و کیک را بپزید. در زمان پخت که عطر دارچین خانه را پر کرده، سس روی کیک را درست کنید: ترکیب پنیر خامه‌ای، پودر قند، کمی کره و وانیل. بعد از خنک شدن کیک، این کرم سفید و لذیذ را روی آن بکشید.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ART, TAG_ROMANTIC, _t_cost("متوسط")]},
    {"title": "چالشِ «بشقاب مزه گرم» (Warm Meze)",
     "desc": "به جای یک غذای واحد، یک دیس حاوی چندین مزه خاورمیانه‌ای و مدیترانه‌ای گرم درست کنید. بادمجان‌ها را روی گاز کبابی کنید و پوست بکنید و با ارده، سیر و لیمو مخلوط کنید (متبل). نخودهای پخته را با ارده و روغن زیتون در غذاساز بگردانید (حمص). نان‌های پیتا را برش بزنید، روغن زیتون و زعتر بزنید و در فر برشته کنید تا در کنار این دیپ‌ها با هم میل کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, TAG_ART, _t_cost("متوسط")]},
    {"title": "مرغ گالانتین (مرغ بدون استخوان شکم‌پر)",
     "desc": "بالاترین سطحِ هماهنگی تکنیکی در آشپزخانه. با یک چاقوی ظریف و تیز، بدون اینکه به پوست و گوشت مرغ آسیب بزنید، اسکلت و استخوان‌های یک مرغ کامل را از داخل آن خارج کنید تا مرغ به صورت یک کیسه گوشتی یکدست درآید. داخل آن را با مایه گوشتی، زرشک، پسته و ادویه‌ها پر کنید، مرغ را رول کرده و بدوزید و در فر رست کنید. برش‌های این مرغ شبیه به رول‌های کالباس مجلل خواهد بود.",
     "border": (0.788, 0.502, 0.376, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("گران")]},
]


def get_food_ideas(age):
    """ایده‌های «سفره دو نفره» — همه‌ی بازه‌های سنی برای همه نمایش داده می‌شه،
    و کنار هر ایده تگ بازه‌ی سنیِ مربوطه می‌خوره."""
    return (_tag_ideas(FOOD_15_20, TAG_AGE_15_20)
            + _tag_ideas(FOOD_20_25, TAG_AGE_20_25)
            + _tag_ideas(FOOD_25_30_EXTRA, TAG_AGE_25_30)
            + _tag_ideas(FOOD_30_35_EXTRA, TAG_AGE_30_35))



# ---------------------------------------------------------------------------
# ایده‌های «دیت‌های خانگی» — فقط برای ۲۰ سال به بالا.
# اگر کاربر ۱۵ تا ۲۰ ساله باشد، در صفحه‌ی این دسته یک پیام مخصوص نمایش داده می‌شود.
# ---------------------------------------------------------------------------
HOME_20_PLUS = [
    {"title": "ماراتن بازی‌های ویدیویی دونفره (Gaming Night)",
     "desc": "یک بازی داستانی و همکاری مثل It Takes Two یا یک بازی مسابقه‌ای مثل Crash Team Racing یا Mortal Kombat را راه بیندازید. کری‌خوانی، کل‌کل و تلاش برای رد کردن مراحل، انرژی فوق‌العاده‌ای به فضای خانه می‌آورد. برای اضافه شدنِ لایه‌ی رقابت، شرط ببندید که بازنده باید تا آخر هفته قهوه‌ی صبحِ برنده رو دم کنه — کوچیک ولی خنده‌دار.",
     "border": (0.608, 0.427, 0.816, 1), "fav": True,
     "tags": [TAG_COMPETE, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "اتاق فرار خانگی (Escape Room Boardgames)",
     "desc": "بازی‌های رومیزی خاصی مثل سری Exit یا Unlock مکانیزم اتاق فرار را در خانه بازسازی می‌کنند. با هم فکرهایتان را روی هم بگذارید، معماها را حل کنید و رمزها را بشکنید تا از بازی خارج شوید. قبل از شروع، تلفن رو در یه اتاق دیگه بذارید و شرط این باشه که فقط با حل معماها اجازه‌ی دسترسی بهش رو دارید. این محدودیت خودش هیجانِ اتاقِ فرار رو خیلی بالا می‌بره.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ADVENT, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "مسابقه کارائوکه (همخوانی با موزیک)",
     "desc": "نسخه‌ی بی‌کلام آهنگ‌های محبوب را روی تلویزیون پخش کنید. با یک میکروفون ساده یا حتی کنترل تلویزیون به‌جای میکروفون، با هم مسابقه‌ی خوانندگی بگذارید و فضا را شبیه یک کنسرت دونفره‌ی شاد کنید. قبل از شروع، هر کدوم پنج آهنگ برای اون یکی انتخاب کنید — کسی نمی‌دونه قراره چه آهنگی بخونه. برای امتیازدهی، از یه اپلیکیشنِ کارائوکه استفاده کنید یا خودتون به‌صورت خنده‌دار رأی‌گیری کنید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CREATIVE, TAG_ROMANTIC, _t_cost("ارزان")]},
    {"title": "چالش ساخت لگو یا پازل بزرگ",
     "desc": "یک پازل ۱۰۰۰ تکه با طرحی که هر دو دوست دارید یا یک ست لگوی جذاب بخرید. چیدن قطعات در کنار گپ زدن و گوش دادن به موسیقی، یک فعالیت تیمی بسیار شیرین است. اگر پازل انتخاب کردید، اول قطعات لبه‌ای رو جدا کنید و قابِ اطراف رو ببندید؛ بعد بر اساس رنگ‌های مسلط، قطعات وسط رو دسته‌بندی کنید. یه پلی‌لیستِ آروم پخش کنید و شرط این باشه که در حین پازل کسی از گوشی استفاده نکنه.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "تست کورکورانه‌ی طعم‌ها (Blind Taste Test)",
     "desc": "چشم‌های پارتنرتان را با یک شال ببندید و تکه‌های کوچکی از خوراکی‌های مختلف (پنیر، شکلات، میوه، سس) در دهانش بگذارید تا حدس بزند. ری‌اکشن‌ها فوق‌العاده خنده‌دار است. برای هیجانِ بیشتر، بعضی از خوراکی‌ها رو با ترکیب‌های عجیب بذارید (مثلاً پنیر با عسل، یا خیارشور با شکلات) تا واکنش صادقانه‌ی طرف رو بگیرید. حتماً یه لیوان آب کنار دستِ کسی که چشم بسته باشه.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_CREATIVE, _t_time("۱ ساعت"), _t_cost("ارزان")]},
    {"title": "شبِ پیتزای من‌درآوردی (DIY Pizza Night)",
     "desc": "نان‌های پیتزای آماده یا خمیر بخرید و ظرف‌های مواد اولیه را روی میز بچینید. هرکس باید پیتزای خودش را با یک طراحی یا ترکیب طعمیِ عجیب درست کند و در نهایت به پیتزای همدیگر نمره بدهید. برای رقابتیِ بیشتر، دو دور بزنید: در دور اول هر کس پیتزا رو با موادِ لذیذ و کلاسیک درست می‌کنه؛ در دور دوم هر کس تعمداً یه ترکیبِ عجیبِ خنده‌دار (مثلاً پنیر با موز) استفاده می‌کنه. عکاسی هر دور فراموش نشه.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("ارزان")]},
    {"title": "بارمن خانگی (موکتیل و دسر پینترستی)",
     "desc": "آبمیوه‌ها، شربت‌های رنگی، سودا، یخ فراوان، لیمو و نعنا تازه بخرید. نوشیدنی‌های لایه‌لایه، خنک و شیکی شبیه فیلم‌ها یا کافه‌های گران‌قیمت درست کنید و با میوه‌ها تزیینش کنید. از قبل چند تا رفرنسِ عکسِ ماکتیل در گوشی داشته باشید و شرط این باشه که در پایان، ماکتیل ساختِ خودتون رو کنار عکسِ رفرنس عکس بگیرید — بازیِ مقایسه‌ی «انتظار در برابر واقعیت».",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CREATIVE, TAG_ROMANTIC, _t_cost("متوسط")]},
    {"title": "فوندوی شکلات و میوه",
     "desc": "یک کاسه شکلات داغ و ذوب‌شده (بن‌ماری) وسط میز بگذارید و دور آن را با موز، توت‌فرنگی، مارشمالو، بیسکویت ویفر و چوب‌شور پر کنید. با سیخ‌های چوبی شب شیرین و رمانتیکی بسازید. برای اینکه شکلات سفت نشه یه قاشقِ کوچیک روغن نارگیل یا خامه بهش اضافه کنید. اگه وسط شب دلتون کباب هم خواست، تکه‌های موز و توت رو با سیخ کبابی گاز داغ گرم کنید و بعد در شکلات فرو ببرید — یه دسرِ نیمه‌کبابیِ خفن.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت"), _t_cost("متوسط")]},
    {"title": "دیتِ «بوم مشترک» (نقاشی روی فرش)",
     "desc": "یک بوم نقاشی بزرگ و رنگ اکریلیک وسط اتاق بگذارید. بدون نقشه‌ی قبلی، نوبتی یا همزمان شروع به رنگ‌آمیزی کنید. این تابلو یک یادگاری ابدی برای دیوار خانه‌تان می‌شود. یه سفره‌ی نایلونی زیرِ بوم پهن کنید. قانونِ خنده‌دار این باشه که هر پنج دقیقه یک بار قلم‌موها رو با هم جابجا کنید — این‌جوری هیچ‌کدوم نمی‌تونید یه بخش رو کاملاً مالِ خودتون بدونید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ART, TAG_CREATIVE, _t_cost("متوسط")]},
    {"title": "کارگاه سفالگری با گل خود‌خشک‌شونده",
     "desc": "گل سفالگریِ هوا-خشک تهیه کنید. برای همدیگر یا برای خانه وسایل کوچک بسازید؛ مثل جاکلیدی، ظروف مینیاتوری یا جاشمعی. بعد از خشک شدن می‌توانید رنگش کنید.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ART, TAG_CALM, _t_cost("ارزان")]},
    {"title": "ساخت بُرد آرزوها و آینده (Vision Board)",
     "desc": "یک مقوای بزرگ بردارید. تصاویر، جملات یا طرح‌هایی از خانه‌ای که دوست دارید، سفرهایی که می‌خواهید بروید یا لایف‌استایلِ مدنظرتان را از اینترنت/مجلات جمع کنید و روی بورد بچسبانید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ROMANTIC, TAG_CREATIVE, _t_cost("ارزان")]},
    {"title": "سینما کلوپ اختصاصی با تم کارگردان",
     "desc": "اتاق را تاریک کنید، ریسه‌های نور را روشن کنید و کوسن‌های فراوان وسط زمین بچینید. سه‌گانه‌ی یک کارگردانِ بزرگ (مثل پیش از طلوع/پیش از غروبِ ریچارد لینکلیتر) را تماشا کنید و درباره‌اش گپ بزنید. یه پُلی‌لیستِ موسیقی از فیلم‌های کارگردان رو در پس‌زمینه (قبل و بعد فیلم) پخش کنید. یه بشقاب اسنکِ تم‌دار (مثلاً کروسان و اسپرسو برای کارگردان‌های فرانسوی) هم فضا رو کامل می‌کنه.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("ارزان")]},
    {"title": "شبِ اسپا و ماساژ خانگی (Home Spa)",
     "desc": "اتاق را با شمع‌های معطر، عود و موزیک‌های ریلکس‌کننده آماده کنید. برای همدیگر ماسک صورت بگذارید، چای سبز یا دمنوش گرم بنوشید و با روغن‌های خوشبو همدیگر را ماساژ دهید. از قبل، ماسک‌ها و روغن‌ها رو در یخچال بذارید تا خنک باشن. قانون شب این باشه که هیچ‌کدوم به گوشی نگاه نکنید و فقط صداهای طبیعت یا موسیقیِ آمبینت پخش بشه.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_CALM, TAG_ROMANTIC, _t_cost("متوسط")]},
    {"title": "دیتِ پادکست عمیق یا کتاب صوتی",
     "desc": "نور اتاق را کم کنید. یک اپیزود پادکست عمیق (روانشناسی، فلسفه، جنایی یا تاریخ) یا یک کتاب صوتی پخش کنید. چشمان‌تان را ببندید، گوش بدهید و بعد درباره‌ی زاویه‌دید خودتان گفتگو کنید. بعد از پایان اپیزود، به جای بحث فوری، پنج دقیقه سکوتِ عمدی رو تجربه کنید و بعد هر کدوم یک جمله‌ی کلیدی از پادکست که در ذهن‌تون مونده رو بگید — این ساختار مکالمه رو خیلی عمیق‌تر می‌کنه.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_CALM, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "شبِ شعر، گرامافون و نوستالژی",
     "desc": "یک آلبوم موسیقی قدیمی، جاز یا سنتیِ باکیفیت پخش کنید. یک کتاب شعر (حافظ، شاملو یا سهراب) بردارید و نوبتی با صدای آرام برای هم بخوانید. صمیمیت کلامیِ شما را خیلی بالا می‌برد. قبل از خوندنِ هر شعر، دفتر رو بذارید در تاریکی و فقط با نور یه شمع بخونید. صدای گرامافون رو تا حدی کم کنید که فقط زمینه باشه، نه اینکه با شعر رقابت کنه.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ROMANTIC, TAG_ART, _t_cost("رایگان")]},
    {"title": "مصاحبه‌ی کپسول زمان (ضبط پادکست دونفره)",
     "desc": "وویس‌رکورد گوشی را روشن کنید و سوال‌های عمیق از همدیگر بپرسید (مثلاً: بزرگ‌ترین ترست این روزها چیه؟ ۵ سال دیگه خودمون رو کجا می‌بینی؟). این فایل را ذخیره کنید تا چند سال بعد خاطره‌بازی کنید. قبل از ضبط، ده سؤال روی کاغذ بنویسید و در یه جعبه بذارید. به نوبت از جعبه سؤال بردارید تا هیچ‌کدوم نتونید سؤالِ آسون رو انتخاب کنید. فایل نهایی رو با تاریخ ذخیره کنید و یادداشت کنید که سال بعد کجا گوش می‌دید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ROMANTIC, _t_time("۱ ساعت"), _t_cost("رایگان")]},
    {"title": "کمپینگ وسط پذیرایی!",
     "desc": "اگر حیاط یا بالکن بزرگ ندارید، وسط پذیرایی چادر مسافرتی‌تان را برپا کنید! داخلش را پر از پتو و بالش کنید، چراغ‌قوه یا ریسه روشن کنید و تنقلات کمپینگ (چای فلاسک و چیپس) تدارک ببینید. چراغ‌های خونه رو خاموش کنید و فقط با چراغ‌قوه و ریسه راه برید. یه بلندگو با صدای طبیعت (باد، شب، پرنده) پخش کنید تا مغزتون واقعاً فکر کنه در جنگلید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ADVENT, TAG_CREATIVE, _t_cost("ارزان")]},
]

def get_home_ideas(age):
    """ایده‌های دیت خانگی فقط برای ۲۰ سال به بالا. زیر ۲۰ سال لیست خالی برمی‌گرده
    و در صفحه‌ی ایده‌ها به‌جاش یک پیام مخصوص نمایش داده می‌شه."""
    try:
        a = int(age)
    except Exception:
        a = 20
    if a < 20:
        return []
    return _tag_ideas(HOME_20_PLUS, TAG_AGE_20_PLUS)


# ---------------------------------------------------------------------------
# ایده‌های «طبیعت‌گردی» بر اساس بازه‌ی سنی کاربر (تجمعی)
# ---------------------------------------------------------------------------
NATURE_15_20 = [
    {"title": "پیک‌نیک تخصصی در پارک جنگلی",
     "desc": "به‌جای یک ساندویچ ساده، منوی پیک‌نیک را از قبل با هم بنویسید: یک غذای اصلی سرد، دو مخلفات و یک دسر. زیرانداز، ترموس چای و یک بلندگوی کوچک ببرید. نکته‌ی عملی: غذاها را در ظرف‌های جدا و از قبل برش‌خورده ببرید تا سر بساط فقط بچینید و وقتتان صرف آماده‌سازی نشود.",
     "border": (0.357, 0.667, 0.498, 1), "fav": True,
     "tags": [TAG_CALM, TAG_DUO, _t_time("۴ ساعت"), _t_cost("ارزان")]},
    {"title": "پیاده‌روی کنار رودخانه",
     "desc": "یک مسیر رودخانه‌ای نزدیک شهر انتخاب کنید و مسیر رفت را در سکوت و مسیر برگشت را در گفت‌وگو طی کنید. کفش ضدلغزش بپوشید چون سنگ‌های کنار آب لیز هستند. نکته: یک بطری خالی ببرید و در راه هر زباله‌ای دیدید جمع کنید؛ این کار کوچک، حس مشترکِ خوبی از روز می‌سازد.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "تماشای غروب روی تپه",
     "desc": "یک تپه یا بلندیِ مشرف به شهر پیدا کنید و نیم‌ساعت قبل از غروب آنجا باشید. یک پتوی نازک و دو لیوان نوشیدنی گرم ببرید. نکته‌ی عملی: زمان دقیق غروب را از اپلیکیشن آب‌وهوا بگیرید و ۴۵ دقیقه زودتر حرکت کنید؛ بهترین رنگ آسمان دقیقاً ۱۰ دقیقه بعد از غروب اتفاق می‌افتد.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "جنگل‌گردی با بازی جست‌وجوی گنج",
     "desc": "قبل از رفتن، هرکدام لیستی از ۱۰ چیز طبیعی بنویسید (برگ قرمز، سنگ صاف، پر پرنده و...) و لیست‌ها را رد و بدل کنید. هرکس زودتر همه را پیدا کرد برنده است. نکته: از هر چیزی که پیدا کردید عکس بگیرید به‌جای برداشتن، تا طبیعت دست‌نخورده بماند.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_ADVENT, TAG_COMPETE, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "دوچرخه‌سواری در مسیر خاکی",
     "desc": "یک مسیر خاکیِ کم‌شیب بیرون شهر انتخاب کنید و با دوچرخه‌ی کرایه‌ای برانید. هر ۲۰ دقیقه یک ایستگاه استراحت با آب و خرما بگذارید. نکته‌ی عملی: قبل از حرکت باد لاستیک‌ها و ترمزها را چک کنید و مسیر را آفلاین روی نقشه ذخیره کنید چون آنتن‌دهی بیرون شهر ضعیف است.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "پرنده‌نگری صبح زود",
     "desc": "یک تالاب یا پارک بزرگ را نزدیک طلوع انتخاب کنید؛ ساعت اول صبح فعال‌ترین زمان پرنده‌هاست. یک دوربین شکاری ساده یا حتی زوم گوشی کافی است. نکته: هر پرنده‌ای دیدید در یک دفترچه با ساعت و رنگش یادداشت کنید؛ در پایان لیست مشترکتان یک یادگاریِ واقعی از آن روز است.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_CALM, TAG_DUO, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "قایق‌سواری پدالی در دریاچه",
     "desc": "یک قایق پدالی یا کایاک دونفره اجاره کنید و تا وسط دریاچه بروید، بعد پدال‌ها را ول کنید و فقط شناور بمانید. نکته‌ی عملی: گوشی‌ها را داخل کیسه‌ی زیپ‌دار بگذارید و ساعت اجاره را طوری بگیرید که آخرِ روز و نور طلایی را روی آب ببینید.",
     "border": (0.251, 0.376, 0.690, 1),
     "tags": [TAG_ADVENT, TAG_DUO, _t_time("۱ ساعت"), _t_cost("متوسط")]},
    {"title": "کوهنوردی سبک تا آبشار",
     "desc": "یک مسیر آبشارِ نزدیک با پیاده‌رویِ حداکثر یک‌ساعته انتخاب کنید. یک تی‌شرت اضافه ببرید چون نزدیک آبشار خیس و خنک می‌شوید. نکته: در نقطه‌ی پایانی ۵ دقیقه بدون حرف زدن فقط به صدای آب گوش بدهید؛ تفاوتش با تماشای معمولی خیلی زیاد است.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_time("۴ ساعت"), _t_cost("ارزان")]},
    {"title": "کاشتن یک نهال مشترک",
     "desc": "یک نهال کوچک بخرید و در یک نهالستان مجاز یا حیاط خانه بکارید و تاریخش را روی یک تکه چوب بنویسید. نکته‌ی عملی: از قبل با شهرداری یا انجمن‌های محیط‌زیستی هماهنگ کنید؛ خیلی از شهرها روزهای مشخصی برای کاشت گروهی دارند و رایگان نهال می‌دهند.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("ارزان")]},
]

NATURE_20_25_EXTRA = [
    {"title": "کمپینگ یک‌شبه با چادر",
     "desc": "یک کمپ‌سایتِ امن و مجاز انتخاب کنید، قبل از تاریکی چادر بزنید و شام را روی گاز پیک‌نیکی بپزید. نکته‌ی عملی: زیرانداز عایق زیر کیسه‌خواب فراموش نشود؛ سرمای زمین بیشتر از سرمای هوا خواب را خراب می‌کند. یک چراغ‌قوه‌ی پیشانی برای هرکدام ببرید.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ADVENT, TAG_DUO, _t_time("یک شب"), _t_cost("متوسط")]},
    {"title": "ستاره‌شناسی شبانه دور از نور شهر",
     "desc": "یک نقطه‌ی حداقل ۳۰ کیلومتر دورتر از نور شهر پیدا کنید و با یک اپلیکیشن نقشه‌ی آسمان صورت‌های فلکی را شکار کنید. نکته: ۲۰ دقیقه اول هیچ صفحه‌ی روشنی نگاه نکنید تا چشم‌ها به تاریکی عادت کنند؛ بعد از آن تعداد ستاره‌هایی که می‌بینید چند برابر می‌شود.",
     "border": (0.251, 0.376, 0.690, 1),
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "اسب‌سواری در دشت",
     "desc": "یک باشگاه سوارکاری با مربی رزرو کنید و جلسه‌ی مقدماتیِ دونفره بگیرید. شلوار کشی و کفش پاشنه‌دار کوتاه بپوشید. نکته‌ی عملی: قبل از سوار شدن چند دقیقه کنار اسب بایستید و گردنش را نوازش کنید؛ آشنایی اولیه ترس را کم می‌کند و تجربه‌ی سواری خیلی روان‌تر می‌شود.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ADVENT, TAG_EXCITING, _t_time("۲ ساعت"), _t_cost("گران")]},
    {"title": "پیاده‌روی جنگلی در مه صبحگاهی",
     "desc": "یک صبح پاییزی یا بهاری، جنگلِ نزدیک را قبل از ساعت ۸ انتخاب کنید تا مه هنوز نشسته باشد. یک ترموس قهوه ببرید. نکته: با گوشی چند ویدئوی ۱۰ ثانیه‌ای از صدای جنگل بگیرید؛ بعداً پخش کردن همان صداها خاطره را برمی‌گرداند.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_CALM, TAG_ROMANTIC, _t_time("۳ ساعت"), _t_cost("رایگان")]},
    {"title": "آبشارگردی یک‌روزه",
     "desc": "دو آبشار در یک مسیر انتخاب کنید و یک روز کامل را به گشتن بین آن‌ها بگذرانید. نکته‌ی عملی: صندل کوهنوردی یا کفشی که خیس شدنش مهم نیست بپوشید و یک حوله‌ی میکروفایبر کوچک ببرید؛ سبک است و سریع خشک می‌شود.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, TAG_SPORT, _t_time("یک روز"), _t_cost("متوسط")]},
    {"title": "آشپزی روی آتش در طبیعت",
     "desc": "در یک محوطه‌ی مجازِ آتش، سیب‌زمینی فویل‌پیچ و ذرت کبابی درست کنید. یکی مسئول آتش و دیگری مسئول غذا باشد و وسط کار جاها را عوض کنید. نکته: زغال را ۴۰ دقیقه قبل از پخت روشن کنید؛ شعله‌ی مستقیم غذا را می‌سوزاند، زغالِ سفیدشده کار درست را می‌کند.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_DUO, TAG_CREATIVE, _t_time("۴ ساعت"), _t_cost("ارزان")]},
    {"title": "چشمه‌گردی و نقشه‌ی دست‌ساز",
     "desc": "سه چشمه یا قناتِ نزدیک را در یک روز ببینید و برای خودتان یک نقشه‌ی دست‌ساز بکشید که مسیر و مزه‌ی آب هرکدام را ثبت کند. نکته‌ی عملی: یک بطری استیل ببرید و آب هر چشمه را بچشید و از ۱۰ نمره بدهید؛ بحث سرِ نمره‌ها بامزه‌ترین بخش روز می‌شود.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_ADVENT, TAG_DUO, _t_time("یک روز"), _t_cost("ارزان")]},
    {"title": "عکاسی طبیعت با نور طلایی",
     "desc": "یک ساعت قبل از غروب به دشت یا مزرعه‌ای بروید و از هم و از طبیعت عکس بگیرید. نکته: پشت به خورشید نایستید؛ خورشید را کنار یا پشت سوژه بگذارید تا لبه‌ی نورانی دور موها بیفتد. در پایان سه عکس برتر را انتخاب و چاپ کنید.",
     "border": (0.608, 0.427, 0.816, 1),
     "tags": [TAG_ART, TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "دشت گل و پیاده‌روی بی‌مقصد",
     "desc": "در فصل گل، یک دشت یا مزرعه‌ی گل انتخاب کنید و بدون مقصد مشخص قدم بزنید. قانون: هیچ‌کدام نباید مسیر را انتخاب کند؛ سر هر دوراهی سکه بیندازید. نکته‌ی عملی: اسپری ضد حساسیت یا ماسک ببرید اگر یکی‌تان به گرده حساسیت دارد.",
     "border": (0.478, 0.188, 0.565, 1),
     "tags": [TAG_CALM, TAG_ROMANTIC, _t_time("۳ ساعت"), _t_cost("رایگان")]},
]

NATURE_25_30_EXTRA = [
    {"title": "کمپینگ کنار دریاچه با صبحانه‌ی طلوع",
     "desc": "چادر را شب کنار دریاچه بزنید و ساعت را نیم‌ساعت قبل از طلوع کوک کنید تا صبحانه را با آفتابِ روی آب بخورید. نکته‌ی عملی: چادر را حداقل ۲۰ متر دورتر از لبه‌ی آب و روی زمینِ کمی شیب‌دار بزنید تا شبنم و رطوبت شبانه اذیت نکند.",
     "border": (0.251, 0.376, 0.690, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_ADVENT, _t_time("یک شب"), _t_cost("متوسط")]},
    {"title": "ترکینگ نیم‌روزه با مسیر مشخص",
     "desc": "یک مسیر ۸ تا ۱۲ کیلومتری با راهنمای مسیر (GPX) انتخاب کنید و با کوله‌ی سبک بروید. نکته: هر ساعت ۵ دقیقه توقف و آب خوردن را جدی بگیرید؛ خستگی در ترکینگ از کم‌آبی می‌آید نه از مسافت. یک جفت جوراب اضافه هم نجات‌دهنده است.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_time("نیم روز"), _t_cost("ارزان")]},
    {"title": "قایق‌سواری پارویی در سپیده‌دم",
     "desc": "کایاک را برای اولین سانس صبح رزرو کنید؛ آب آینه‌ای و بی‌موج است. یکی پارو بزند و دیگری مسیر را هدایت کند، بعد جا عوض کنید. نکته‌ی عملی: جلیقه‌ی نجات را حتی اگر شنا بلدید بپوشید و یک بند نگهدارنده برای عینک آفتابی ببندید.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, TAG_SPORT, _t_time("۲ ساعت"), _t_cost("متوسط")]},
    {"title": "بازدید از باغ گیاه‌شناسی و ژورنال طبیعت",
     "desc": "یک باغ گیاه‌شناسی یا گلخانه‌ی بزرگ را انتخاب کنید و هرکدام یک دفتر کوچک ببرید: اسم گیاه، بو، و یک جمله درباره‌اش. نکته: در انتها دفترها را عوض کنید و بلند بخوانید؛ فهمیدن اینکه طرف مقابل چه چیزی را دیده و شما ندیده‌اید، جذاب‌ترین قسمت است.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_ART, _t_time("۳ ساعت"), _t_cost("ارزان")]},
    {"title": "پیک‌نیک شام با فانوس",
     "desc": "به‌جای ناهار، پیک‌نیکِ شام ترتیب بدهید: دو فانوس ال‌ای‌دی، یک سبد غذای گرم در ظرف عایق و موسیقی آرام. نکته‌ی عملی: یک زیرانداز ضدآب و یک پتوی گرم ببرید؛ زمینِ شب سردتر از چیزی است که فکر می‌کنید و همین یک قلم، شب را نجات می‌دهد.",
     "border": (0.910, 0.380, 0.227, 1),
     "tags": [TAG_ROMANTIC, TAG_DUO, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    {"title": "اسب‌سواری در مسیر جنگلی",
     "desc": "این بار به‌جای مانژ، تور سوارکاریِ مسیرِ جنگلی با مربی رزرو کنید. نکته: قبلش نیم‌ساعت پیاده‌روی کنید تا بدنتان گرم شود؛ کمردرد بعد از سواری معمولاً از سرد بودن عضلات می‌آید. بعد از تور، سیب یا هویج به اسب بدهید.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_ADVENT, TAG_EXCITING, _t_time("۳ ساعت"), _t_cost("گران")]},
    {"title": "روستاگردی و خرید محلی",
     "desc": "یک روستای کوهستانی انتخاب کنید، در بازار محلی خرید کنید و ناهار را در خانه‌مسافر بخورید. نکته‌ی عملی: پول نقد ببرید چون بیشتر دستفروش‌های محلی دستگاه کارت ندارند، و برای هر خرید یک سقف بودجه‌ی مشترک بگذارید تا خرید تبدیل به یک بازی شود.",
     "border": (0.565, 0.376, 0.125, 1),
     "tags": [TAG_ADVENT, TAG_DUO, _t_time("یک روز"), _t_cost("متوسط")]},
    {"title": "شکار بارانِ شهابی",
     "desc": "تقویم بارش‌های شهابی (مثل پرسئید در مرداد) را چک کنید و یک شب صاف را برای دیدنش بیرون شهر برنامه‌ریزی کنید. نکته: صندلی تاشوی تختخواب‌شو یا زیرانداز ببرید تا بتوانید دراز بکشید؛ گردن‌درد بزرگ‌ترین دشمن رصد شهابی است.",
     "border": (0.478, 0.188, 0.565, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("۴ ساعت"), _t_cost("ارزان")]},
    {"title": "کوهنوردی تا پناهگاه با چای بعدازظهر",
     "desc": "یک پناهگاه کوهستانیِ در دسترس انتخاب کنید، تا آنجا بالا بروید و بعدازظهر را با چای و بازی ورق در ارتفاع بگذرانید. نکته‌ی عملی: یک لایه‌ی بادگیر سبک ببرید؛ اختلاف دمای دامنه و پناهگاه معمولاً بیشتر از ۸ درجه است.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_SPORT, TAG_DUO, _t_time("نیم روز"), _t_cost("ارزان")]},
]

NATURE_30_35_EXTRA = [
    {"title": "گلمپینگ آخر هفته",
     "desc": "یک اقامتگاه گلمپینگ (کمپینگ لوکس) با چادر مجهز رزرو کنید تا هم طبیعت داشته باشید هم راحتی. نکته‌ی عملی: اقامتگاهی را انتخاب کنید که آشپزخانه‌ی مشترک دارد و یک وعده را خودتان بپزید؛ ترکیب راحتی و کار مشترک بهترین حالت این سفر است.",
     "border": (0.910, 0.380, 0.227, 1), "fav": True,
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("آخر هفته"), _t_cost("گران")]},
    {"title": "سفر جاده‌ای با توقف‌های طبیعی",
     "desc": "یک مسیر ۲۰۰ کیلومتری انتخاب کنید و از قبل چهار نقطه‌ی توقف تعیین کنید: یک چشمه، یک نقطه‌ی منظره، یک کافه‌ی بین‌راهی و یک جنگل. نکته: پلی‌لیست را نفری نصف بسازید و در هر توقف نوبت پخش عوض شود؛ این کوچک‌ترین کار، سفر را دونفره می‌کند.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, TAG_DUO, _t_time("یک روز"), _t_cost("متوسط")]},
    {"title": "پرنده‌نگری تخصصی در تالاب",
     "desc": "یک تالابِ ثبت‌شده را در فصل مهاجرت انتخاب کنید و یک دوربین شکاری ۸x۴۲ کرایه کنید. نکته‌ی عملی: لباس تیره و بی‌صدا بپوشید و در پناهگاه رصد بی‌حرکت بنشینید؛ پرنده‌ها به حرکت حساس‌ترند تا به رنگ. یک چک‌لیست گونه‌ها پرینت کنید.",
     "border": (0.251, 0.376, 0.690, 1),
     "tags": [TAG_CALM, TAG_DUO, _t_time("نیم روز"), _t_cost("متوسط")]},
    {"title": "طبیعت‌درمانی و پیاده‌روی آگاهانه",
     "desc": "یک مسیر جنگلی کوتاه را در دو ساعت طی کنید، اما با قاعده‌ی «هر ۱۰ دقیقه یک توقف پنج‌حسی»: چه می‌بینید، می‌شنوید، می‌بویید، لمس می‌کنید و چه مزه‌ای در دهان دارید. نکته: گوشی‌ها را کامل خاموش کنید؛ حالت سایلنت کافی نیست.",
     "border": (0.357, 0.667, 0.498, 1),
     "tags": [TAG_CALM, TAG_DUO, _t_time("۲ ساعت"), _t_cost("رایگان")]},
    {"title": "پیک‌نیک شرابِ بی‌الکل و پنیر در تاکستان",
     "desc": "یک باغ انگور یا باغ میوه‌ی گردشگری پیدا کنید و بساط تخته‌ی پنیر، میوه‌ی تازه و نوشیدنی خنک راه بیندازید. نکته‌ی عملی: پنیرها را نیم‌ساعت قبل از سرو از کیف خنک دربیاورید؛ پنیرِ هم‌دمای محیط طعمش کاملاً فرق می‌کند.",
     "border": (0.478, 0.188, 0.565, 1),
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("۴ ساعت"), _t_cost("متوسط")]},
    {"title": "کوهنوردی سحرگاهی تا قله‌ی کوچک",
     "desc": "یک قله‌ی محلی با صعود ۳ ساعته انتخاب کنید و طوری حرکت کنید که طلوع را در نیمه‌ی مسیر ببینید. نکته: سرعت را با کندترین نفر تنظیم کنید و هر ۴۵ دقیقه توقفِ ۵ دقیقه‌ای بگذارید؛ هدف رسیدن نیست، رسیدنِ با هم است.",
     "border": (0.180, 0.478, 0.314, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_time("نیم روز"), _t_cost("ارزان")]},
    {"title": "دوچرخه‌سواری بین‌شهری در جاده‌ی سبز",
     "desc": "یک مسیر جاده‌ای کم‌تردد ۳۰ کیلومتری انتخاب کنید و وسط راه در یک روستا ناهار بخورید. نکته‌ی عملی: کیت پنچرگیری، دو تیوب یدک و چراغ عقب فراموش نشود، و مسیر برگشت را با خودرو یا اتوبوس برنامه‌ریزی کنید تا خستگی روز را خراب نکند.",
     "border": (0.788, 0.502, 0.376, 1),
     "tags": [TAG_SPORT, TAG_ADVENT, _t_time("یک روز"), _t_cost("متوسط")]},
    {"title": "شب‌مانی در کلبه‌ی جنگلی",
     "desc": "یک کلبه‌ی چوبی در جنگل برای یک شب اجاره کنید، شومینه روشن کنید و شام را با هم بپزید. نکته: از قبل مطمئن شوید کلبه هیزم دارد و اگر ندارد از روستای مسیر بخرید؛ دنبال هیزم گشتن در تاریکی، بدترین شروع ممکن برای شب است.",
     "border": (0.565, 0.376, 0.125, 1),
     "tags": [TAG_ROMANTIC, TAG_CALM, _t_time("یک شب"), _t_cost("گران")]},
    {"title": "آبشارگردیِ دو مقصدی با پیاده‌روی طولانی",
     "desc": "دو آبشار در یک دره را با مسیرِ پیاده‌رویِ بین‌شان انتخاب کنید و کل روز را در دره بگذرانید. نکته‌ی عملی: ساعت برگشت را طوری بچینید که حداقل یک ساعت قبل از غروب از دره بیرون باشید؛ تاریکیِ دره خیلی زودتر از شهر می‌رسد.",
     "border": (0.345, 0.537, 0.800, 1),
     "tags": [TAG_ADVENT, TAG_SPORT, _t_time("یک روز"), _t_cost("متوسط")]},
]


def get_nature_ideas(age):
    """ایده‌های «طبیعت‌گردی» — همه‌ی بازه‌های سنی برای همه نمایش داده می‌شه،
    و کنار هر ایده تگ بازه‌ی سنیِ مربوطه می‌خوره."""
    return (_tag_ideas(NATURE_15_20, TAG_AGE_15_20)
            + _tag_ideas(NATURE_20_25_EXTRA, TAG_AGE_20_25)
            + _tag_ideas(NATURE_25_30_EXTRA, TAG_AGE_25_30)
            + _tag_ideas(NATURE_30_35_EXTRA, TAG_AGE_30_35))


IDEAS = {
    "active": [],  # ← به‌صورت پویا با get_active_ideas(age) پر می‌شه
    "creative": [
        {"title": "نقاشی روی بوم دونفره",
     "desc": "یه بوم بگیرید و هر کدوم نصفشو نقاشی کنید. آخرش کنار هم بذارید! قبل از شروع، یه تم مشترک انتخاب کنید (مثلاً «صبح»، «شهر»، «رویا»). قانون کار اینه که در طول کار به بومِ همدیگه نگاه نکنید تا در انتها که کنار هم بذاریدشون، تفاوتِ نگاهِ دو نفر به یک تم خودش تبدیل به یه اثرِ سومِ خیالی بشه.",
         "border": (0.608, 0.427, 0.816, 1),
         "tags": [TAG_ART, _t_time("۲ ساعت"), _t_cost("ارزان")]},
        {"title": "ساخت سفالگری",
     "desc": "یه کلاس سفالگری دونفره برید و هر کدوم یه ظرف برای اون یکی بسازید. در انتخاب کلاس، حتماً کلاسی رو بردارید که چرخِ سفال داره و فقط دستی نیست. هر کدوم برای طرفِ مقابل یه ظرفِ متناسب با علاقه‌اش بسازید (مثلاً ماگِ قهوه اگه پارتنر قهوه‌خوره). یادتون باشه بعد از خشک شدنِ گل و لعاب‌کاری، حداقل یک هفته منتظر تحویل بمونید — این هیجانِ انتظار هم بخشی از دیته.",
         "border": (0.788, 0.502, 0.376, 1),
         "tags": [TAG_CREATIVE, _t_time("۲ ساعت"), _t_cost("متوسط")]},
        {"title": "عکاسی خیابانی",
     "desc": "با دوربین یا گوشی یه روز عکاس همدیگه باشید و خاطره بسازید. قانون این باشه که فقط پرتره‌های صریح از هم نگیرید — یاد بگیرید هر عکس یه فِرمِ اضافه هم داشته باشه (بازتاب در شیشه، سایه روی زمین، عابرِ محو در پس‌زمینه). در انتهای روز پنج عکسِ برتر رو انتخاب و پرینت کنید.",
         "border": (0.345, 0.537, 0.800, 1),
         "tags": [TAG_ART, _t_time("۳ ساعت"), _t_cost("رایگان")]},
    ],
    "food": [
        {"title": "شام در رستوران رمانتیک",
     "desc": "یه رستوران با نور شمع رزرو کنید و یه شب خاص بسازید. از قبل با رستوران هماهنگ کنید که میزی نزدیک پنجره یا در یه گوشه‌ی خلوت‌تر رزرو شه. لباس‌های نیمه‌رسمی بپوشید و شرط این باشه که در طول شام گوشی‌ها در کیف بمونن — یه شب کاملاً بی‌ حواس‌پرتی.",
         "border": (0.910, 0.380, 0.227, 1), "fav": True,
         "tags": [TAG_ROMANTIC, _t_time("۲ ساعت"), _t_cost("گران")]},
        {"title": "صبحانه در کافه",
     "desc": "یه صبح زود بیدار شید و برید یه کافه دنج صبحانه بخورید. قبلش دو تا کافه رو در نقشه علامت بزنید و اون روزی که رفتید، شرط این باشه که فقط بر اساس عطرِ ورودی کافه انتخاب کنید کدوم رو بمونید. سفارشِ همدیگه رو انتخاب کنید — بدون مشورت.",
         "border": (0.357, 0.667, 0.498, 1),
         "tags": [TAG_CALM, _t_time("۱ ساعت"), _t_cost("متوسط")]},
        {"title": "تور غذای خیابانی",
     "desc": "یه مسیر مشخص کنید و از چند جای مختلف غذا تست کنید. مسیر رو از قبل روی نقشه بکشید و برای هر ایستگاه یه بودجه‌ی محدود در نظر بگیرید. قانون: هیچ غذایی نباید تکراری باشه، و در هر ایستگاه باید یه چیز رو با فروشنده به فارسی چاق سلامتی کنید — این تعامل نصف لذتِ تور رو می‌سازه.",
         "border": (0.788, 0.502, 0.376, 1),
         "tags": [TAG_ADVENT, _t_time("۳ ساعت"), _t_cost("متوسط")]},
    ],
    "nature": [],  # ← به‌صورت پویا با get_nature_ideas(age) پر می‌شه
    "home": [],  # ← به‌صورت پویا با get_home_ideas(age) پر می‌شه
}


# ---------------------------------------------------------------------------
# شناسه دستگاه
# ---------------------------------------------------------------------------
def get_device_id(username: str = "") -> str:
    """شناسه‌ی دستگاه.

    اگر username داده شود، شناسه از فایل <storage_folder>/device_id.txt همان
    اکانت خوانده/ساخته می‌شود (هر اکانت شناسه‌ی خودش را دارد و چیزی بیرون از
    پوشه‌اش نوشته نمی‌شود). بدون username، فایل سراسری SAVE_DIR استفاده می‌شود.
    """
    base_id = ""
    try:
        from jnius import autoclass
        Secure = autoclass('android.provider.Settings$Secure')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        context = PythonActivity.mActivity.getApplicationContext()
        android_id = Secure.getString(context.getContentResolver(), Secure.ANDROID_ID)
        if android_id:
            base_id = str(android_id)
    except Exception:
        pass
    if not base_id:
        try:
            base_id = f"{platform.node()}-{uuid.getnode()}"
        except Exception:
            base_id = str(uuid.getnode())

    try:
        if username:
            folder = account_folder(username)
            if _is_saf(folder):
                if _saf_ready(folder):
                    existing = (_saf_read_text(folder, "device_id.txt") or "").strip()
                    if existing:
                        return existing
                    _saf_write_text(folder, "device_id.txt", base_id)
                return base_id
            dev_file = os.path.join(folder, "device_id.txt")
        else:
            dev_file = DEVICE_FILE
        if os.path.exists(dev_file):
            with open(dev_file, "r", encoding="utf-8") as f:
                did = f.read().strip()
                if did:
                    return did
        os.makedirs(os.path.dirname(dev_file) or SAVE_DIR, exist_ok=True)
        with open(dev_file, "w", encoding="utf-8") as f:
            f.write(base_id)
    except Exception:
        pass
    return base_id


# ---------------------------------------------------------------------------
# مدیریت دیتابیس
# ساختار اکانت:
# {
#   username, password, phone, age, gender, avatar,
#   partner: "",        # نام کاربری همدم
#   link_code: "",      # کدی که خودش ساخته
#   link_role: ""       # "owner" (لینک ساخته) یا "joiner" (با کد وصل شده)
# }
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# تنظیمات محلی برنامه (کنار SAVE_FILE) — برای به‌خاطرسپاری آخرین مسیر ذخیره‌سازی
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# تنظیمات محلی برنامه — کاملاً در حافظه (In-memory)
# هیچ فایل تنظیماتی روی دیسک نوشته نمی‌شود. «آخرین مسیر ذخیره‌سازی» فقط تا پایان
# همین اجرای برنامه به‌خاطر می‌ماند تا ساخت اکانت بعدی راحت‌تر باشد.
# ---------------------------------------------------------------------------
_RUNTIME_SETTINGS = {}


def load_settings() -> dict:
    """تنظیمات موقتِ همین اجرا (سازگار با امضای قبلی؛ بدون فایل)."""
    return dict(_RUNTIME_SETTINGS)


def save_settings(data: dict):
    """ذخیره‌ی تنظیمات فقط در حافظه (بدون نوشتن روی دیسک)."""
    try:
        _RUNTIME_SETTINGS.clear()
        _RUNTIME_SETTINGS.update(data or {})
    except Exception as e:
        print(f"[Settings] خطا: {e}")


def get_last_storage_path() -> str:
    return (_RUNTIME_SETTINGS.get("last_storage_path") or "").strip()


def set_last_storage_path(path: str):
    _RUNTIME_SETTINGS["last_storage_path"] = path or ""


def _active_storage_dir() -> str:
    """مسیر پایه‌ای که کاربر آخرین بار (در همین اجرا) انتخاب کرده است."""
    p = get_last_storage_path()
    if p and not p.startswith("content://"):
        try:
            os.makedirs(p, exist_ok=True)
            return p
        except Exception:
            pass
    return SAVE_DIR


# ---------------------------------------------------------------------------
# معماری ذخیره‌سازی: «هر اکانت یک پوشه»
# همه‌ی داده‌های یک اکانت (account.json, device_id.txt, recovery_key.txt,
# avatar/, memories/, personal_ideas.json, done_ideas.json, diary_notes.json)
# فقط داخل پوشه‌ی انتخابیِ خود کاربر نوشته می‌شوند.
# تنها استثنا: known_accounts.json — یک لوکیتورِ حداقلی با ساختار
# {"username": "storage_folder_path"} و بدون هیچ داده‌ی حساس، که فقط برای
# «ورود با نام‌کاربری/رمز بدون انتخاب دستیِ پوشه» لازم است.
# ---------------------------------------------------------------------------

KNOWN_ACCOUNTS_FILE = os.path.join(SAVE_DIR, "known_accounts.json")
RECOVERY_FILENAME = "recovery_key.txt"
ACCOUNT_FILENAME = "account.json"
_LOCAL_ACCOUNTS_DIR = os.path.join(SAVE_DIR, "accounts")


# ---------------------------------------------------------------------------
# SAF (Storage Access Framework) — نوشتن/خواندن واقعی داخل پوشه‌ی انتخابیِ کاربر
# روی اندروید. اگر pyjnius/کلاس‌های اندروید در دسترس نباشند (دسکتاپ)، همه‌ی
# توابع None/False برمی‌گردانند و caller به رفتار قبلی (fallback محلی) برمی‌گردد.
# ---------------------------------------------------------------------------
_SAF_CACHE = {}


def _is_saf(path: str) -> bool:
    return bool(path) and str(path).startswith("content://")


def _saf_env():
    """(autoclass, cast, activity, resolver, DocumentFile, Uri) یا None."""
    if "env" in _SAF_CACHE:
        return _SAF_CACHE["env"]
    env = None
    try:
        from jnius import autoclass, cast  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        Uri = autoclass("android.net.Uri")
        DocumentFile = None
        for cls in ("androidx.documentfile.provider.DocumentFile",
                    "android.support.v4.provider.DocumentFile"):
            try:
                DocumentFile = autoclass(cls)
                break
            except Exception:
                continue
        if DocumentFile is not None:
            env = (autoclass, cast, activity, resolver, DocumentFile, Uri)
    except Exception as e:
        print(f"[SAF][env] unavailable: {type(e).__name__}: {e}")
        env = None
    _SAF_CACHE["env"] = env
    return env


def _saf_doc(uri_str: str):
    """DocumentFile مربوط به یک tree/document URI."""
    env = _saf_env()
    if not env or not _is_saf(uri_str):
        return None
    _autoclass, _cast, activity, _resolver, DocumentFile, Uri = env
    uri = Uri.parse(uri_str)
    doc = None
    try:
        doc = DocumentFile.fromTreeUri(activity, uri)
    except Exception:
        doc = None
    if doc is None:
        try:
            doc = DocumentFile.fromSingleUri(activity, uri)
        except Exception:
            doc = None
    return doc


def _saf_find_child(parent_doc, name: str):
    try:
        child = parent_doc.findFile(name)
        return child
    except Exception:
        return None


def _saf_ensure_dir(parent_uri: str, name: str) -> str:
    """ساخت (یا پیداکردنِ) زیرپوشه داخل tree URI. URI پوشه یا "" برمی‌گرداند."""
    doc = _saf_doc(parent_uri)
    if doc is None:
        return ""
    try:
        child = _saf_find_child(doc, name)
        if child is None or not child.isDirectory():
            child = doc.createDirectory(name)
        if child is None:
            return ""
        return child.getUri().toString()
    except Exception as e:
        print(f"[SAF][mkdir] {type(e).__name__}: {e}")
        return ""


def _saf_ensure_path(base_uri: str, *names) -> str:
    cur = base_uri
    for n in names:
        if not n:
            continue
        cur = _saf_ensure_dir(cur, n)
        if not cur:
            return ""
    return cur


def _saf_write_bytes(dir_uri: str, filename: str, data: bytes,
                     mime: str = "application/octet-stream") -> str:
    """ساخت/بازنویسی فایل داخل پوشه‌ی SAF. URI فایل یا "" برمی‌گرداند."""
    env = _saf_env()
    doc = _saf_doc(dir_uri)
    if not env or doc is None:
        return ""
    _autoclass, _cast, _activity, resolver, _DocumentFile, _Uri = env
    try:
        child = _saf_find_child(doc, filename)
        if child is None:
            child = doc.createFile(mime, filename)
        if child is None:
            return ""
        stream = resolver.openOutputStream(child.getUri(), "wt")
        if stream is None:
            return ""
        try:
            stream.write(bytearray(data))
            stream.flush()
        finally:
            try:
                stream.close()
            except Exception:
                pass
        return child.getUri().toString()
    except Exception as e:
        print(f"[SAF][write] {type(e).__name__}: {e}")
        return ""


def _saf_write_text(dir_uri: str, filename: str, text: str,
                    mime: str = "text/plain") -> str:
    return _saf_write_bytes(dir_uri, filename, (text or "").encode("utf-8"), mime)


def _saf_read_bytes(dir_uri: str, filename: str):
    env = _saf_env()
    doc = _saf_doc(dir_uri)
    if not env or doc is None:
        return None
    _autoclass, _cast, _activity, resolver, _DocumentFile, _Uri = env
    try:
        child = _saf_find_child(doc, filename)
        if child is None or not child.exists():
            return None
        stream = resolver.openInputStream(child.getUri())
        if stream is None:
            return None
        out = bytearray()
        try:
            buf = bytearray(8192)
            while True:
                n = stream.read(buf)
                if n is None or n <= 0:
                    break
                out.extend(buf[:n])
        finally:
            try:
                stream.close()
            except Exception:
                pass
        return bytes(out)
    except Exception as e:
        print(f"[SAF][read] {type(e).__name__}: {e}")
        return None


def _saf_read_text(dir_uri: str, filename: str) -> str:
    data = _saf_read_bytes(dir_uri, filename)
    if data is None:
        return ""
    try:
        return data.decode("utf-8")
    except Exception:
        return ""


def _saf_copy_into(dir_uri: str, filename: str, src_path: str) -> str:
    """کپی یک فایل محلی (عکس آواتار/خاطره) داخل پوشه‌ی SAF."""
    try:
        with open(src_path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"[SAF][copy] read src: {e}")
        return ""
    ext = (os.path.splitext(filename)[1] or "").lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "application/octet-stream")
    return _saf_write_bytes(dir_uri, filename, data, mime)


def _saf_delete_tree(dir_uri: str) -> bool:
    doc = _saf_doc(dir_uri)
    if doc is None:
        return False
    try:
        return bool(doc.delete())
    except Exception as e:
        print(f"[SAF][delete] {type(e).__name__}: {e}")
        return False


def _saf_ready(uri: str) -> bool:
    """آیا واقعاً می‌توان روی این URI با SAF کار کرد؟"""
    return _is_saf(uri) and _saf_doc(uri) is not None


def make_user_folder(base_path: str, username: str) -> str:
    """داخل مسیر انتخاب‌شده یک پوشه به نام کاربر می‌سازد و مسیر کامل را برمی‌گرداند.

    مسیرهای content:// (SAF اندروید) با os.makedirs قابل ساخت نیستند و نیاز به
    DocumentsContract/DocumentFile دارند؛ در آن حالت مسیر منطقی برگردانده می‌شود
    و caller (create_account) به پوشه‌ی محلیِ اکانت سوییچ می‌کند.
    """
    if not base_path or not username:
        return base_path or ""
    if _is_saf(base_path):
        # SAF: واقعاً یک زیرپوشه به نام کاربر داخل درختِ انتخابی ساخته می‌شود.
        child = _saf_ensure_dir(base_path, username)
        if child:
            # زیرپوشه‌های استاندارد اکانت هم همان‌جا ساخته می‌شوند.
            _saf_ensure_dir(child, "avatar")
            _saf_ensure_dir(child, "memories")
            return child
        return base_path.rstrip("/") + "/" + username
    try:
        full = os.path.join(base_path, username)
        os.makedirs(full, exist_ok=True)
        return full
    except Exception as e:
        print(f"[make_user_folder] خطا: {e}")
        return base_path


def _safe_name(username: str) -> str:
    return "".join(ch for ch in (username or "") if ch.isalnum() or ch in "_-") or "user"


def _read_known_accounts() -> dict:
    """لوکیتورِ حداقلی: {username: storage_folder}. هیچ داده‌ی حساسی ندارد."""
    out = {}
    try:
        if os.path.exists(KNOWN_ACCOUNTS_FILE):
            with open(KNOWN_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str) and k and v:
                        out[k] = v
    except Exception as e:
        print(f"[known_accounts] {e}")
    return out


def _write_known_accounts(mapping: dict):
    """نوشتن لوکیتور (فقط نگاشت نام‌کاربری → مسیر پوشه)."""
    clean = {}
    for k, v in (mapping or {}).items():
        if isinstance(k, str) and isinstance(v, str) and k and v:
            clean[k] = v
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(KNOWN_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[known_accounts] خطا: {e}")
    # تلاشِ اختیاری: یک کپی از همین لوکیتور کنارِ آخرین پوشه‌ی استفاده‌شده
    try:
        base = _active_storage_dir()
        if base and os.path.normpath(base) != os.path.normpath(SAVE_DIR):
            with open(os.path.join(base, "known_accounts.json"), "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _discover_account_folders() -> dict:
    """کشفِ پوشه‌های اکانت: لوکیتور + پوشه‌ی محلیِ اکانت‌ها + آخرین مسیر انتخابی."""
    folders = dict(_read_known_accounts())
    search_bases = [_LOCAL_ACCOUNTS_DIR, _active_storage_dir()]
    for base in search_bases:
        try:
            if not base or base.startswith("content://") or not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                sub = os.path.join(base, name)
                if not os.path.isdir(sub):
                    continue
                if os.path.exists(os.path.join(sub, ACCOUNT_FILENAME)):
                    acc = read_account_file(sub)
                    uname = (acc.get("username") or "").strip()
                    if uname and uname not in folders:
                        folders[uname] = sub
        except Exception:
            continue
    return folders


def load_index() -> dict:
    """ایندکس مجازی (سازگار با امضای قبلی).

    فقط «folders» واقعاً روی دیسک ذخیره می‌شود؛ device_sessions و link_codes
    از روی همان account.json داخل پوشه‌ی هر اکانت بازسازی می‌شوند.
    """
    data = {"folders": _discover_account_folders(),
            "device_sessions": {}, "link_codes": {}}
    for uname, folder in list(data["folders"].items()):
        acc = read_account_file(folder)
        if not acc:
            continue
        did = (acc.get("device_id") or "").strip()
        if did:
            data["device_sessions"][did] = uname
        code = (acc.get("link_code") or "").strip()
        if code:
            data["link_codes"][code] = uname
    return data


def save_index(idx: dict):
    """فقط نگاشتِ نام‌کاربری → پوشه ذخیره می‌شود (بدون داده‌ی حساس)."""
    _write_known_accounts((idx or {}).get("folders", {}) or {})



def default_account_folder(username: str) -> str:
    """پوشه‌ی پیش‌فرض اکانت وقتی کاربر پوشه‌ای انتخاب نکرده باشد."""
    return os.path.join(_LOCAL_ACCOUNTS_DIR, _safe_name(username))


def account_folder(username: str) -> str:
    """پوشه‌ی اختصاصی یک اکانت (از ایندکس؛ در نبود آن مسیر پیش‌فرض)."""
    if not username:
        return default_account_folder("_guest")
    folder = (_read_known_accounts().get(username) or "").strip()
    if not folder:
        folder = (_discover_account_folders().get(username) or "").strip()
    if not folder:
        folder = default_account_folder(username)
    if not folder.startswith("content://"):
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
    return folder


def register_account_folder(username: str, folder: str):
    """ثبت/به‌روزرسانی نگاشت نام‌کاربری → پوشه در لوکیتورِ حداقلی."""
    if not username or not folder:
        return
    mapping = _read_known_accounts()
    mapping[username] = folder
    _write_known_accounts(mapping)



def read_account_file(folder: str) -> dict:
    """خواندن account.json از یک پوشه (بدون نیاز به ایندکس)."""
    try:
        if not folder:
            return {}
        if _is_saf(folder):
            raw = _saf_read_text(folder, ACCOUNT_FILENAME)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("username"):
                    return data
            return {}
        path = os.path.join(folder, ACCOUNT_FILENAME)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("username"):
                    return data
    except Exception as e:
        print(f"[read_account_file] {e}")
    return {}


def write_account_file(acc: dict) -> str:
    """نوشتن رکورد کامل اکانت داخل پوشه‌ی خودش. مسیر پوشه برگردانده می‌شود."""
    username = (acc.get("username") or "").strip()
    if not username:
        return ""
    folder = (acc.get("storage_folder") or "").strip() or account_folder(username)
    if _is_saf(folder):
        # SAF: فایل واقعاً داخل همان پوشه‌ی انتخابیِ کاربر نوشته می‌شود.
        if _saf_ready(folder):
            try:
                acc["storage_folder"] = folder
                payload = json.dumps(acc, ensure_ascii=False, indent=2)
                if _saf_write_text(folder, ACCOUNT_FILENAME, payload, "application/json"):
                    return folder
                print("[write_account_file] نوشتن SAF ناموفق بود؛ پوشه‌ی محلی استفاده می‌شود.")
            except Exception as e:
                print(f"[write_account_file][SAF] {type(e).__name__}: {e}")
        else:
            print("[write_account_file] SAF در دسترس نیست؛ از پوشه‌ی محلی اکانت استفاده می‌شود.")
        folder = default_account_folder(username)
    try:
        os.makedirs(folder, exist_ok=True)
        acc["storage_folder"] = folder
        with open(os.path.join(folder, ACCOUNT_FILENAME), "w", encoding="utf-8") as f:
            json.dump(acc, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[write_account_file] خطا: {e}")
    return folder


def _migrate_legacy_db(idx: dict) -> bool:
    """مهاجرت یک‌باره از فایل‌های سراسریِ قدیمی به مدل «هر اکانت یک پوشه».

    user_data.json و accounts_index.json و app_settings.json قدیمی خوانده و
    بایگانی می‌شوند؛ داده‌ی هر اکانت داخل پوشه‌ی خودش نوشته می‌شود.
    """
    changed = False
    legacy_index = os.path.join(SAVE_DIR, "accounts_index.json")
    try:
        if os.path.exists(legacy_index):
            with open(legacy_index, "r", encoding="utf-8") as f:
                old = json.load(f) or {}
            for uname, folder in (old.get("folders") or {}).items():
                if uname and folder and uname not in idx["folders"]:
                    idx["folders"][uname] = folder
                    changed = True
            # انتقال سشن‌ها/کدها به داخل account.json خودِ اکانت‌ها
            for did, uname in (old.get("device_sessions") or {}).items():
                acc = read_account_file(idx["folders"].get(uname, ""))
                if acc and not acc.get("device_id"):
                    acc["device_id"] = did
                    write_account_file(acc)
            for code, uname in (old.get("link_codes") or {}).items():
                acc = read_account_file(idx["folders"].get(uname, ""))
                if acc and not acc.get("link_code"):
                    acc["link_code"] = code
                    write_account_file(acc)
            try:
                os.rename(legacy_index, legacy_index + ".legacy")
            except Exception:
                pass
    except Exception as e:
        print(f"[migrate-index] {e}")

    for legacy_settings in (os.path.join(SAVE_DIR, "app_settings.json"),):
        try:
            if os.path.exists(legacy_settings):
                os.rename(legacy_settings, legacy_settings + ".legacy")
        except Exception:
            pass

    legacy_files = [SAVE_FILE, os.path.join(_active_storage_dir(), "user_data.json")]
    for lf in legacy_files:
        try:
            if not lf or not os.path.exists(lf):
                continue
            with open(lf, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            for uname, acc in (data.get("accounts") or {}).items():
                if not isinstance(acc, dict) or uname in idx["folders"]:
                    continue
                folder = (acc.get("storage_folder") or "").strip()
                if not folder or folder.startswith("content://"):
                    folder = default_account_folder(uname)
                acc["username"] = uname
                acc["storage_folder"] = folder
                for did, u2 in (data.get("device_sessions") or {}).items():
                    if u2 == uname and not acc.get("device_id"):
                        acc["device_id"] = did
                for code, u3 in (data.get("link_codes") or {}).items():
                    if u3 == uname and not acc.get("link_code"):
                        acc["link_code"] = code
                write_account_file(acc)
                idx["folders"][uname] = folder
                changed = True
            try:
                os.rename(lf, lf + ".legacy")
            except Exception:
                pass
        except Exception as e:
            print(f"[migrate] {e}")
    return changed



def load_db() -> dict:
    """دیتابیس مجازی: اکانت‌ها از account.json پوشه‌های شناخته‌شده خوانده می‌شوند."""
    idx = {"folders": _discover_account_folders()}
    if _migrate_legacy_db(idx):
        _write_known_accounts(idx["folders"])
    accounts = {}
    stale = []
    known = _read_known_accounts()
    for uname, folder in list(idx.get("folders", {}).items()):
        acc = read_account_file(folder)
        if acc:
            acc["storage_folder"] = folder
            accounts[uname] = acc
        else:
            stale.append(uname)
    # پوشه‌هایی که دیگر وجود ندارند از لوکیتور حذف می‌شوند
    dirty = False
    for uname in stale:
        if uname in known:
            known.pop(uname, None)
            dirty = True
    for uname, folder in idx.get("folders", {}).items():
        if uname in accounts and known.get(uname) != folder:
            known[uname] = folder
            dirty = True
    if dirty:
        _write_known_accounts(known)

    device_sessions = {}
    link_codes = {}
    for uname, acc in accounts.items():
        did = (acc.get("device_id") or "").strip()
        if did:
            device_sessions[did] = uname
        code = (acc.get("link_code") or "").strip()
        if code:
            link_codes[code] = uname
    return {
        "accounts": accounts,
        "device_sessions": device_sessions,
        "link_codes": link_codes,
    }


def save_db(db: dict):
    """ذخیره: هر اکانت فقط داخل پوشه‌ی خودش + به‌روزرسانی لوکیتورِ حداقلی.

    device_sessions و link_codes جای مستقلی روی دیسک ندارند؛ آن‌ها از فیلدهای
    device_id / link_code همان account.json ساخته می‌شوند.
    """
    try:
        known = _read_known_accounts()
        folders = {}
        sessions = db.get("device_sessions") or {}
        codes = db.get("link_codes") or {}
        for uname, acc in (db.get("accounts") or {}).items():
            if not isinstance(acc, dict):
                continue
            acc["username"] = uname
            if not (acc.get("storage_folder") or "").strip():
                acc["storage_folder"] = known.get(uname) or default_account_folder(uname)
            # همگام‌سازی سشن/کد لینک روی خودِ رکورد اکانت
            for did, u2 in sessions.items():
                if u2 == uname:
                    acc["device_id"] = did
            my_codes = [c for c, u3 in codes.items() if u3 == uname]
            if my_codes:
                acc["link_code"] = my_codes[0]
            folder = write_account_file(acc)
            if folder:
                folders[uname] = folder
        _write_known_accounts(folders)
    except Exception as e:
        print(f"[Save] خطا: {e}")



def username_exists(username: str) -> bool:
    db = load_db()
    return username in db.get("accounts", {})


def get_account(username: str) -> dict:
    db = load_db()
    return db.get("accounts", {}).get(username, {})


def _is_valid_username(s: str) -> bool:
    s = (s or "").strip()
    if not s or len(s) < 3:
        return False
    if " " in s:
        return False
    return True


def create_account(username: str, password: str, age: int, gender: str,
                   storage_path: str = "", full_name: str = "") -> tuple:
    """اکانت ساخته می‌شود و بلافاصله پوشه‌ی اختصاصی‌اش (به همراه account.json و
    device_id.txt) ایجاد می‌شود."""
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    if not _is_valid_username(username):
        return False, "نام کاربری باید حداقل ۳ کاراکتر و بدون فاصله باشد"
    db = load_db()
    if username in db["accounts"]:
        return False, "این نام کاربری قبلاً ثبت شده؛ از صفحه ورود استفاده کن"
    folder = make_user_folder(storage_path, username) if storage_path else ""
    if _is_saf(folder) and not _saf_ready(folder):
        print("[create_account] هشدار: SAF در دسترس نیست؛ "
              "داده‌ها در پوشه‌ی محلی اکانت ذخیره می‌شوند.")
        folder = ""
    if not folder:
        folder = default_account_folder(username)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
    recovery_key = generate_recovery_key()
    db["accounts"][username] = {
        "username": username,
        "full_name": full_name,
        "password": password,
        "phone": "",
        "age": age,
        "gender": gender,
        "avatar": "",
        "partner": "",
        "link_code": "",
        "link_role": "",
        "memories": {},
        "storage_path": storage_path or "",
        "storage_uri": storage_path or "",
        "storage_folder": folder,
        "recovery_key": recovery_key,
    }
    register_account_folder(username, folder)
    save_db(db)
    # ذخیره‌ی ریکاوری‌کی در فایل متنی داخل همان پوشه‌ی اکانت
    try:
        write_recovery_key_file(username, recovery_key)
    except Exception as e:
        print(f"[create_account] recovery: {e}")
    # ساخت device_id مخصوص همین اکانت داخل پوشه‌ی خودش
    try:
        get_device_id(username)
    except Exception:
        pass
    return True, "اکانت با موفقیت ساخته شد"


def verify_login(username: str, password: str, age: int, gender: str) -> tuple:
    """ورود با نام کاربری + رمز عبور + جنسیت + سن."""
    username = (username or "").strip()
    db = load_db()
    acc = db["accounts"].get(username)
    if not acc:
        return False, "نام کاربری‌ای با این مشخصات یافت نشد", None
    if (acc.get("password") or "") != (password or ""):
        return False, "رمز عبور اشتباه است", None
    if int(acc.get("age", -1)) != int(age):
        return False, "سن با اطلاعات اکانت مطابقت ندارد", None
    if acc.get("gender") != gender:
        return False, "جنسیت با اطلاعات اکانت مطابقت ندارد", None
    return True, "ورود موفق", acc


def set_session(username: str):
    db = load_db()
    did = get_device_id(username)
    db["device_sessions"][did] = username
    acc = db["accounts"].get(username)
    if isinstance(acc, dict):
        acc["device_id"] = did
    save_db(db)


def clear_session():
    """پاک کردن سشن این دستگاه — فقط با بازنویسی account.json خودِ اکانت‌ها."""
    db = load_db()
    changed = False
    for uname, acc in (db.get("accounts") or {}).items():
        did = (acc.get("device_id") or "").strip()
        if did and did == get_device_id(uname):
            acc["device_id"] = ""
            db["device_sessions"].pop(did, None)
            changed = True
    if changed:
        save_db(db)


def get_session_username() -> str:
    """پیمایش پوشه‌های شناخته‌شده و مقایسه‌ی device_id داخل account.json."""
    db = load_db()
    for uname, acc in (db.get("accounts") or {}).items():
        try:
            did = (acc.get("device_id") or "").strip()
            if did and did == get_device_id(uname):
                return uname
        except Exception:
            continue
    return ""


# ---------------------------------------------------------------------------
# ریکاوری‌کی (بازیابی رمز عبور)
# ---------------------------------------------------------------------------
def generate_recovery_key(length: int = 24) -> str:
    """کد تصادفی ۲۴ کاراکتری (حروف بزرگ/کوچک + عدد) — مثل الگوی generate_link_code."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def write_recovery_key_file(username: str, key: str) -> str:
    """نوشتن recovery_key.txt داخل پوشه‌ی همان اکانت. مسیر فایل برگردانده می‌شود."""
    if not username or not key:
        return ""
    folder = account_folder(username)
    if _is_saf(folder):
        if _saf_ready(folder):
            uri = _saf_write_text(folder, RECOVERY_FILENAME, key)
            if uri:
                return uri
        folder = default_account_folder(username)
    if not folder:
        folder = default_account_folder(username)
    try:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, RECOVERY_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            f.write(key)
        return path
    except Exception as e:
        print(f"[recovery_key] خطا: {e}")
        return ""


def get_recovery_key(username: str) -> str:
    """ریکاوری‌کیِ اکانت؛ اگر داخل account.json نبود از فایل خوانده می‌شود."""
    acc = get_account(username) or {}
    key = (acc.get("recovery_key") or "").strip()
    if key:
        return key
    try:
        folder = account_folder(username)
        path = os.path.join(folder, RECOVERY_FILENAME)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def find_account_by_recovery_key(key: str) -> tuple:
    """در بین همه‌ی اکانت‌های شناخته‌شده می‌گردد و (username, account_dict) را
    برای کدِ ریکاوری منطبق برمی‌گرداند؛ اگر پیدا نشد ("", {})."""
    key = (key or "").strip()
    if not key:
        return "", {}
    db = load_db()
    for uname, acc in (db.get("accounts") or {}).items():
        stored = (acc.get("recovery_key") or "").strip()
        if not stored:
            # سازگاری با اکانت‌هایی که فقط فایل متنی دارند
            try:
                path = os.path.join(acc.get("storage_folder") or "", RECOVERY_FILENAME)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        stored = f.read().strip()
                    if stored:
                        acc["recovery_key"] = stored
                        write_account_file(acc)
            except Exception:
                stored = ""
        if stored and stored == key:
            return uname, dict(acc)
    return "", {}


def change_password_by_recovery_key(key: str, new_password: str) -> tuple:
    """تغییر رمز عبور با ریکاوری‌کی. خروجی: (ok, message, username)."""
    new_password = (new_password or "").strip()
    if not new_password:
        return False, "رمز جدید را وارد کنید", ""
    uname, acc = find_account_by_recovery_key(key)
    if not uname or not acc:
        return False, "ریکاوری‌کی نامعتبر است", ""
    if (acc.get("password") or "") == new_password:
        return False, "رمز جدید نباید با رمز قبلی یکسان باشد", uname
    acc["password"] = new_password
    write_account_file(acc)
    return True, "رمز عبور با موفقیت تغییر کرد", uname



def generate_link_code(username: str) -> str:
    db = load_db()
    acc = db["accounts"].get(username)
    if not acc:
        return ""

    old = acc.get("link_code", "")
    if old and old in db.get("link_codes", {}):
        del db["link_codes"][old]

    chars = string.ascii_letters + string.digits
    while True:
        code = "".join(random.choice(chars) for _ in range(11))
        if code not in db.get("link_codes", {}):
            break

    db["link_codes"][code] = username
    db["accounts"][username]["link_code"] = code
    save_db(db)
    return code


def connect_partner(my_username: str, code: str) -> tuple:
    db = load_db()
    me = db["accounts"].get(my_username)
    if not me:
        return False, "اکانت شما یافت نشد", None

    code = (code or "").strip()
    if not code:
        return False, "لطفاً کد همدم را وارد کنید", None

    owner = db.get("link_codes", {}).get(code)
    if not owner:
        return False, "کد نامعتبر است یا منقضی شده", None

    if owner == my_username:
        return False, "نمی‌توانی کد خودت را وارد کنی", None

    partner = db["accounts"].get(owner)
    if not partner:
        return False, "صاحب این کد یافت نشد", None

    if me.get("partner"):
        return False, "تو قبلاً با یک نفر همدم شده‌ای", None
    if partner.get("partner"):
        return False, "این کاربر قبلاً با شخص دیگری همدم شده", None

    if me.get("gender") == partner.get("gender"):
        return False, "همدم باید یک دختر و یک پسر باشند", None

    # اتصال دوطرفه با تعیین نقش‌ها
    db["accounts"][my_username]["partner"] = owner
    db["accounts"][my_username]["link_role"] = "joiner"   # با کد وصل شده
    db["accounts"][owner]["partner"] = my_username
    db["accounts"][owner]["link_role"] = "owner"          # لینک ساخته

    if code in db["link_codes"]:
        del db["link_codes"][code]
    db["accounts"][owner]["link_code"] = ""
    db["accounts"][my_username]["link_code"] = ""

    save_db(db)
    return True, "اکانت‌ها با موفقیت همدم شدند 💞", owner


def get_partner_account(username: str) -> dict:
    db = load_db()
    me = db["accounts"].get(username, {})
    p = me.get("partner", "")
    if p:
        return db["accounts"].get(p, {})
    return {}


def unlink_partner(username: str) -> tuple:
    """قطع همدمی: هر دو اکانت به حالت مستقل برمی‌گردند."""
    db = load_db()
    me = db["accounts"].get(username)
    if not me:
        return False, "اکانت یافت نشد"
    partner_name = me.get("partner", "")
    if not partner_name:
        return False, "شما همدمی ندارید"

    # ریست خودم
    db["accounts"][username]["partner"] = ""
    db["accounts"][username]["link_role"] = ""
    db["accounts"][username]["link_code"] = ""

    # ریست همدم
    if partner_name in db["accounts"]:
        db["accounts"][partner_name]["partner"] = ""
        db["accounts"][partner_name]["link_role"] = ""
        db["accounts"][partner_name]["link_code"] = ""

    save_db(db)
    return True, "همدمی پایان یافت؛ اکانت مستقل شد"


def delete_account(username: str) -> tuple:
    """حذف کامل اکانت: پوشه‌ی اختصاصی + ورودی ایندکس + سشن‌ها.
    پس از این عملیات هیچ اثری از اکانت بیرون از پوشه‌ی حذف‌شده باقی نمی‌ماند."""
    db = load_db()
    acc = db["accounts"].get(username)
    if not acc:
        return False, "اکانت یافت نشد"

    # اگر همدم داشت، همدم را مستقل کن
    partner_name = acc.get("partner", "")
    if partner_name and partner_name in db["accounts"]:
        db["accounts"][partner_name]["partner"] = ""
        db["accounts"][partner_name]["link_role"] = ""
        db["accounts"][partner_name]["link_code"] = ""

    # پاک کردن کد لینک کاربر از جدول کدها
    code = acc.get("link_code", "")
    if code and code in db.get("link_codes", {}):
        del db["link_codes"][code]

    folder = account_folder(username)

    # حذف اکانت از دیتابیس در حافظه و از سشن‌ها
    del db["accounts"][username]
    for did, uname in list(db.get("device_sessions", {}).items()):
        if uname == username:
            del db["device_sessions"][did]

    # ابتدا ایندکس/سشن‌ها را ذخیره کن (save_db دیگر داخل پوشه‌ی حذف‌شده نمی‌نویسد)
    save_db(db)

    # سپس کل پوشه‌ی اختصاصی کاربر را حذف کن
    try:
        if _is_saf(folder):
            if _saf_delete_tree(folder):
                print(f"[delete_account] پوشه‌ی SAF حذف شد -> {folder}")
            else:
                print(f"[delete_account] هشدار: حذف پوشه‌ی SAF ناموفق بود -> {folder}")
        else:
            f_norm = os.path.normpath(folder)
            try:
                save_norm = os.path.normpath(SAVE_DIR)
            except Exception:
                save_norm = ""
            unsafe_roots = {os.path.normpath("/"), save_norm}
            if f_norm and f_norm not in unsafe_roots and os.path.isdir(f_norm):
                shutil.rmtree(f_norm, ignore_errors=True)
    except Exception as e:
        print(f"[delete_account] خطا در حذف پوشه ({folder}): {e}")

    return True, "اکانت با موفقیت حذف شد"
    return True, "اکانت با موفقیت حذف شد"


# ---------------------------------------------------------------------------
# عکس پروفایل
# ---------------------------------------------------------------------------
def _user_subdir(username: str, sub: str) -> tuple:
    """
    مسیر زیرپوشه‌ی اختصاصی کاربر (avatar / memories) داخل پوشه‌ی خودِ اکانت.
    خروجی: (path, is_saf)

    دیگر هیچ fallback ای به AVATAR_DIR/MEMORIES_DIR سراسری وجود ندارد؛ اگر کاربر
    پوشه‌ای انتخاب نکرده باشد، از پوشه‌ی محلیِ مخصوصِ همان اکانت
    (<SAVE_DIR>/accounts/<username>) استفاده می‌شود که باز هم «یک پوشه به ازای هر
    اکانت» است. تنها استثناء حالت SAF (content://) است که نوشتن مستقیم فایل روی آن
    ممکن نیست و is_saf=True برگردانده می‌شود.
    """
    sf = account_folder(username)
    if _is_saf(sf):
        if _saf_ready(sf):
            child = _saf_ensure_dir(sf, sub)
            if child:
                return child, True
        return sf.rstrip("/") + "/" + sub, True
    return os.path.join(sf, sub), False


def process_and_save_avatar(src_path: str, username: str) -> tuple:
    if not src_path or not os.path.exists(src_path):
        return None, "فایلی انتخاب نشد"
    size = os.path.getsize(src_path)
    if size > MAX_UPLOAD_SIZE:
        kb = size / 1024
        return None, f"حجم عکس {kb:.0f} کیلوبایت است؛ باید کمتر از ۳۰۰ کیلوبایت باشد"
    try:
        ext = os.path.splitext(src_path)[1] or ".png"
        safe = "".join(c for c in username if c.isalnum()) or "user"
        target_dir, is_saf = _user_subdir(username, "avatar")
        fname = f"avatar_{safe}{ext}"
        if is_saf:
            # SAF: عکس واقعاً داخل پوشه‌ی انتخابیِ کاربر (…/<username>/avatar)
            # نوشته می‌شود. یک نسخه‌ی محلی هم نگه داشته می‌شود تا ویجت Image
            # بتواند آن را نمایش دهد (Kivy نمی‌تواند content:// را رندر کند).
            saf_uri = _saf_copy_into(target_dir, fname, src_path)
            local_dir = os.path.join(default_account_folder(username), "avatar")
            os.makedirs(local_dir, exist_ok=True)
            dest_local = os.path.join(local_dir, fname)
            shutil.copyfile(src_path, dest_local)
            if not saf_uri:
                print("[avatar][SAF] نوشتن در پوشه‌ی انتخابی ناموفق بود؛ فقط نسخه‌ی محلی ذخیره شد.")
            return dest_local, "ok"
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, fname)
        shutil.copyfile(src_path, dest)
        return dest, "ok"
    except Exception as e:
        return None, f"خطا در ذخیره عکس: {e}"


def update_account_avatar(username: str, avatar_path: str):
    db = load_db()
    if username in db["accounts"]:
        db["accounts"][username]["avatar"] = avatar_path
        save_db(db)


def _mem_key(category_id: str, idea_title: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in idea_title)[:60]
    return f"{category_id}__{safe}"


def get_memory_image(username: str, category_id: str, idea_title: str) -> str:
    db = load_db()
    acc = db.get("accounts", {}).get(username, {})
    mems = acc.get("memories", {}) or {}
    return mems.get(_mem_key(category_id, idea_title), "")


def save_memory_image(username: str, category_id: str, idea_title: str, src_path: str):
    if not src_path or not os.path.exists(src_path):
        return None, "فایلی انتخاب نشد"
    try:
        ext = os.path.splitext(src_path)[1] or ".png"
        safe_user = "".join(c for c in username if c.isalnum()) or "user"
        key = _mem_key(category_id, idea_title)
        fname = f"mem_{safe_user}_{key}{ext}"
        target_dir, is_saf = _user_subdir(username, "memories")
        if is_saf:
            # SAF: عکس خاطره واقعاً داخل …/<username>/memories نوشته می‌شود و
            # یک نسخه‌ی محلی برای نمایش در Image نگه داشته می‌شود.
            if not _saf_copy_into(target_dir, fname, src_path):
                print("[memory][SAF] نوشتن در پوشه‌ی انتخابی ناموفق بود؛ فقط نسخه‌ی محلی ذخیره شد.")
            local_dir = os.path.join(default_account_folder(username), "memories")
            os.makedirs(local_dir, exist_ok=True)
            dest = os.path.join(local_dir, fname)
        else:
            os.makedirs(target_dir, exist_ok=True)
            dest = os.path.join(target_dir, fname)
        shutil.copyfile(src_path, dest)
        db = load_db()
        acc = db.get("accounts", {}).get(username)
        if acc is None:
            return None, "اکانت یافت نشد"
        if "memories" not in acc or not isinstance(acc.get("memories"), dict):
            acc["memories"] = {}
        acc["memories"][key] = dest
        save_db(db)
        return dest, "ok"
    except Exception as e:
        return None, f"خطا در ذخیره خاطره: {e}"



def upload_avatar(file_path: str) -> tuple:
    if not _REQUESTS_AVAILABLE:
        return False, "ماژول requests نصب نیست (آپلود انجام نشد)"
    if not file_path or not os.path.exists(file_path):
        return False, "فایلی برای آپلود نیست"
    if os.path.getsize(file_path) > MAX_UPLOAD_SIZE:
        return False, "حجم عکس بیشتر از ۳۰۰ کیلوبایت است"
    try:
        with open(file_path, "rb") as f:
            files = {"avatar": (os.path.basename(file_path), f, "image/png")}
            resp = requests.post(UPLOAD_URL, files=files, timeout=20)
        if resp.status_code == 200:
            return True, "عکس با موفقیت آپلود شد"
        return False, f"خطای سرور: {resp.status_code}"
    except Exception as e:
        return False, f"خطای اتصال: {e}"


# ---------------------------------------------------------------------------
# KV
# ---------------------------------------------------------------------------
KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<RoundedButton@ButtonBehavior+BoxLayout>:
    bg_color: 1, 0.75, 0.8, 1
    text: ""
    text_color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: self.bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(28)]
    Label:
        text: root.text
        font_name: app.font_name
        font_size: sp(18)
        bold: True
        color: root.text_color
        halign: "center"
        text_size: self.size
        valign: "middle"

<RootCard@BoxLayout>:
    canvas.before:
        Color:
            rgba: app.theme_surface_92
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(30)]
        Color:
            rgba: app.theme_card_border
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(30))
            width: dp(1.5)

<AuthForm@FloatLayout>:
    title_text: ""
    subtitle_text: ""
    btn_text: ""
    show_signup_link: False
    is_signup: False
    parent_screen: None
    username_input: username_input
    password_input: password_input
    fullname_input: fullname_input
    age_slider: age_slider
    age_label: age_value_label
    male_btn: male_btn
    female_btn: female_btn
    card_wrap: card_wrap

    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.55, self.height * 0.78
            size: dp(220), dp(220)
        Color:
            rgba: app.theme_bubble2
        Ellipse:
            pos: -dp(70), -dp(50)
            size: dp(190), dp(190)

    ScrollView:
        pos: root.pos
        size: root.size
        do_scroll_x: False
        # لرزشِ کوچکِ انگشت نباید به‌عنوان اسکرول تفسیر شود (لینک فراموشی رمز)
        scroll_distance: dp(28)
        scroll_timeout: 250
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: max(inner_col.minimum_height + dp(40), root.height)
            padding: dp(16), dp(20)
            BoxLayout:
                id: inner_col
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(12)

                Widget:
                    size_hint_y: None
                    height: dp(20)

                RootCard:
                    id: card_wrap
                    orientation: "vertical"
                    size_hint: None, None
                    width: root.width * 0.96
                    height: self.minimum_height
                    padding: dp(22), dp(26)
                    spacing: dp(14)
                    pos_hint: {"center_x": 0.5}

                    Label:
                        text: root.title_text
                        font_name: app.font_name
                        font_size: sp(28)
                        bold: True
                        color: app.theme_title
                        size_hint_y: None
                        height: dp(46)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"

                    Label:
                        text: root.subtitle_text
                        font_name: app.font_name
                        font_size: sp(13)
                        color: app.theme_text_secondary
                        size_hint_y: None
                        height: dp(24)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"

                    Widget:
                        size_hint_y: None
                        height: dp(6)

                    InputBox:
                        size_hint_y: None
                        height: dp(48)
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(16)]
                        RTLTextInput:
                            id: username_input
                            hint_text: app.t_username if root.is_signup else app.t_login_username
                            font_name: app.font_name
                            font_size: sp(16)
                            multiline: False
                            background_color: 0, 0, 0, 0
                            foreground_color: app.theme_text_primary
                            hint_text_color: app.theme_text_hint
                            cursor_color: 0.8, 0.5, 0.6, 1
                            padding: dp(14), dp(12)

                    # ── نام و نام خانوادگی (فقط در صفحه‌ی ساخت اکانت) ──
                    InputBox:
                        size_hint_y: None
                        height: dp(48) if root.is_signup else 0
                        opacity: 1 if root.is_signup else 0
                        disabled: False if root.is_signup else True
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(16)]
                        RTLTextInput:
                            id: fullname_input
                            hint_text: app.t_fullname
                            font_name: app.font_name
                            font_size: sp(16)
                            multiline: False
                            background_color: 0, 0, 0, 0
                            foreground_color: app.theme_text_primary
                            hint_text_color: app.theme_text_hint
                            cursor_color: 0.8, 0.5, 0.6, 1
                            padding: dp(14), dp(12)

                    InputBox:
                        size_hint_y: None
                        height: dp(48)
                        opacity: 1
                        disabled: False
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(16)]
                        RTLTextInput:
                            id: password_input
                            hint_text: app.t_password
                            font_name: app.font_name
                            font_size: sp(16)
                            multiline: False
                            password: True
                            background_color: 0, 0, 0, 0
                            foreground_color: app.theme_text_primary
                            hint_text_color: app.theme_text_hint
                            cursor_color: 0.8, 0.5, 0.6, 1
                            padding: dp(14), dp(12)
                        EyeToggleButton:
                            id: eye_btn
                            password_field: password_input
                            on_release: self.toggle()

                    # ── لینک «فراموشی رمز عبور؟» (فقط در فرم ورود) ──
                    LinkLabel:
                        text: app.t_forgot_link
                        font_name: app.font_name
                        font_size: sp(12)
                        bold: True
                        color: app.theme_accent
                        underline: True
                        size_hint_y: None
                        height: (dp(34) if not root.is_signup else 0)
                        opacity: (1 if not root.is_signup else 0)
                        disabled: (True if root.is_signup else False)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"
                        on_release: root.parent_screen.go_forgot_password()

                    # ── فیلد تکرار رمز حذف شده است ──

                    # ── انتخاب محل ذخیره‌سازی در حافظه‌ی دستگاه (فقط در signup) ──
                    BoxLayout:
                        orientation: "vertical"
                        size_hint_y: None
                        height: (dp(56) if root.is_signup else 0)
                        opacity: 1 if root.is_signup else 0
                        disabled: False if root.is_signup else True
                        spacing: dp(2)
                        Label:
                            id: storage_label
                            text: app.t_storage_label
                            font_name: app.font_name
                            font_size: sp(13)
                            bold: True
                            color: (app.theme_title if root.parent_screen and getattr(root.parent_screen, "selected_storage_path", "") else (app.theme_text_secondary))
                            size_hint_y: None
                            height: dp(24)
                            halign: "right"
                            text_size: self.size
                            valign: "middle"
                            on_touch_down:
                                if self.collide_point(*args[1].pos) and root.is_signup: root.parent_screen.pick_storage_folder()
                        Label:
                            id: storage_path_label
                            text: (root.parent_screen.selected_storage_path if root.parent_screen and getattr(root.parent_screen, "selected_storage_path", "") else app.t_storage_none)
                            font_name: app.font_name
                            font_size: sp(11)
                            color: app.theme_text_secondary
                            size_hint_y: None
                            height: dp(20)
                            halign: "right"
                            text_size: self.size
                            valign: "middle"
                            shorten: True
                            shorten_from: "left"

                    Widget:
                        size_hint_y: None
                        height: dp(2)

                    Label:
                        text: app.t_gender
                        font_name: app.font_name
                        font_size: sp(13)
                        color: app.theme_text_secondary
                        size_hint_y: None
                        height: dp(18)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"

                    BoxLayout:
                        size_hint_y: None
                        height: dp(100)
                        spacing: dp(12)
                        GenderImageButton:
                            id: female_btn
                            image_source: app.girl_image
                            label_text: app.t_female
                            on_release: root.parent_screen.set_gender("female")
                        GenderImageButton:
                            id: male_btn
                            image_source: app.boy_image
                            label_text: app.t_male
                            on_release: root.parent_screen.set_gender("male")

                    Widget:
                        size_hint_y: None
                        height: dp(2)

                    BoxLayout:
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(64)
                        spacing: dp(2)
                        BoxLayout:
                            size_hint_y: None
                            height: dp(20)
                            Label:
                                text: app.t_age
                                font_name: app.font_name
                                font_size: sp(13)
                                color: app.theme_text_secondary
                                halign: "right"
                                text_size: self.size
                                valign: "middle"
                            Label:
                                id: age_value_label
                                text: "20"
                                font_name: app.font_name
                                bold: True
                                font_size: sp(15)
                                color: app.theme_title
                                halign: "left"
                                text_size: self.size
                                valign: "middle"
                        Slider:
                            id: age_slider
                            min: 15
                            max: 35
                            value: 20
                            step: 1
                            cursor_size: dp(22), dp(22)
                            on_value: root.parent_screen.set_age(self.value)

                    Widget:
                        size_hint_y: None
                        height: dp(8)

                    # ── تایید قوانین (فقط در signup) ──
                    BoxLayout:
                        id: rules_row
                        orientation: "horizontal"
                        size_hint_y: None
                        height: (max(rules_text.texture_size[1] + dp(14), dp(34)) if root.is_signup else 0)
                        opacity: 1 if root.is_signup else 0
                        disabled: False if root.is_signup else True
                        spacing: dp(8)
                        Label:
                            id: rules_text
                            text: app.t_rules_accept
                            font_name: app.font_name
                            font_size: sp(12)
                            color: 0.35, 0.32, 0.34, 1
                            markup: True
                            halign: "right"
                            valign: "middle"
                            text_size: self.width, None
                            size_hint_y: None
                            height: self.texture_size[1]
                            on_ref_press: root.parent_screen.open_rules()
                        RulesCheckbox:
                            id: rules_checkbox
                            size_hint: None, None
                            size: dp(26), dp(26)
                            pos_hint: {"center_y": 0.5}

                    RoundedButton:
                        id: submit_btn
                        text: root.btn_text
                        bg_color: app.theme_accent
                        size_hint_y: None
                        height: dp(50)
                        on_release: root.parent_screen.try_submit()

                    Label:
                        text: app.t_login_link if root.is_signup else app.t_signup_link
                        font_name: app.font_name
                        font_size: sp(13)
                        bold: True
                        color: app.theme_title
                        size_hint_y: None
                        height: dp(28)
                        opacity: 1
                        halign: "center"
                        text_size: self.size
                        valign: "middle"
                        on_touch_down:
                            if self.collide_point(*args[1].pos): (root.parent_screen.go_login() if root.is_signup else root.parent_screen.go_signup())

                    # ── لینک ورود با پوشه‌ی محل ذخیره‌سازی (فقط در صفحه‌ی ورود) ──
                    Label:
                        text: app.t_folder_login_link
                        font_name: app.font_name
                        font_size: sp(12)
                        bold: True
                        color: app.theme_accent
                        underline: True
                        size_hint_y: None
                        height: (dp(26) if not root.is_signup else 0)
                        opacity: (1 if not root.is_signup else 0)
                        disabled: (True if root.is_signup else False)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"
                        on_touch_down:
                            if (not root.is_signup) and self.collide_point(*args[1].pos): root.parent_screen.login_by_folder()

                    Label:
                        text: app.t_shared
                        font_name: app.font_name
                        font_size: sp(11)
                        color: 0.65, 0.6, 0.62, 1
                        size_hint_y: None
                        height: dp(22)
                        halign: "center"
                        text_size: self.size
                        valign: "middle"

                Widget:
                    size_hint_y: None
                    height: dp(16)

<ToastBar@BoxLayout>:
    bar_color: 0.82, 0.33, 0.08, 0.96
    canvas.before:
        Color:
            rgba: self.bar_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(18)]
    padding: dp(16), dp(10)

<LoginScreen>:
    FloatLayout:
        AuthForm:
            id: form
            parent_screen: root
            title_text: app.t_title
            subtitle_text: app.t_subtitle
            btn_text: app.t_login_btn
            show_signup_link: True
            is_signup: False
        # ── آیکون راهنما (علامت سوال) بالا-سمت‌راست ──
        Image:
            source: app.question_image
            size_hint: None, None
            size: dp(32), dp(32)
            allow_stretch: True
            keep_ratio: True
            pos_hint: {"right": 0.97, "top": 0.985}
            opacity: 1 if app.question_image else 0
            on_touch_down:
                if self.opacity > 0 and self.collide_point(*args[1].pos): root.open_help()
        ToastBar:
            id: toast_bar
            size_hint: None, None
            width: min(dp(360), root.width * 0.9)
            height: dp(52)
            opacity: 0
            pos_hint: {"center_x": 0.5}
            top: root.height + dp(60)

<SignupScreen>:
    FloatLayout:
        AuthForm:
            id: form
            parent_screen: root
            title_text: app.t_signup_title
            subtitle_text: app.t_signup_sub
            btn_text: app.t_signup_btn
            show_signup_link: False
            is_signup: True
        # ── آیکون راهنما (علامت سوال) بالا-سمت‌راست ──
        Image:
            source: app.question_image
            size_hint: None, None
            size: dp(32), dp(32)
            allow_stretch: True
            keep_ratio: True
            pos_hint: {"right": 0.97, "top": 0.985}
            opacity: 1 if app.question_image else 0
            on_touch_down:
                if self.opacity > 0 and self.collide_point(*args[1].pos): root.open_help()
        ToastBar:
            id: toast_bar
            size_hint: None, None
            width: min(dp(360), root.width * 0.9)
            height: dp(52)
            opacity: 0
            pos_hint: {"center_x": 0.5}
            top: root.height + dp(60)

<RulesScreen>:
    canvas.before:
        Color:
            rgba: 0.20, 0.20, 0.23, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: "vertical"
        padding: dp(18), dp(20)
        spacing: dp(12)
        Label:
            text: app.t_rules_title
            font_name: app.font_name
            font_size: sp(22)
            bold: True
            color: 1, 1, 1, 1
            size_hint_y: None
            height: dp(44)
            halign: "right"
            text_size: self.size
            valign: "middle"
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(4), dp(4)
                spacing: dp(10)
                RTLLabel:
                    id: rules_body
                    raw_text: app.t_rules_body_raw
                    font_name: app.font_name
                    font_size: sp(15)
                    color: 1, 1, 1, 1
                    size_hint_y: None
                    halign: "right"
                    valign: "top"
                    on_texture_size: self.height = self.texture_size[1] + dp(20)
        RoundedButton:
            text: app.t_rules_ok_btn
            bg_color: 0.15, 0.45, 0.25, 1
            size_hint_y: None
            height: dp(52)
            on_release: root.accept_rules()


<HelpScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.55, self.height * 0.78
            size: dp(220), dp(220)
        Color:
            rgba: app.theme_bubble2
        Ellipse:
            pos: -dp(70), -dp(50)
            size: dp(190), dp(190)
    FloatLayout:
        BoxLayout:
            orientation: "vertical"
            padding: dp(18), dp(20)
            spacing: dp(12)
            size_hint: 1, 1

            BoxLayout:
                size_hint_y: None
                height: dp(48)
                spacing: dp(8)
                Image:
                    source: app.back_image
                    size_hint: None, None
                    size: dp(32), dp(32)
                    allow_stretch: True
                    keep_ratio: True
                    pos_hint: {"center_y": 0.5}
                    opacity: 1 if app.back_image else 0
                    on_touch_down:
                        if self.opacity > 0 and self.collide_point(*args[1].pos): root.go_back()
                Label:
                    text: app.t_help_title
                    font_name: app.font_name
                    font_size: sp(22)
                    bold: True
                    color: app.theme_title
                    halign: "right"
                    valign: "middle"
                    text_size: self.size

            RootCard:
                orientation: "vertical"
                size_hint_y: 1
                padding: dp(18), dp(18)
                spacing: dp(10)
                ScrollView:
                    do_scroll_x: False
                    BoxLayout:
                        orientation: "vertical"
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(10)
                        RTLLabel:
                            id: help_body
                            raw_text: root.help_text_raw
                            font_name: app.font_name
                            font_size: sp(15)
                            color: app.theme_title
                            size_hint_y: None
                            halign: "right"
                            valign: "top"
                            on_texture_size: self.height = self.texture_size[1] + dp(10)

            RoundedButton:
                text: app.t_help_back_btn
                bg_color: app.theme_accent
                size_hint_y: None
                height: dp(50)
                on_release: root.go_back()

<CategoryCard>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(140)
    padding: dp(14)
    spacing: dp(6)
    canvas.before:
        # سایه‌ی نرم پشت کارت
        Color:
            rgba: 0, 0, 0, 0.10
        RoundedRectangle:
            pos: self.x + dp(2), self.y - dp(4)
            size: self.size
            radius: [dp(22)]
        Color:
            rgba: 0, 0, 0, 0.06
        RoundedRectangle:
            pos: self.x + dp(4), self.y - dp(7)
            size: self.size
            radius: [dp(22)]
        Color:
            rgba: self.card_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(22)]
    FloatLayout:
        size_hint_y: 0.45
        Label:
            text: root.emoji_text
            font_name: "Roboto"
            font_size: sp(38)
            halign: "center"
            valign: "middle"
            size_hint: 1, 1
            text_size: self.size
            opacity: 0 if root.icon_source else 1
        Image:
            source: root.icon_source
            size_hint: None, None
            size: dp(44), dp(44)
            allow_stretch: True
            keep_ratio: True
            pos_hint: {"center_x": 0.5, "center_y": 0.5}
            opacity: 1 if root.icon_source else 0
    BoxLayout:
        orientation: "vertical"
        spacing: dp(4)
        size_hint_y: 0.55
        Label:
            text: root.title_text
            font_name: app.font_name
            font_size: sp(15)
            bold: True
            color: 0.32, 0.26, 0.28, 1
            halign: "center"
            valign: "middle"
            text_size: self.size
        Label:
            text: root.subtitle_text
            font_name: app.font_name
            font_size: sp(12)
            color: 0.42, 0.36, 0.38, 1
            halign: "center"
            valign: "middle"
            text_size: self.size

<CategoriesScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.6, self.height * 0.82
            size: dp(180), dp(180)

    BoxLayout:
        orientation: "vertical"
        padding: dp(16), dp(18)
        spacing: dp(12)

        FloatLayout:
            id: avatar_holder
            size_hint_y: None
            height: dp(96)

        Label:
            text: app.t_cat_title
            font_name: app.font_name
            font_size: sp(23)
            bold: True
            color: app.theme_title
            size_hint_y: None
            height: dp(38)
            halign: "center"
            text_size: self.size
            valign: "middle"

        Label:
            text: app.t_cat_sub
            font_name: app.font_name
            font_size: sp(13)
            color: app.theme_cat_sub
            size_hint_y: None
            height: dp(22)
            halign: "center"
            text_size: self.size
            valign: "middle"

        ScrollView:
            do_scroll_x: False
            GridLayout:
                id: categories_grid
                cols: 2
                spacing: dp(18), dp(20)
                size_hint_y: None
                height: self.minimum_height
                padding: dp(8), dp(10)

    # ── دکمه‌ی تغییر تم (بالا-چپ، شیشه‌ای و گرد) ──
    FloatLayout:
        size_hint: 1, 1
        BoxLayout:
            size_hint: None, None
            size: dp(44), dp(44)
            pos_hint: {"x": 0.045, "top": 0.985}
            padding: dp(7)
            canvas.before:
                Color:
                    rgba: 0.55, 0.58, 0.62, 0.35
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(13)]
                Color:
                    rgba: 1, 1, 1, 0.18
                Line:
                    rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(13))
                    width: 1
            ThemeToggleButton:
                id: theme_toggle_btn

<IdeaCard>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(170)
    padding: dp(14)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: app.theme_surface
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(20)]
        Color:
            rgba: root.border_color
        RoundedRectangle:
            pos: self.right - dp(5), self.y
            size: dp(5), self.height
            radius: [0, dp(20), dp(20), 0]
    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(28)
        spacing: dp(6)
        Label:
            text: root.title_text
            font_name: app.font_name
            font_size: sp(15)
            bold: True
            color: app.theme_text_strong
            halign: "right"
            valign: "middle"
            text_size: self.size
        Widget:
            size_hint_x: None
            width: dp(14)
            opacity: 1 if root.is_done else 0
            canvas:
                Color:
                    rgba: 0.231, 0.722, 0.216, 1
                Ellipse:
                    pos: self.center_x - dp(6), self.center_y - dp(6)
                    size: dp(12), dp(12)
    Label:
        text: root.desc_text
        font_name: app.font_name
        font_size: sp(12)
        color: app.theme_text_body
        halign: "right"
        valign: "top"
        text_size: self.size
    BoxLayout:
        id: tags_box
        size_hint_y: None
        height: dp(28)
        spacing: dp(6)

<IdeasScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
    FloatLayout:
        BoxLayout:
            orientation: "vertical"
            padding: dp(14), dp(16)
            spacing: dp(10)
            size_hint: 1, 1
            pos_hint: {"x": 0, "y": 0}
            BoxLayout:
                size_hint_y: None
                height: dp(46)
                spacing: dp(8)
                BoxLayout:
                    size_hint_x: None
                    width: dp(54)
                    padding: dp(7)
                    canvas.before:
                        Color:
                            rgba: 0.55, 0.58, 0.62, 0.35
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(14)]
                        Color:
                            rgba: 1, 1, 1, 0.18
                        Line:
                            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(14))
                            width: 1
                    IconImageButton:
                        id: back_btn
                        source: app.back_image
                        on_release: root.go_back()
                BoxLayout:
                    size_hint_x: None
                    width: dp(54)
                    padding: dp(7)
                    canvas.before:
                        Color:
                            rgba: 0.55, 0.58, 0.62, 0.35
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(14)]
                        Color:
                            rgba: 1, 1, 1, 0.18
                        Line:
                            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(14))
                            width: 1
                    IconImageButton:
                        id: random_btn
                        source: app.random_image
                        on_release: root.do_random_spin()
                BoxLayout:
                    size_hint_x: None
                    width: dp(54) if root.show_add_button else 0
                    opacity: 1 if root.show_add_button else 0
                    disabled: not root.show_add_button
                    padding: dp(7)
                    canvas.before:
                        Color:
                            rgba: 0.23, 0.58, 0.40, 0.85
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(14)]
                        Color:
                            rgba: 1, 1, 1, 0.22
                        Line:
                            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(14))
                            width: 1
                    Button:
                        background_normal: ""
                        background_color: 0, 0, 0, 0
                        text: "+"
                        font_size: sp(28)
                        bold: True
                        color: 1, 1, 1, 1
                        on_release: root.open_add_idea()
                Label:
                    id: title_lbl
                    text: ""
                    font_name: app.font_name
                    font_size: sp(18)
                    bold: True
                    color: app.theme_title
                    halign: "right"
                    valign: "middle"
                    text_size: self.size
            Label:
                id: subtitle_lbl
                text: ""
                font_name: app.font_name
                font_size: sp(12)
                color: 0.62, 0.38, 0.44, 1
                size_hint_y: None
                height: dp(22)
                halign: "right"
                text_size: self.size
            ScrollView:
                id: ideas_scroll
                do_scroll_x: False
                BoxLayout:
                    id: ideas_box
                    orientation: "vertical"
                    spacing: dp(12)
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(2), dp(4)

        Image:
            source: app.question_image
            size_hint: None, None
            size: dp(32), dp(32)
            allow_stretch: True
            keep_ratio: True
            pos_hint: {"right": 0.97, "top": 0.985}
            opacity: 1 if app.question_image else 0
            on_touch_down:
                if self.opacity > 0 and self.collide_point(*args[1].pos): root.open_help()

<IdeaDetailScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.6, self.height * 0.82
            size: dp(180), dp(180)
        Color:
            rgba: app.theme_bubble2
        Ellipse:
            pos: -dp(70), -dp(50)
            size: dp(190), dp(190)
    BoxLayout:
        orientation: "vertical"
        padding: dp(14), dp(16)
        spacing: dp(10)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            BoxLayout:
                size_hint_x: None
                width: dp(54)
                padding: dp(7)
                canvas.before:
                    Color:
                        rgba: 0.89, 0.204, 0.204, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                IconImageButton:
                    source: app.back_image
                    on_release: app.root.current = "ideas"
            Widget:
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                spacing: dp(14)
                size_hint_y: None
                height: self.minimum_height
                padding: dp(4), dp(4)
                Label:
                    id: detail_title
                    text: ""
                    font_name: app.font_name
                    font_size: sp(22)
                    bold: True
                    color: app.theme_title
                    size_hint_y: None
                    height: self.texture_size[1] + dp(8)
                    halign: "right"
                    valign: "top"
                    text_size: self.width, None
                BoxLayout:
                    id: detail_tags_box
                    size_hint_y: None
                    height: dp(30)
                    spacing: dp(6)
                RTLLabel:
                    id: detail_desc
                    raw_text: ""
                    font_name: app.font_name
                    font_size: sp(14)
                    color: app.theme_text_primary
                    size_hint_y: None
                    height: self.texture_size[1] + dp(8)
                    halign: "right"
                    valign: "top"
                Widget:
                    size_hint_y: None
                    height: dp(10)
                FloatLayout:
                    id: memory_holder
                    size_hint_y: None
                    height: dp(220)
                Widget:
                    size_hint_y: None
                    height: dp(12)
                BoxLayout:
                    id: done_btn_holder
                    size_hint_y: None
                    height: dp(56)

<EditProfileScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.6, self.height * 0.82
            size: dp(180), dp(180)
        Color:
            rgba: app.theme_bubble2
        Ellipse:
            pos: -dp(70), -dp(50)
            size: dp(190), dp(190)
    BoxLayout:
        orientation: "vertical"
        padding: dp(18), dp(20)
        spacing: dp(12)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            BoxLayout:
                size_hint_x: None
                width: dp(54)
                padding: dp(7)
                canvas.before:
                    Color:
                        rgba: 0.55, 0.58, 0.62, 0.35
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                IconImageButton:
                    source: app.back_image
                    on_release: root.go_back()
            Label:
                text: root.header_text
                font_name: app.font_name
                font_size: sp(20)
                bold: True
                color: app.theme_title
                halign: "right"
                valign: "middle"
                text_size: self.size
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(12)
                padding: dp(4), dp(4)
                Label:
                    id: username_label
                    text: ""
                    font_name: app.font_name
                    font_size: sp(14)
                    color: app.theme_text_primary
                    size_hint_y: None
                    height: dp(28)
                    halign: "right"
                    text_size: self.size
                    valign: "middle"
                Label:
                    id: gender_label
                    text: ""
                    font_name: app.font_name
                    font_size: sp(14)
                    color: app.theme_text_primary
                    size_hint_y: None
                    height: dp(28)
                    halign: "right"
                    text_size: self.size
                    valign: "middle"
                Label:
                    text: root.t_fullname_label
                    font_name: app.font_name
                    font_size: sp(13)
                    color: 0.5, 0.42, 0.45, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size
                InputBox:
                    size_hint_y: None
                    height: dp(48)
                    canvas.before:
                        Color:
                            rgba: app.theme_input_bg
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16)]
                    RTLTextInput:
                        id: fullname_input
                        font_name: app.font_name
                        font_size: sp(16)
                        multiline: False
                        background_color: 0, 0, 0, 0
                        foreground_color: app.theme_text_primary
                        cursor_color: 0.8, 0.5, 0.6, 1
                        padding: dp(14), dp(12)
                Label:
                    text: root.t_password_label
                    font_name: app.font_name
                    font_size: sp(13)
                    color: 0.5, 0.42, 0.45, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size
                InputBox:
                    size_hint_y: None
                    height: dp(48)
                    canvas.before:
                        Color:
                            rgba: app.theme_input_bg
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16)]
                    RTLTextInput:
                        id: password_input
                        hint_text: root.t_password_hint
                        font_name: app.font_name
                        font_size: sp(16)
                        multiline: False
                        password: True
                        background_color: 0, 0, 0, 0
                        foreground_color: app.theme_text_primary
                        hint_text_color: app.theme_text_hint
                        cursor_color: 0.8, 0.5, 0.6, 1
                        padding: dp(14), dp(12)
                    EyeToggleButton:
                        id: eye_btn
                        password_field: password_input
                        on_release: self.toggle()
                Label:
                    text: root.t_age_label
                    font_name: app.font_name
                    font_size: sp(13)
                    color: 0.5, 0.42, 0.45, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size
                BoxLayout:
                    orientation: "horizontal"
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    Label:
                        id: age_value_label
                        text: "20"
                        font_name: app.font_name
                        font_size: sp(16)
                        bold: True
                        color: app.theme_title
                        size_hint_x: None
                        width: dp(48)
                        halign: "center"
                        valign: "middle"
                        text_size: self.size
                    Slider:
                        id: age_slider
                        min: 15
                        max: 35
                        step: 1
                        value: 20
                        on_value: root._on_age(self.value)
                Widget:
                    size_hint_y: None
                    height: dp(8)
                BoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    padding: dp(0), dp(0)
                    canvas.before:
                        Color:
                            rgba: 0.15, 0.6, 0.35, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16)]
                    Button:
                        text: root.t_save_btn
                        font_name: app.font_name
                        font_size: sp(17)
                        bold: True
                        color: 1, 1, 1, 1
                        background_color: 0, 0, 0, 0
                        background_normal: ""
                        on_release: root.save_changes()
"""

# ---------------------------------------------------------------------------
# RTLTextInput
# ---------------------------------------------------------------------------
class RTLTextInput(TextInput):
    """
    RTL/فارسی TextInput مقاوم به لمس.

    نکته‌ی مهم درباره‌ی نگاشت مکان‌نما:
    - self._raw_text = رشته‌ی *منطقی* اصلی که کاربر تایپ کرده (append-only از دید مکان‌نما).
    - self.text     = رشته‌ی *نمایشی* بعد از reshape/bidi که فقط برای رندر استفاده می‌شود.
    چون کیوی برای رسم و لمس، از self.text (نمایشی) استفاده می‌کند و بازچینی bidi
    ترتیب کاراکترها را عوض می‌کند، هیچ نگاشت ۱-به-۱ ساده‌ای بین لمس و ایندکس منطقی
    وجود ندارد. راه‌حل درست و پایدار: هر لمس داخل ویجت، فوکوس بگیرد و مکان‌نما را
    به انتهای منطقی (که همان انتهای نمایشی است پس از bidi) ببرد. این هم برای فیلد
    نام کاربری و هم برای فیلد رمز عبور (password=True) درست کار می‌کند.
    """

    _raw_text = StringProperty("")
    _updating = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.write_tab = False
        self.halign = "right"
        self.base_direction = "rtl"
        self.multiline = kwargs.get("multiline", False)

    # ------------ ورودی‌ها ------------
    def insert_text(self, substring, from_undo=False):
        if not substring:
            return
        # همیشه در انتهای منطقی درج می‌کنیم — سازگار با رفتار قبلی که مکان‌نما را
        # پس از هر ویرایش به انتها می‌برد.
        self._raw_text = self._raw_text + substring
        self._sync_display()

    def do_backspace(self, from_undo=False, mode='bsp'):
        if not self._raw_text:
            return
        self._raw_text = self._raw_text[:-1]
        self._sync_display()

    # ------------ همگام‌سازی نمایش ------------
    def _sync_display(self):
        if self._updating:
            return
        self._updating = True
        raw = self._raw_text or ""
        display = raw
        # BUGFIX 1: مراحل مجزا؛ هر خطا در logcat دیده می‌شود و متن خام حفظ می‌شود.
        display = _bidi_step(_reshape_step(raw))
        self.text = display
        # مکان‌نما را به انتهای نمایشی می‌بریم (مسیر واحد _move_cursor_to_end).
        self._move_cursor_to_end()
        self._updating = False

    # ------------ لمس/کلیک ------------
    def _move_cursor_to_end(self):
        """تنها مسیر معتبر برای بردن مکان‌نما به انتهای متن نمایشی.
        چون bidi ترتیب کاراکترها را عوض می‌کند و در حالت password متن نمایشی
        ماسک‌شده است، هیچ نگاشت لمس→ایندکسِ قابل‌اعتمادی وجود ندارد؛ پس همیشه
        انتهای متن هدف است. بدون Clock و بدون فراخوانی تکراری."""
        try:
            self.cursor = (len(self.text or ""), 0)
        except Exception:
            pass

    def on_touch_down(self, touch):
        """
        مسیر قطعی و بدون race:
        - لمس بیرون از ویجت → به‌طور کامل به super واگذار می‌شود (تا فوکوس آزاد
          شود و ویجت‌های همسایه مثل EyeToggleButton رویدادشان را بگیرند).
        - لمس داخل ویجت → همین‌جا مدیریت می‌شود: فوکوس مستقیم ست می‌شود،
          مکان‌نما یک‌بار به انتها می‌رود و رویداد مصرف می‌شود؛ دیگر منطق
          فوکوس/مکان‌نمای پیش‌فرض TextInput (که منبع رفتار غیرقطعی بود) اجرا
          نمی‌شود.
        """
        if self.disabled or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        # لمس‌های غیر از کلیک اصلی (اسکرول چرخ ماوس و ...) را به super بسپار
        btn = getattr(touch, "button", None)
        if btn is not None and btn != "left":
            return super().on_touch_down(touch)

        touch.grab(self)
        try:
            self.focus = True
        except Exception:
            pass
        self._move_cursor_to_end()
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            # اطمینان نهایی: فوکوس و مکان‌نما پس از رها شدن لمس پایدار بماند
            try:
                if not self.focus and not self.disabled:
                    self.focus = True
            except Exception:
                pass
            self._move_cursor_to_end()
            return True
        return super().on_touch_up(touch)

    # ------------ API خارجی (سازگار با کد فعلی) ------------
    def get_raw_text(self):
        return self._raw_text or ""

    def set_raw_text(self, text):
        self._raw_text = text or ""
        self._sync_display()




# ---------------------------------------------------------------------------
# RTLLabel — لیبل چندخطی فارسی با شکستن صحیح خطوط
# ---------------------------------------------------------------------------
from kivy.uix.label import Label as _KVLabel
from kivy.core.text import Label as _CoreLabel
from kivy.factory import Factory as _Factory


def _fa_line(raw_line: str) -> str:
    """اعمال reshape/bidi روی یک خط تک — بدون شکستن اضافی."""
    if not raw_line:
        return raw_line
    # BUGFIX 1: استفاده از مراحل مجزای reshape/bidi با لاگ خطای قابل مشاهده
    return _bidi_step(_reshape_step(raw_line))


def fa_wrap(raw_text: str, width_px: float, font_name: str, font_size_px: float) -> str:
    """
    شکستن پاراگراف فارسی به‌درستی:
      1) روی رشته‌ی *منطقی* (raw) کلمه‌به‌کلمه wrap می‌کنیم.
      2) هر خط شکسته‌شده جداگانه از reshape/bidi عبور می‌کند.
      3) خطوط با \n به هم می‌چسبند تا کیوی خودش دوباره wrap نکند.
    این روش مشکل «به‌هم‌ریختگی ترتیب کلمات بین خط‌ها» را وقتی متن از قبل bidi شده و
    دوباره توسط Label بازwrap می‌شود کاملاً حل می‌کند.
    """
    if not raw_text:
        return ""
    if not width_px or width_px <= 1:
        return _fa_line(raw_text)

    measure = _CoreLabel(font_name=font_name, font_size=font_size_px)
    space_w = 0
    try:
        measure.refresh()
        # اندازه‌گیری فاصله
        measure.text = " "
        measure.refresh()
        space_w = measure.texture.size[0] if measure.texture else 0
    except Exception:
        space_w = font_size_px * 0.3

    out_lines = []
    for para in raw_text.split("\n"):
        if not para.strip():
            out_lines.append("")
            continue
        words = para.split(" ")
        cur_words = []
        cur_w = 0.0
        for w in words:
            if not w:
                continue
            try:
                measure.text = w
                measure.refresh()
                ww = measure.texture.size[0] if measure.texture else len(w) * font_size_px * 0.5
            except Exception:
                ww = len(w) * font_size_px * 0.5
            add = ww + (space_w if cur_words else 0)
            if cur_words and (cur_w + add) > width_px:
                out_lines.append(" ".join(cur_words))
                cur_words = [w]
                cur_w = ww
            else:
                cur_words.append(w)
                cur_w += add
        if cur_words:
            out_lines.append(" ".join(cur_words))

    return "\n".join(_fa_line(ln) for ln in out_lines)


class RTLLabel(_KVLabel):
    """
    Labelی که متن فارسی خام را می‌گیرد و در زمان تغییر عرض/متن، به‌درستی wrap می‌کند.
    استفاده: در KV به‌جای Label بنویسید RTLLabel و raw_text را ست کنید.
    """
    raw_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.halign = kwargs.get("halign", "right")
        self.valign = kwargs.get("valign", "top")
        self.base_direction = "rtl"
        # فعال نگه داشتن text_size روی عرض ویجت تا ارتفاع درست حساب شود؛
        # ولی چون خودمان \n می‌گذاریم، کیوی دیگر کلمات را دستکاری نمی‌کند.
        self.bind(width=self._rewrap, raw_text=self._rewrap,
                  font_name=self._rewrap, font_size=self._rewrap)

    def _rewrap(self, *_):
        if self.width <= 1:
            return
        wrapped = fa_wrap(self.raw_text or "", float(self.width),
                          self.font_name, float(self.font_size))
        # text_size را روی همان عرض می‌گذاریم تا texture_size ارتفاع را درست بدهد؛
        # چون از قبل \n داریم، عرض کافی است و کیوی خط اضافه نمی‌کند.
        self.text_size = (self.width, None)
        self.text = wrapped


try:
    _Factory.register("RTLLabel", cls=RTLLabel)
except Exception:
    pass


# ---------------------------------------------------------------------------
# EyeToggleButton
# ---------------------------------------------------------------------------
class EyeToggleButton(ButtonBehavior, BoxLayout):
    password_field = None
    _visible = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_x = None
        self.width = dp(50)
        self.padding = [dp(8), dp(8)]
        Clock.schedule_once(self._build_icon, 0)

    # ناحیه‌ی لمسی دکمه‌ی چشم دقیقاً محدود به خودِ دکمه است؛ هر لمسی خارج از آن
    # (یعنی روی فیلد رمز کنارش) اصلاً پردازش نمی‌شود تا تداخل فوکوس پیش نیاید.
    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        return super().on_touch_up(touch)

    def _build_icon(self, dt):
        source = EYE_IMAGE if os.path.exists(EYE_IMAGE) else ""
        self._img = Image(source=source, size_hint=(None, None),
                          size=(dp(32), dp(32)), allow_stretch=True,
                          keep_ratio=False)
        self.add_widget(self._img)

    def toggle(self):
        if not self.password_field:
            return
        self._visible = not self._visible
        self.password_field.password = not self._visible
        if hasattr(self, '_img'):
            if self._visible:
                self._img.source = EYE_OPEN_IMAGE if os.path.exists(EYE_OPEN_IMAGE) else ""
            else:
                self._img.source = EYE_IMAGE if os.path.exists(EYE_IMAGE) else ""

    def reset(self):
        self._visible = False
        if self.password_field:
            self.password_field.password = True
        if hasattr(self, '_img'):
            self._img.source = EYE_IMAGE if os.path.exists(EYE_IMAGE) else ""


# ---------------------------------------------------------------------------
# RulesCheckbox — چک‌باکس تصویری تایید قوانین
# ---------------------------------------------------------------------------
class RulesCheckbox(ButtonBehavior, BoxLayout):
    checked = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(2)] * 4
        Clock.schedule_once(self._build_icon, 0)

    def _build_icon(self, dt):
        src = CHECKBOX_EMPTY_IMAGE if os.path.exists(CHECKBOX_EMPTY_IMAGE) else ""
        self._img = Image(source=src, allow_stretch=True, keep_ratio=True)
        self.add_widget(self._img)

    def on_release(self):
        self.set_checked(not self.checked)

    def set_checked(self, val: bool):
        self.checked = bool(val)
        if hasattr(self, "_img"):
            if self.checked:
                self._img.source = CHECKBOX_CHECKED_IMAGE if os.path.exists(CHECKBOX_CHECKED_IMAGE) else ""
            else:
                self._img.source = CHECKBOX_EMPTY_IMAGE if os.path.exists(CHECKBOX_EMPTY_IMAGE) else ""


# ---------------------------------------------------------------------------
# IconImageButton — یک دکمه‌ی تصویری ساده
# ---------------------------------------------------------------------------
class ThemeToggleButton(ButtonBehavior, Image):
    """دکمه‌ی چرخشی تعویض تم (خورشید/ماه) — سواپ عکس دقیقاً در ۱۸۰ درجه."""
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = True
        self._busy = False
        app = App.get_running_app()
        dark = bool(app.dark_mode) if app else False
        self.source = resolve_asset("moon" if dark else "sun")
        with self.canvas.before:
            PushMatrix()
            self._rot = Rotate(angle=0, origin=self.center)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_origin, size=self._update_origin,
                  angle=self._apply_angle)

    def _update_origin(self, *a):
        self._rot.origin = self.center

    def _apply_angle(self, *a):
        self._rot.origin = self.center
        self._rot.angle = self.angle

    def on_release(self):
        if self._busy:
            return
        self._busy = True
        self.angle = 0
        anim = Animation(angle=-180, duration=0.28, t="in_out_quad")
        anim.bind(on_complete=lambda *a: self._swap_half())
        anim.start(self)

    def _swap_half(self):
        app = App.get_running_app()
        new_dark = not bool(app.dark_mode) if app else True
        if app:
            app.dark_mode = new_dark
        self.source = resolve_asset("moon" if new_dark else "sun")
        if app:
            app.set_theme(app.active_gender)
        anim = Animation(angle=-360, duration=0.28, t="in_out_quad")
        anim.bind(on_complete=lambda *a: self._finish_spin())
        anim.start(self)

    def _finish_spin(self):
        self.angle = 0
        self._busy = False


class LinkLabel(ButtonBehavior, Label):
    """لیبل قابل کلیک با ناحیه‌ی لمسی قطعی.

    کل مستطیلِ لیبل (نه فقط دور حروف) لمس‌پذیر است و لمس با grab گرفته می‌شود تا
    ScrollViewِ والد نتواند لرزشِ کوچکِ انگشت را به‌عنوان اسکرول تفسیر کند و جلوی
    on_release را بگیرد (همان الگوی RTLTextInput).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.halign = kwargs.get("halign", "center")
        self.valign = kwargs.get("valign", "middle")
        # تضمین اینکه ناحیه‌ی متن دقیقاً برابر کل مستطیل ویجت باشد
        self.bind(size=self._sync_text_size, pos=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *a):
        try:
            self.text_size = self.size
        except Exception:
            pass

    def _touchable(self) -> bool:
        return (not self.disabled) and self.opacity > 0 and self.height > 1

    def on_touch_down(self, touch):
        if self._touchable() and self.collide_point(*touch.pos):
            touch.grab(self)
            self._pressed_inside = True
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if getattr(self, "_pressed_inside", False):
                self._pressed_inside = False
                if self._touchable() and self.collide_point(*touch.pos):
                    try:
                        self.dispatch("on_release")
                    except Exception:
                        pass
            return True
        return super().on_touch_up(touch)


class IconImageButton(ButtonBehavior, Image):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = True


# ---------------------------------------------------------------------------
# GenderImageButton
# ---------------------------------------------------------------------------
class GenderImageButton(ButtonBehavior, BoxLayout):
    selected = BooleanProperty(False)
    image_source = StringProperty("")
    label_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(8)] * 4
        self.spacing = dp(4)
        Clock.schedule_once(self._build, 0)
        self.bind(selected=self._update_canvas)

    def _build(self, dt):
        self._img = Image(source=self.image_source, size_hint_y=0.72,
                          allow_stretch=True, fit_mode="contain")
        self._lbl = Label(text=self.label_text, font_name=APP_FONT, font_size="14sp",
                          color=(0.4, 0.3, 0.35, 1), size_hint_y=0.28,
                          halign="center", valign="middle")
        self._lbl.bind(size=self._lbl.setter("text_size"))
        self.add_widget(self._img)
        self.add_widget(self._lbl)
        self._draw_bg()

    def _draw_bg(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*(theme["gender_sel"] if self.selected else (1, 1, 1, 0.7)))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(20)])
            Color(*(theme["gender_brd_sel"] if self.selected else (0.85, 0.8, 0.82, 1)))
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(20)), width=2)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *a):
        self._draw_bg()

    def _update_canvas(self, *a):
        self._draw_bg()


# ---------------------------------------------------------------------------
# RoundImage
# ---------------------------------------------------------------------------
class RoundImage(Image):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *a):
        self.canvas.before.clear()
        self.canvas.after.clear()
        with self.canvas.before:
            StencilPush()
            Ellipse(pos=self.pos, size=self.size)
            StencilUse()
        with self.canvas.after:
            StencilUnUse()
            Ellipse(pos=self.pos, size=self.size)
            StencilPop()


# ---------------------------------------------------------------------------
# RotatingIcon — آیکونی که می‌تواند ۳۶۰ درجه بچرخد
# ---------------------------------------------------------------------------
class RotatingIcon(Image):
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            PushMatrix()
            self._rot = Rotate(angle=0, origin=self.center)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._update_origin, size=self._update_origin,
                  angle=self._apply_angle)

    def _update_origin(self, *a):
        self._rot.origin = self.center

    def _apply_angle(self, *a):
        self._rot.origin = self.center
        self._rot.angle = self.angle

    def spin_once(self, callback=None):
        self.angle = 0
        anim = Animation(angle=-360, duration=0.5, t="in_out_quad")
        if callback:
            anim.bind(on_complete=lambda *a: callback())
        anim.start(self)


# ---------------------------------------------------------------------------
# ProfileAvatarButton
# ---------------------------------------------------------------------------
class ProfileAvatarButton(ButtonBehavior, BoxLayout):
    avatar_path = StringProperty("")
    ring_gender = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._photo = None
        Clock.schedule_once(self._build, 0)

    def _build(self, dt):
        app = App.get_running_app()
        if not self.ring_gender and app and app.current_user:
            self.avatar_path = app.current_user.get("avatar", "") or ""
        self._draw_ring()
        self._refresh_content()
        self.bind(pos=self._redraw, size=self._redraw,
                  avatar_path=lambda *a: self._refresh_content(),
                  ring_gender=lambda *a: self._draw_ring())

    def _draw_ring(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK
        if self.ring_gender == "male":
            ring = THEME_BLUE.get("avatar_ring", (0.42, 0.66, 0.87, 1))
        elif self.ring_gender == "female":
            ring = THEME_PINK.get("avatar_ring", (0.82, 0.55, 0.65, 1))
        else:
            ring = theme.get("avatar_ring", (0.82, 0.55, 0.65, 1))
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*ring)
            Ellipse(pos=self.pos, size=self.size)
            Color(*neutral("avatar_inner"))
            pad = dp(4)
            Ellipse(pos=(self.x + pad, self.y + pad),
                    size=(self.width - 2 * pad, self.height - 2 * pad))

    def _refresh_content(self, *a):
        self.clear_widgets()
        if self.avatar_path and os.path.exists(self.avatar_path):
            self._photo = RoundImage(source=self.avatar_path, size_hint=(1, 1),
                                     allow_stretch=True, keep_ratio=False)
            self.add_widget(self._photo)
        else:
            src = CAMERA_IMAGE if os.path.exists(CAMERA_IMAGE) else ""
            box = FloatLayout()
            icon = Image(source=src, size_hint=(None, None),
                         size=(dp(30), dp(30)), allow_stretch=True,
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
            box.add_widget(icon)
            self.add_widget(box)

    def _redraw(self, *a):
        self._draw_ring()

    def _refresh_theme(self, *a):
        self._draw_ring()


# ---------------------------------------------------------------------------
class ButtonBehavior_BoxLayout(ButtonBehavior, BoxLayout):
    pass


# ---------------------------------------------------------------------------
# PhotoSourceMenu
# ---------------------------------------------------------------------------
class PhotoSourceMenu(ModalView):
    def __init__(self, on_pick=None, **kwargs):
        super().__init__(**kwargs)
        self.on_pick = on_pick
        self.size_hint = (None, None)
        self.width = min(dp(320), Window.width * 0.86)
        self.height = dp(230)
        self.title = ""
        self.separator_height = 0
        self.background = ""
        # پس‌زمینه‌ی خودِ ModalView کاملاً شفاف تا مستطیل تیزگوشه دیده نشود؛
        # تیره کردن پشت صفحه با overlay_color انجام می‌شود.
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.45)
        self.auto_dismiss = True
        self._build()

    def _build(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK
        accent = theme["accent"]

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(0, 0, 0, 0.10)
            self._sh2 = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(0, 0, 0, 0.16)
            self._sh = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(*neutral("surface_glass"))
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(*neutral("glass_border"))
            self._brd = Line(rounded_rectangle=(root.x, root.y, root.width, root.height, dp(26)), width=1.4)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        title = Label(text=fa("انتخاب عکس پروفایل"), font_name=APP_FONT,
                      font_size="16sp", bold=True, color=neutral("text_primary"),
                      size_hint_y=None, height=dp(30), halign="center")
        title.bind(size=title.setter("text_size"))
        root.add_widget(title)

        cam_btn = self._glass_btn(fa("📷  عکس گرفتن با دوربین"), accent)
        cam_btn.bind(on_release=lambda *a: self._choose("camera"))
        root.add_widget(cam_btn)

        gal_btn = self._glass_btn(fa("🖼  انتخاب از گالری"), accent)
        gal_btn.bind(on_release=lambda *a: self._choose("gallery"))
        root.add_widget(gal_btn)

        self.add_widget(root)
        self._root = root

    def _glass_btn(self, text, accent):
        btn = ButtonBehavior_BoxLayout()
        btn.size_hint_y = None
        btn.height = dp(56)
        with btn.canvas.before:
            Color(accent[0], accent[1], accent[2], 0.85)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(18)])
        btn.bind(pos=lambda *a: self._upd_btn(btn), size=lambda *a: self._upd_btn(btn))
        lbl = Label(text=text, font_name=APP_FONT, font_size="15sp", bold=True,
                    color=(1, 1, 1, 1), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))
        btn.add_widget(lbl)
        return btn

    def _upd_bg(self, *a):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size
        try:
            self._sh.pos = (self._root.x + dp(2), self._root.y - dp(3))
            self._sh.size = self._root.size
            self._sh2.pos = (self._root.x + dp(4), self._root.y - dp(6))
            self._sh2.size = self._root.size
        except Exception:
            pass
        self._brd.rounded_rectangle = (self._root.x, self._root.y,
                                       self._root.width, self._root.height, dp(26))

    def _upd_btn(self, btn):
        btn._bg.pos = btn.pos
        btn._bg.size = btn.size

    def _refresh_theme(self, *a):
        try:
            self.clear_widgets()
            self._build()
        except Exception:
            pass

    def _choose(self, source):
        self.dismiss()
        if self.on_pick:
            self.on_pick(source)


# ---------------------------------------------------------------------------
# ConfirmDialog — دیالوگ تایید (برای حذف اکانت / حذف همدم)
# ---------------------------------------------------------------------------
class ConfirmDialog(ModalView):
    def __init__(self, message="", on_confirm=None, danger=True, **kwargs):
        super().__init__(**kwargs)
        self.on_confirm = on_confirm
        self.message = message
        self.danger = danger
        self.size_hint = (None, None)
        self.width = min(dp(320), Window.width * 0.86)
        self.height = dp(200)
        self.title = ""
        self.separator_height = 0
        self.background = ""
        self.background_color = (0, 0, 0, 0.5)
        self.auto_dismiss = True
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(*neutral("dialog_bg"))
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)])
        root.bind(pos=lambda *a: self._upd(root), size=lambda *a: self._upd(root))

        msg = Label(text=fa(self.message), font_name=APP_FONT, font_size="15sp",
                    bold=True, color=neutral("dialog_text"), halign="center",
                    valign="middle")
        msg.bind(size=msg.setter("text_size"))
        root.add_widget(msg)

        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))

        cancel = self._mk_btn(fa("انصراف"), (0.40, 0.40, 0.45, 1))
        cancel.bind(on_release=lambda *a: self.dismiss())
        btn_row.add_widget(cancel)

        ok_color = (0.80, 0.25, 0.25, 1) if self.danger else (0.30, 0.60, 0.40, 1)
        confirm = self._mk_btn(fa("تایید"), ok_color)
        confirm.bind(on_release=lambda *a: self._do_confirm())
        btn_row.add_widget(confirm)

        root.add_widget(btn_row)
        self.add_widget(root)
        self._root = root

    def _mk_btn(self, text, color):
        btn = ButtonBehavior_BoxLayout()
        with btn.canvas.before:
            Color(*color)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(14)])
        btn.bind(pos=lambda *a: self._upd_btn(btn, color),
                 size=lambda *a: self._upd_btn(btn, color))
        lbl = Label(text=text, font_name=APP_FONT, font_size="16sp", bold=True,
                    color=(1, 1, 1, 1), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))
        btn.add_widget(lbl)
        return btn

    def _upd(self, root):
        self._bg.pos = root.pos
        self._bg.size = root.size

    def _upd_btn(self, btn, color):
        btn.canvas.before.clear()
        with btn.canvas.before:
            Color(*color)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(14)])

    def _refresh_theme(self, *a):
        try:
            self.clear_widgets()
            self._build()
        except Exception:
            pass

    def _do_confirm(self):
        self.dismiss()
        if self.on_confirm:
            self.on_confirm()


# ---------------------------------------------------------------------------
# SettingsMenu — خروج + حذف اکانت + حذف/ترک همدم
# ---------------------------------------------------------------------------
class SettingsMenu(ModalView):
    def __init__(self, on_logout=None, on_delete=None, on_unlink=None,
                 has_partner=False, link_role="", **kwargs):
        super().__init__(**kwargs)
        self.on_logout = on_logout
        self.on_delete = on_delete
        self.on_unlink = on_unlink
        self.has_partner = has_partner
        self.link_role = link_role
        self.size_hint = (None, None)
        self.width = min(dp(310), Window.width * 0.85)
        # ارتفاع بسته به وجود همدم
        rows = 3 if has_partner else 2
        self.height = dp(70 + rows * 64)
        self.title = ""
        self.separator_height = 0
        self.background = ""
        # پس‌زمینه‌ی خودِ ModalView کاملاً شفاف تا مستطیل تیزگوشه دیده نشود؛
        # تیره کردن پشت صفحه با overlay_color انجام می‌شود.
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.45)
        self.auto_dismiss = True
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        with root.canvas.before:
            Color(0, 0, 0, 0.10)
            self._sh2 = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)])
            Color(0, 0, 0, 0.16)
            self._sh = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)])
            Color(*neutral("dialog_bg"))
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(22)])
            Color(*neutral("dialog_border"))
            self._brd = Line(rounded_rectangle=(root.x, root.y, root.width, root.height, dp(22)), width=1.2)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        title = Label(text=fa("تنظیمات"), font_name=APP_FONT, font_size="16sp",
                      bold=True, color=neutral("dialog_text"),
                      size_hint_y=None, height=dp(26), halign="center")
        title.bind(size=title.setter("text_size"))
        root.add_widget(title)

        # ── خروج از اکانت ──
        logout_btn = self._row_btn(fa("خروج از اکانت"),
                                   LOGOUT_IMAGE,
                                   (0.32, 0.32, 0.36, 1),
                                   (1, 0.92, 0.92, 1))
        logout_btn.bind(on_release=lambda *a: self._do(self.on_logout))
        root.add_widget(logout_btn)

        # ── حذف اکانت ──
        del_btn = self._row_btn(fa("حذف اکانت"),
                                GARBAGE_IMAGE,
                                (0.45, 0.20, 0.22, 1),
                                (1, 0.85, 0.85, 1))
        del_btn.bind(on_release=lambda *a: self._do(self.on_delete))
        root.add_widget(del_btn)

        # ── حذف همدم / ترک همدم (فقط در صورت داشتن همدم) ──
        if self.has_partner:
            if self.link_role == "owner":
                hd_text = "حذف همدم"
            else:
                hd_text = "ترک همدم"
            unlink_btn = self._row_btn(fa(hd_text),
                                       "",  # بدون آیکون خاص؛ از قلب استفاده می‌کنیم
                                       (0.30, 0.30, 0.40, 1),
                                       (1, 0.80, 0.85, 1),
                                       fallback_emoji="💔")
            unlink_btn.bind(on_release=lambda *a: self._do(self.on_unlink))
            root.add_widget(unlink_btn)

        self.add_widget(root)
        self._root = root

    def _row_btn(self, text, icon_path, bg_color, text_color, fallback_emoji=""):
        btn = ButtonBehavior_BoxLayout()
        btn.orientation = "horizontal"
        btn.size_hint_y = None
        btn.height = dp(54)
        btn.spacing = dp(10)
        btn.padding = [dp(12), dp(6)]
        with btn.canvas.before:
            Color(*bg_color)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(16)])
        btn.bind(pos=lambda *a: self._upd_btn(btn, bg_color),
                 size=lambda *a: self._upd_btn(btn, bg_color))

        # متن (سمت راست، وسط‌چین)
        lbl = Label(text=text, font_name=APP_FONT, font_size="15sp",
                    bold=True, color=text_color, halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))

        # آیکون (سمت چپ)
        wrap_icon = BoxLayout(size_hint_x=None, width=dp(40))
        if icon_path and os.path.exists(icon_path):
            icon = Image(source=icon_path, size_hint=(None, None),
                         size=(dp(28), dp(28)), allow_stretch=True, keep_ratio=True,
                         pos_hint={"center_y": 0.5})
            wrap_icon.add_widget(icon)
        elif fallback_emoji:
            em = Label(text=fallback_emoji, font_name="Roboto", font_size="22sp",
                       halign="center", valign="middle")
            em.bind(size=em.setter("text_size"))
            wrap_icon.add_widget(em)

        btn.add_widget(lbl)
        btn.add_widget(wrap_icon)
        return btn

    def _upd_bg(self, *a):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size
        try:
            self._sh.pos = (self._root.x + dp(2), self._root.y - dp(3))
            self._sh.size = self._root.size
            self._sh2.pos = (self._root.x + dp(4), self._root.y - dp(6))
            self._sh2.size = self._root.size
        except Exception:
            pass
        self._brd.rounded_rectangle = (self._root.x, self._root.y,
                                       self._root.width, self._root.height, dp(22))

    def _upd_btn(self, btn, color):
        btn.canvas.before.clear()
        with btn.canvas.before:
            Color(*color)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(16)])

    def _refresh_theme(self, *a):
        try:
            self.clear_widgets()
            self._build()
        except Exception:
            pass

    def _do(self, callback):
        self.dismiss()
        if callback:
            callback()


# ---------------------------------------------------------------------------
# PartnerMenu — صفحه شیشه‌ای «همدم»
# ---------------------------------------------------------------------------
class PartnerMenu(ModalView):
    def __init__(self, parent_popup=None, **kwargs):
        super().__init__(**kwargs)
        self.parent_popup = parent_popup
        self.size_hint = (None, None)
        self.width = min(dp(340), Window.width * 0.9)
        self.height = dp(430)
        self.title = ""
        self.separator_height = 0
        self.background = ""
        # پس‌زمینه‌ی خودِ ModalView کاملاً شفاف تا مستطیل تیزگوشه دیده نشود؛
        # تیره کردن پشت صفحه با overlay_color انجام می‌شود.
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.45)
        self.auto_dismiss = True
        self._generated_code = ""
        self._build()

    def _build(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK
        accent = theme["accent"]

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(0, 0, 0, 0.10)
            self._sh2 = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(0, 0, 0, 0.16)
            self._sh = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(*neutral("surface_glass"))
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(26)])
            Color(*neutral("glass_border"))
            self._brd = Line(rounded_rectangle=(root.x, root.y, root.width, root.height, dp(26)), width=1.4)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        title = Label(text=fa("همدم"), font_name=APP_FONT, font_size="20sp",
                      bold=True, color=neutral("text_primary"),
                      size_hint_y=None, height=dp(34), halign="center")
        title.bind(size=title.setter("text_size"))
        root.add_widget(title)

        make_btn = self._glass_btn(fa("ساخت لینک"), accent)
        make_btn.bind(on_release=lambda *a: self._make_link())
        root.add_widget(make_btn)

        self.code_box = BoxLayout(orientation="horizontal", size_hint_y=None,
                                  height=dp(54), spacing=dp(6), padding=[dp(12), dp(6)])
        with self.code_box.canvas.before:
            Color(*neutral("surface_soft"))
            self.code_box._bg = RoundedRectangle(pos=self.code_box.pos,
                                                 size=self.code_box.size, radius=[dp(16)])
        self.code_box.bind(pos=lambda *a: self._upd_simple(self.code_box),
                           size=lambda *a: self._upd_simple(self.code_box))

        self.code_label = Label(text=fa("کد اینجا نمایش داده می‌شود"),
                                font_name=APP_FONT, font_size="15sp", bold=True,
                                color=neutral("text_primary"), halign="center",
                                valign="middle")
        self.code_label.bind(size=self.code_label.setter("text_size"))

        copy_btn = ButtonBehavior_BoxLayout()
        copy_btn.size_hint_x = None
        copy_btn.width = dp(40)
        copy_src = COPY_IMAGE if os.path.exists(COPY_IMAGE) else ""
        copy_icon = Image(source=copy_src, size_hint=(None, None),
                          size=(dp(28), dp(28)), allow_stretch=True, keep_ratio=True,
                          pos_hint={"center_x": 0.5, "center_y": 0.5})
        cbox = FloatLayout()
        cbox.add_widget(copy_icon)
        copy_btn.add_widget(cbox)
        copy_btn.bind(on_release=lambda *a: self._copy_code())

        self.code_box.add_widget(self.code_label)
        self.code_box.add_widget(copy_btn)
        root.add_widget(self.code_box)

        connect_title = Label(text=fa("محل اتصال همدمت"), font_name=APP_FONT,
                              font_size="13sp", color=neutral("text_secondary"),
                              size_hint_y=None, height=dp(22), halign="center")
        connect_title.bind(size=connect_title.setter("text_size"))
        root.add_widget(connect_title)

        paste_wrap = BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(8), dp(4)])
        with paste_wrap.canvas.before:
            Color(*neutral("surface_soft"))
            paste_wrap._bg = RoundedRectangle(pos=paste_wrap.pos,
                                              size=paste_wrap.size, radius=[dp(16)])
        paste_wrap.bind(pos=lambda *a: self._upd_simple(paste_wrap),
                        size=lambda *a: self._upd_simple(paste_wrap))
        self.paste_input = TextInput(hint_text=fa("کد همدم را اینجا پیست کن"),
                                     font_name=APP_FONT, font_size="15sp",
                                     multiline=False, background_color=(0, 0, 0, 0),
                                     foreground_color=neutral("text_primary"),
                                     hint_text_color=neutral("text_hint"),
                                     cursor_color=(0.6, 0.4, 0.5, 1),
                                     halign="center", padding=[dp(8), dp(12)])
        paste_wrap.add_widget(self.paste_input)
        root.add_widget(paste_wrap)

        connect_btn = self._glass_btn(fa("اتصال"), accent)
        connect_btn.bind(on_release=lambda *a: self._connect())
        root.add_widget(connect_btn)

        self.add_widget(root)
        self._root = root

    def _glass_btn(self, text, accent):
        btn = ButtonBehavior_BoxLayout()
        btn.size_hint_y = None
        btn.height = dp(50)
        with btn.canvas.before:
            Color(accent[0], accent[1], accent[2], 0.9)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(18)])
        btn.bind(pos=lambda *a: self._upd_simple(btn), size=lambda *a: self._upd_simple(btn))
        lbl = Label(text=text, font_name=APP_FONT, font_size="16sp", bold=True,
                    color=(1, 1, 1, 1), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))
        btn.add_widget(lbl)
        return btn

    def _upd_bg(self, *a):
        self._bg.pos = self._root.pos
        self._bg.size = self._root.size
        try:
            self._sh.pos = (self._root.x + dp(2), self._root.y - dp(3))
            self._sh.size = self._root.size
            self._sh2.pos = (self._root.x + dp(4), self._root.y - dp(6))
            self._sh2.size = self._root.size
        except Exception:
            pass
        self._brd.rounded_rectangle = (self._root.x, self._root.y,
                                       self._root.width, self._root.height, dp(26))

    def _upd_simple(self, w):
        w._bg.pos = w.pos
        w._bg.size = w.size

    def _refresh_theme(self, *a):
        try:
            _code = self._generated_code
            _pasted = self.paste_input.text if getattr(self, "paste_input", None) else ""
            self.clear_widgets()
            self._build()
            self._generated_code = _code
            if _code:
                self.code_label.text = _code
            if _pasted:
                self.paste_input.text = _pasted
        except Exception:
            pass

    def _toast(self, text):
        show_themed_toast(text)

    def _make_link(self):
        app = App.get_running_app()
        uname = app.current_user.get("username", "")
        if not uname:
            self._toast(fa("ابتدا وارد شوید"))
            return
        acc = get_account(uname)
        if acc.get("partner"):
            self._toast(fa("شما قبلاً همدم دارید"))
            return
        code = generate_link_code(uname)
        if code:
            self._generated_code = code
            self.code_label.text = code

    def _copy_code(self):
        if not self._generated_code:
            self._toast(fa("ابتدا یک لینک بساز"))
            return
        if _CLIPBOARD_AVAILABLE:
            try:
                Clipboard.copy(self._generated_code)
                self._toast(fa("کد کپی شده"))
                return
            except Exception:
                pass
        self._toast(fa("کپی ممکن نشد"))

    def _connect(self):
        app = App.get_running_app()
        uname = app.current_user.get("username", "")
        code = self.paste_input.text.strip()
        ok, msg, partner = connect_partner(uname, code)
        if not ok:
            self._toast(fa(msg))
            return
        app.current_user = dict(get_account(uname))
        self._toast(fa(msg))
        self.dismiss()
        if self.parent_popup:
            try:
                self.parent_popup.dismiss()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CategoryCard
# ---------------------------------------------------------------------------
class CategoryCard(BoxLayout):
    title_text = StringProperty("")
    subtitle_text = StringProperty("")
    emoji_text = StringProperty("")
    icon_source = StringProperty("")
    card_color = ListProperty([1, 1, 1, 1])
    category_id = StringProperty("")

    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos):
            App.get_running_app().root.get_screen("categories").open_category(self.category_id)
            return True
        return False


# ---------------------------------------------------------------------------
# ProfileMenuPopup
# ---------------------------------------------------------------------------
class ProfileMenuPopup(Popup):
    def __init__(self, user: dict, parent_screen=None, **kwargs):
        super().__init__(**kwargs)
        self.title = ""
        self.separator_height = 0
        self.size_hint = (0.92, 0.74)
        self.pos_hint = {"center_x": 0.5, "top": 0.97}
        self.user = user
        self.parent_screen = parent_screen
        self.background = ""
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK
        self.background_color = (theme["bg"][0], theme["bg"][1], theme["bg"][2], 1)
        self._build_content()

    def _build_content(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_PINK

        # ارتفاع داینامیک: با وجود همدم، بخش اطلاعات یک ردیف بیشتر دارد (rows=5)
        # و محتوا از کادر گرد بیرون می‌زد (دکمه‌ی تنظیمات دیده نمی‌شد).
        partner = get_partner_account(self.user.get("username", ""))
        rows = 5 if partner else 4
        _extra = dp(34) * (rows - 4)
        _target_h = min(Window.height * 0.94, Window.height * 0.74 + _extra)
        self.size_hint = (0.92, None)
        self.height = _target_h

        root = BoxLayout(orientation="vertical", spacing=dp(12), padding=[dp(18), dp(18)])
        with root.canvas.before:
            Color(*theme["bg"])
            self._root_bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(28)])
        root.bind(pos=self._upd_root_bg, size=self._upd_root_bg)

        # ── ردیف بالا: دکمه setting چرخان (در مربع شیشه‌ای گرد) ──
        top_row = FloatLayout(size_hint_y=None, height=dp(48))
        setting_btn = ButtonBehavior_BoxLayout()
        setting_btn.size_hint = (None, None)
        setting_btn.size = (dp(46), dp(46))
        setting_btn.pos_hint = {"right": 1, "top": 1}
        with setting_btn.canvas.before:
            Color(*neutral("surface_soft"))
            setting_btn._glass_bg = RoundedRectangle(
                pos=setting_btn.pos, size=setting_btn.size, radius=[dp(14)])
            Color(*neutral("glass_border"))
            setting_btn._glass_brd = Line(
                rounded_rectangle=(setting_btn.x, setting_btn.y,
                                   setting_btn.width, setting_btn.height, dp(14)),
                width=1.2)
        def _upd_glass(*_a, _b=setting_btn):
            _b._glass_bg.pos = _b.pos
            _b._glass_bg.size = _b.size
            _b._glass_brd.rounded_rectangle = (_b.x, _b.y, _b.width, _b.height, dp(14))
        setting_btn.bind(pos=_upd_glass, size=_upd_glass)
        s_src = SETTING_IMAGE if os.path.exists(SETTING_IMAGE) else ""
        self.setting_icon = RotatingIcon(source=s_src, size_hint=(None, None),
                                         size=(dp(34), dp(34)), allow_stretch=True,
                                         keep_ratio=True,
                                         pos_hint={"center_x": 0.5, "center_y": 0.5})
        sbox = FloatLayout()
        sbox.add_widget(self.setting_icon)
        setting_btn.add_widget(sbox)
        setting_btn.bind(on_release=lambda *a: self._spin_and_open_settings())
        top_row.add_widget(setting_btn)
        root.add_widget(top_row)

        # ── آواتار(ها) ──
        avatar_row = FloatLayout(size_hint_y=None, height=dp(120))

        if partner:
            me_gender = self.user.get("gender", "")
            self.avatar = ProfileAvatarButton(size_hint=(None, None), size=(dp(92), dp(92)),
                                              pos_hint={"center_x": 0.30, "center_y": 0.5})
            self.avatar.ring_gender = me_gender
            self.avatar.avatar_path = self.user.get("avatar", "")
            self.avatar.bind(on_release=lambda *a: self._open_photo_menu())
            avatar_row.add_widget(self.avatar)

            partner_avatar = ProfileAvatarButton(size_hint=(None, None), size=(dp(92), dp(92)),
                                                 pos_hint={"center_x": 0.70, "center_y": 0.5})
            partner_avatar.ring_gender = partner.get("gender", "")
            partner_avatar.avatar_path = partner.get("avatar", "")
            avatar_row.add_widget(partner_avatar)
        else:
            self.avatar = ProfileAvatarButton(size_hint=(None, None), size=(dp(96), dp(96)),
                                              pos_hint={"center_x": 0.5, "center_y": 0.5})
            self.avatar.ring_gender = self.user.get("gender", "")
            self.avatar.avatar_path = self.user.get("avatar", "")
            self.avatar.bind(on_release=lambda *a: self._open_photo_menu())
            avatar_row.add_widget(self.avatar)

        root.add_widget(avatar_row)

        hint_text = "خورشید و ماه کنار هم 💞" if partner else "برای تغییر عکس روی دایره بزنید"
        hint = Label(text=fa(hint_text), font_name=APP_FONT,
                     font_size="11sp", color=neutral("text_secondary"),
                     size_hint_y=None, height=dp(18), halign="center")
        hint.bind(size=hint.setter("text_size"))
        root.add_widget(hint)

        info = self._make_section(self.user, partner)
        root.add_widget(info)

        # فضای انعطاف‌پذیر تا دکمه‌ها بیایند پایین
        root.add_widget(BoxLayout())

        # ── دکمه‌ی «ویرایش پروفایل» — دقیقاً بالای ردیف بازگشت/همدم ──
        edit_row = FloatLayout(size_hint_y=None, height=dp(50))
        edit_btn = self._make_btn(fa("ویرایش پروفایل"), theme["accent"], font_size="15sp")
        edit_btn.size_hint = (None, None)
        edit_btn.width = dp(220)
        edit_btn.height = dp(44)
        edit_btn.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        edit_btn.bind(on_release=lambda *a: self._open_edit_profile())
        edit_row.add_widget(edit_btn)
        root.add_widget(edit_row)

        # ── دکمه‌های پایین: بازگشت + همدم (کوچک‌تر، متن وسط و بزرگ‌تر) ──
        btn_row = FloatLayout(size_hint_y=None, height=dp(50))
        # یک ردیف افقی وسط‌چین با عرض محدود
        inner = BoxLayout(orientation="horizontal", spacing=dp(12),
                          size_hint=(None, None), height=dp(46),
                          width=dp(230),
                          pos_hint={"center_x": 0.5, "center_y": 0.5})

        back_btn = self._make_btn(fa("بازگشت"), theme["accent"], font_size="16sp")
        back_btn.size_hint_x = None
        back_btn.width = dp(105)
        back_btn.bind(on_release=lambda *a: self.dismiss())
        inner.add_widget(back_btn)

        hamdam_btn = self._make_btn(fa("همدم"), theme["accent"], font_size="16sp")
        hamdam_btn.size_hint_x = None
        hamdam_btn.width = dp(105)
        hamdam_btn.bind(on_release=lambda *a: self._open_partner_menu())
        inner.add_widget(hamdam_btn)

        btn_row.add_widget(inner)
        root.add_widget(btn_row)

        self.content = root

    def _refresh_theme(self, *a):
        try:
            _app = App.get_running_app()
            _th = _app.current_theme if _app else THEME_PINK
            self.background_color = (_th["bg"][0], _th["bg"][1], _th["bg"][2], 1)
            self._build_content()
        except Exception:
            pass

    def _upd_root_bg(self, *a):
        self._root_bg.pos = self.content.pos
        self._root_bg.size = self.content.size

    def _spin_and_open_settings(self):
        # چرخش ۳۶۰ درجه سپس باز شدن منوی تنظیمات
        if hasattr(self, "setting_icon"):
            self.setting_icon.spin_once(callback=self._open_settings)
        else:
            self._open_settings()

    def _open_partner_menu(self):
        menu = PartnerMenu(parent_popup=self)
        menu.open()

    def _open_edit_profile(self):
        app = App.get_running_app()
        self.dismiss()
        try:
            scr = app.root.get_screen("edit_profile")
            scr.parent_screen = self.parent_screen
            scr.load_user()
            app.root.transition = SlideTransition(direction="left")
            app.root.current = "edit_profile"
        except Exception as e:
            print("[EditProfile] open failed:", e)

    def _open_settings(self):
        uname = self.user.get("username", "")
        acc = get_account(uname)
        has_partner = bool(acc.get("partner"))
        link_role = acc.get("link_role", "")
        menu = SettingsMenu(on_logout=self._logout,
                            on_delete=self._confirm_delete,
                            on_unlink=self._confirm_unlink,
                            has_partner=has_partner,
                            link_role=link_role)
        menu.open()

    def _logout(self):
        app = App.get_running_app()
        clear_session()
        app.skip_autologin = True
        app.current_user = {}
        app.active_gender = ""
        self.dismiss()
        if self.parent_screen and self.parent_screen.manager:
            self.parent_screen.manager.transition = SlideTransition(direction="right")
            self.parent_screen.manager.current = "login"

    # ── حذف اکانت ──
    def _confirm_delete(self):
        dlg = ConfirmDialog(message="آیا از حذف کامل اکانت مطمئنی؟ این کار قابل بازگشت نیست!",
                            on_confirm=self._do_delete, danger=True)
        dlg.open()

    def _do_delete(self):
        app = App.get_running_app()
        uname = self.user.get("username", "")
        ok, msg = delete_account(uname)
        clear_session()
        app.skip_autologin = True
        app.current_user = {}
        app.active_gender = ""
        self.dismiss()
        if self.parent_screen and self.parent_screen.manager:
            self.parent_screen.manager.transition = SlideTransition(direction="right")
            self.parent_screen.manager.current = "login"

    # ── حذف / ترک همدم ──
    def _confirm_unlink(self):
        uname = self.user.get("username", "")
        acc = get_account(uname)
        role = acc.get("link_role", "")
        if role == "owner":
            msg = "همدمت حذف شود و اکانت مستقل گردد؟"
        else:
            msg = "از این اکانت مشترک خارج می‌شوی و مستقل می‌گردی؟"
        dlg = ConfirmDialog(message=msg, on_confirm=self._do_unlink, danger=True)
        dlg.open()

    def _do_unlink(self):
        app = App.get_running_app()
        uname = self.user.get("username", "")
        ok, msg = unlink_partner(uname)
        # به‌روزرسانی اطلاعات کاربر فعلی
        app.current_user = dict(get_account(uname))
        self.dismiss()
        if self.parent_screen:
            self.parent_screen.refresh_avatar_area()
            self.parent_screen._toast(fa(msg))

    def _open_photo_menu(self):
        menu = PhotoSourceMenu(on_pick=self._handle_photo_source)
        menu.open()

    def _handle_photo_source(self, source):
        if source == "camera":
            self._take_photo()
        else:
            self._pick_gallery()

    def _take_photo(self):
        target = os.path.join(SAVE_DIR, "camera_temp.png")
        if _PLYER_AVAILABLE:
            try:
                plyer_camera.take_picture(filename=target,
                                          on_complete=lambda path: self._after_capture(path))
                return
            except Exception as e:
                self._toast(fa(f"دوربین در دسترس نیست: {e}"))
        else:
            self._toast(fa("دوربین فقط روی گوشی کار می‌کند"))

    def _after_capture(self, path):
        Clock.schedule_once(lambda dt: self._apply_photo(path), 0)

    def _pick_gallery(self):
        if _PLYER_AVAILABLE:
            try:
                plyer_filechooser.open_file(on_selection=self._after_gallery,
                                            filters=[["Images", "*.png", "*.jpg", "*.jpeg"]])
                return
            except Exception as e:
                self._toast(fa(f"گالری در دسترس نیست: {e}"))
        else:
            self._toast(fa("گالری فقط روی گوشی کار می‌کند"))

    def _after_gallery(self, selection):
        if selection:
            Clock.schedule_once(lambda dt: self._apply_photo(selection[0]), 0)

    def _apply_photo(self, path):
        uname = self.user.get("username", "")
        saved_path, msg = process_and_save_avatar(path, uname)
        if not saved_path:
            self._toast(fa(msg))
            return

        self.user["avatar"] = saved_path
        self.avatar.avatar_path = saved_path
        update_account_avatar(uname, saved_path)

        app = App.get_running_app()
        if app.current_user:
            app.current_user["avatar"] = saved_path

        if self.parent_screen:
            self.parent_screen.refresh_avatar_area()

        # تلاش آپلود به سرور را در پس‌زمینه انجام بده ولی همیشه پیام موفقیت محلی نشان بده
        try:
            upload_avatar(saved_path)
        except Exception:
            pass
        self._toast(fa("عکس شما با موفقیت آپلود شد ✓"))

    def _toast(self, text):
        show_themed_toast(text)

    def _make_section(self, data, partner=None):
        rows = 4 if not partner else 5
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        padding=[dp(14), dp(12)], size_hint_y=None,
                        height=dp(30 * rows + 30))
        color = neutral("info_male") if data.get("gender") == "male" else neutral("info_female")
        with box.canvas.before:
            Color(*color)
            RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(18)])
        box.bind(pos=lambda *a: self._redraw_bg(box, color),
                 size=lambda *a: self._redraw_bg(box, color))

        gender_txt = "☀️ خورشید (پسر)" if data.get("gender") == "male" else "🌙 ماه (دختر)"
        g_lbl = Label(text=fa(gender_txt), font_name=APP_FONT, font_size="15sp", bold=True,
                      color=neutral("text_primary"), halign="right",
                      size_hint_y=None, height=dp(26))
        g_lbl.bind(size=g_lbl.setter("text_size"))
        box.add_widget(g_lbl)

        u_lbl = Label(text=fa(f"نام کاربری: {data.get('username','')}"), font_name=APP_FONT,
                      font_size="13sp", color=neutral("text_primary"), halign="right",
                      size_hint_y=None, height=dp(24))
        u_lbl.bind(size=u_lbl.setter("text_size"))
        box.add_widget(u_lbl)

        a_lbl = Label(text=fa(f"سن: {data.get('age','')}"), font_name=APP_FONT,
                      font_size="13sp", color=neutral("text_primary"), halign="right",
                      size_hint_y=None, height=dp(24))
        a_lbl.bind(size=a_lbl.setter("text_size"))
        box.add_widget(a_lbl)

        fn_lbl = Label(text=fa(f"نام و نام خانوادگی: {data.get('full_name','')}"), font_name=APP_FONT,
                       font_size="13sp", color=neutral("text_primary"), halign="right",
                       size_hint_y=None, height=dp(24))
        fn_lbl.bind(size=fn_lbl.setter("text_size"))
        box.add_widget(fn_lbl)

        if partner:
            partner_txt = f"همدم: {partner.get('username','')}"
            hp_lbl = Label(text=fa(partner_txt), font_name=APP_FONT, font_size="13sp",
                           bold=True, color=neutral("text_strong"), halign="right",
                           size_hint_y=None, height=dp(24))
            hp_lbl.bind(size=hp_lbl.setter("text_size"))
            box.add_widget(hp_lbl)

        return box

    def _redraw_bg(self, box, color):
        box.canvas.before.clear()
        with box.canvas.before:
            Color(*color)
            RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(18)])

    def _make_btn(self, text, color, font_size="15sp"):
        btn = ButtonBehavior_BoxLayout()
        btn.size_hint_y = None
        btn.height = dp(46)
        with btn.canvas.before:
            Color(*color)
            btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(16)])
        btn.bind(pos=lambda *a: self._redraw_btn(btn, color),
                 size=lambda *a: self._redraw_btn(btn, color))
        lbl = Label(text=text, font_name=APP_FONT, font_size=font_size, bold=True,
                    color=(1, 1, 1, 1), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))
        btn.add_widget(lbl)
        return btn

    def _redraw_btn(self, btn, color):
        btn.canvas.before.clear()
        with btn.canvas.before:
            Color(*color)
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(16)])


# ---------------------------------------------------------------------------
# CategoriesScreen
# ---------------------------------------------------------------------------
class CategoriesScreen(Screen):
    def on_pre_enter(self, *args):
        self.populate_categories()
        self.refresh_avatar_area()

    def _toast(self, text):
        p = Popup(title="", separator_height=0,
                  content=Label(text=text, font_name=APP_FONT, halign="center",
                                color=(1, 1, 1, 1)),
                  size_hint=(0.8, 0.22))
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 2.0)

    def refresh_avatar_area(self):
        app = App.get_running_app()
        user = app.current_user or {}
        # رفرش اطلاعات از دیتابیس
        uname = user.get("username", "")
        if uname:
            app.current_user = dict(get_account(uname))
            user = app.current_user

        holder = self.ids.avatar_holder
        holder.clear_widgets()

        partner = get_partner_account(user.get("username", ""))

        if partner:
            my_btn = ProfileAvatarButton(size_hint=(None, None), size=(dp(78), dp(78)),
                                         pos_hint={"center_x": 0.36, "center_y": 0.5})
            my_btn.ring_gender = user.get("gender", "")
            my_btn.avatar_path = user.get("avatar", "") or ""
            my_btn.bind(on_release=lambda *a: self.open_profile_menu())
            holder.add_widget(my_btn)

            p_btn = ProfileAvatarButton(size_hint=(None, None), size=(dp(78), dp(78)),
                                        pos_hint={"center_x": 0.64, "center_y": 0.5})
            p_btn.ring_gender = partner.get("gender", "")
            p_btn.avatar_path = partner.get("avatar", "") or ""
            p_btn.bind(on_release=lambda *a: self.open_profile_menu())
            holder.add_widget(p_btn)

            self._profile_refs = [my_btn, p_btn]
        else:
            single = ProfileAvatarButton(size_hint=(None, None), size=(dp(84), dp(84)),
                                         pos_hint={"center_x": 0.5, "center_y": 0.5})
            single.ring_gender = user.get("gender", "")
            single.avatar_path = user.get("avatar", "") or ""
            single.bind(on_release=lambda *a: self.open_profile_menu())
            holder.add_widget(single)
            self._profile_refs = [single]

        Clock.schedule_once(lambda dt: [b._draw_ring() for b in self._profile_refs], 0)

    def populate_categories(self):
        grid = self.ids.categories_grid
        grid.clear_widgets()
        try:
            _u = App.get_running_app().current_user or {}
            user_age = int(_u.get("age", 20) or 20)
        except Exception:
            user_age = 20
        for cat in CATEGORIES:
            mn = cat.get("min_age")
            mx = cat.get("max_age")
            if mn is not None and user_age < mn:
                continue
            if mx is not None and user_age > mx:
                continue
            icon = cat.get("icon")
            icon_src = icon if (icon and os.path.exists(icon)) else ""
            card = CategoryCard(
                title_text=fa(cat["title"]),
                subtitle_text=fa(cat["subtitle"]),
                emoji_text=cat["emoji"],
                icon_source=icon_src,
                card_color=cat["color"],
                category_id=cat["id"],
            )
            grid.add_widget(card)


    def open_profile_menu(self):
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        if uname:
            app.current_user = dict(get_account(uname))
        user = app.current_user or {}
        popup = ProfileMenuPopup(user=user, parent_screen=self)
        popup.bind(on_dismiss=lambda *a: self.refresh_avatar_area())
        popup.open()

    def open_category(self, category_id):
        app = App.get_running_app()
        if category_id == "diary":
            try:
                scr = app.root.get_screen("diary")
                scr.refresh_list()
            except Exception as e:
                print("[open_category diary]", e)
            app.root.transition = SlideTransition(direction="left")
            app.root.current = "diary"
            return
        cat = next(c for c in CATEGORIES if c["id"] == category_id)
        ideas_screen = app.root.get_screen("ideas")
        ideas_screen.load_category(cat)
        app.root.current = "ideas"



# ---------------------------------------------------------------------------
# IdeaCard + IdeasScreen (اضافه‌شده از نسخه‌ی Flet)
# ---------------------------------------------------------------------------
class IdeaCard(ButtonBehavior, BoxLayout):
    is_done = BooleanProperty(False)
    title_text = StringProperty("")
    desc_text  = StringProperty("")
    border_color = ListProperty([0.9, 0.4, 0.25, 1])
    category_id = StringProperty("")
    raw_title = StringProperty("")
    raw_desc  = StringProperty("")
    raw_idea = ObjectProperty(None, allownone=True)

    def on_release(self):
        app = App.get_running_app()
        # اگر صفحه‌ی ایده‌ها در حالت قفل/انیمیشن باشد، فقط برنده قابل کلیک است
        try:
            ideas_scr = app.root.get_screen("ideas")
            if getattr(ideas_scr, "_spinning", False):
                return
            if getattr(ideas_scr, "locked", False) and getattr(ideas_scr, "_winner_card", None) is not self:
                return
        except Exception:
            pass
        try:
            scr = app.root.get_screen("idea_detail")
            scr.load_idea(self.category_id, self.raw_idea)
            app.root.current = "idea_detail"
        except Exception as e:
            print("[IdeaCard] open detail failed:", e)


class IdeasScreen(Screen):
    current_category_id = StringProperty("")
    _spin_event = None
    _spinning = BooleanProperty(False)
    locked = BooleanProperty(False)
    _winner_card = ObjectProperty(None, allownone=True)
    show_add_button = BooleanProperty(True)

    def load_category(self, cat):
        self.current_category_id = cat["id"]
        # دکمه‌ی «افزودن ایده‌ی شخصی» فقط در دسته‌ی home برای سنین زیر ۲۰ سال مخفی می‌شود.
        try:
            _age_val = int((App.get_running_app().current_user or {}).get("age", 20) or 20)
        except Exception:
            _age_val = 20
        self.show_add_button = (cat["id"] != "home") or (_age_val >= 20)
        self.ids.title_lbl.text    = fa(f'{cat["emoji"]}  {cat["title"]}')
        self.ids.subtitle_lbl.text = fa(cat["subtitle"])
        box = self.ids.ideas_box
        box.clear_widgets()
        self._cards = []
        # ریست حالت قفل/انیمیشن
        self._cancel_spin_animation()
        self.locked = False
        self._winner_card = None
        # دسته‌های وابسته به سن: «هیجانی و فعال» و «خلاقانه و هنری»
        _app = App.get_running_app()
        _age = (getattr(_app, "current_user", None) or {}).get("age", 20)
        if cat["id"] == "active":
            ideas_list = get_active_ideas(_age)
        elif cat["id"] == "creative":
            ideas_list = get_creative_ideas(_age)
        elif cat["id"] == "food":
            ideas_list = get_food_ideas(_age)
        elif cat["id"] == "home":
            ideas_list = get_home_ideas(_age)
        elif cat["id"] == "nature":
            ideas_list = get_nature_ideas(_age)
        else:
            ideas_list = IDEAS.get(cat["id"], [])

        # ایده‌های شخصیِ کاربر برای همین دسته
        try:
            _u = (App.get_running_app().current_user or {}).get("username", "")
            _personal = load_personal_ideas(_u, cat["id"]) if _u else []
            if _personal:
                ideas_list = list(ideas_list) + list(_personal)
        except Exception as _e:
            print("[Ideas.load_category] personal:", _e)

        # وضعیت خالی برای دیت‌های خانگیِ زیر ۲۰ سال: پیام مخصوص وسط صفحه
        if cat["id"] == "home" and not ideas_list:
            empty = Label(
                text=fa("خونه هیچی نداره، برو دنیا رو ببین!"),
                font_name=APP_FONT, font_size="18sp", bold=True,
                color=neutral("text_strong"),
                size_hint_y=None, height=dp(420),
                halign="center", valign="middle",
            )
            empty.bind(size=lambda i, v: setattr(i, "text_size", v))
            box.add_widget(empty)
            return

        for idea in ideas_list:
            _done_flag = False
            try:
                _u2 = (App.get_running_app().current_user or {}).get("username", "")
                _done_flag = is_idea_done(_u2, cat["id"], idea["title"]) if _u2 else False
            except Exception:
                _done_flag = False
            card = IdeaCard(
                is_done=_done_flag,
                title_text=fa(idea["title"]),
                desc_text=fa(idea["desc"]),
                border_color=list(idea["border"]),
                category_id=cat["id"],
                raw_title=idea["title"],
                raw_desc=idea["desc"],
                raw_idea=idea,
            )
            tags_box = card.ids.tags_box
            for txt, bg, fg in idea["tags"]:
                # FloatLayout به‌جای BoxLayout تا حلقه‌ی فیدبک سایز
                # (label.texture_size -> box.width -> label.size -> ...) شکسته شود.
                tag = FloatLayout(size_hint_x=None, width=dp(70))
                with tag.canvas.before:
                    Color(*bg)
                    rr = RoundedRectangle(pos=tag.pos, size=tag.size, radius=[dp(12)])
                def _upd(inst, _v, _rr=rr):
                    _rr.pos = inst.pos; _rr.size = inst.size
                tag.bind(pos=_upd, size=_upd)
                lbl = Label(text=fa(txt), font_name=APP_FONT, font_size="11sp",
                            color=fg, halign="center", valign="middle",
                            size_hint=(None, None),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})
                # فقط یک‌طرفه: texture_size -> سایز لیبل و عرض کانتینر
                def _sync(inst, ts, _tag=tag):
                    inst.size = ts
                    _tag.width = ts[0] + dp(20)
                lbl.bind(texture_size=_sync)
                _sync(lbl, lbl.texture_size)
                tag.add_widget(lbl)
                tags_box.add_widget(tag)
            # spacer
            tags_box.add_widget(BoxLayout())
            box.add_widget(card)
            self._cards.append(card)

    def _cancel_spin_animation(self):
        """متوقف کردن کامل انیمیشن رندوم و پاکسازی overlay (در صورت وجود)."""
        if self._spin_event:
            try:
                self._spin_event.cancel()
            except Exception:
                pass
            self._spin_event = None
        overlay = getattr(self, "_spin_overlay", None)
        scatters = getattr(self, "_spin_scatters", None) or []
        cards = getattr(self, "_spin_cards", None) or []
        box = getattr(self, "_spin_box", None)
        # کنسل انیمیشن‌های در حال اجرا
        for sc in scatters:
            try:
                Animation.cancel_all(sc)
            except Exception:
                pass
        # بازگرداندن کارت‌ها به BoxLayout اگر بیرون افتاده باشن
        if box is not None and cards:
            for sc, card in zip(scatters, cards):
                try:
                    sc.remove_widget(card)
                except Exception:
                    pass
                try:
                    card.size_hint = (1, None)
                    card.height = dp(170)
                    card.opacity = 1.0
                except Exception:
                    pass
                # فقط اگر هنوز در ساختار نیست، اضافه کن
                if card.parent is None:
                    box.add_widget(card, index=0)
        if overlay is not None:
            try:
                Window.remove_widget(overlay)
            except Exception:
                pass
        self._spin_overlay = None
        self._spin_scatters = None
        self._spin_cards = None
        self._spin_slots = None
        self._spin_box = None
        self._spinning = False

    def go_back(self):
        # اگر وسط انیمیشن دکمه بک بزنه: همه چی کنسل و صفحه عوض شه
        self._cancel_spin_animation()
        self.locked = False
        self._winner_card = None
        # بازنشانی شفافیت کارت‌ها
        try:
            for c in self.ids.ideas_box.children:
                c.opacity = 1.0
        except Exception:
            pass
        App.get_running_app().root.current = "categories"

    def open_add_idea(self):
        try:
            app = App.get_running_app()
            scr = app.root.get_screen("add_idea")
            scr.category_id = self.current_category_id
            app.root.transition = SlideTransition(direction="left")
            app.root.current = "add_idea"
        except Exception as e:
            print("[Ideas.open_add_idea] failed:", e)

    def open_help(self):
        try:
            app = App.get_running_app()
            help_scr = app.root.get_screen("help")
            help_scr.set_source("ideas")
            app.root.transition = SlideTransition(direction="left")
            app.root.current = "help"
        except Exception as e:
            print("[Ideas.open_help] failed:", e)

    # ---------------- Random spin animation (smooth, ~3s) ----------------
    def do_random_spin(self):
        # اول اسکرول رو سریع برگردون بالا، بعد رندوم رو شروع کن
        try:
            sv = self.ids.ideas_scroll
            if sv.scroll_y < 0.995:
                Animation.cancel_all(sv, "scroll_y")
                anim = Animation(scroll_y=1.0, duration=0.35, t="out_quad")
                anim.bind(on_complete=lambda *a: self._do_random_spin_real())
                anim.start(sv)
                return
        except Exception:
            pass
        self._do_random_spin_real()

    def _do_random_spin_real(self):
        # اگر در حال انیمیشن: کنسل و شروع دوباره
        if self._spinning:
            self._cancel_spin_animation()
        # ریست حالت قفل قبلی
        self.locked = False
        self._winner_card = None

        box = self.ids.ideas_box
        cards = [c for c in reversed(box.children) if isinstance(c, IdeaCard)]
        if len(cards) < 2:
            return
        self._spinning = True

        # Reset previous highlight / size
        for c in cards:
            c.opacity = 1
            try:
                c.height = dp(170)
            except Exception:
                pass

        # Capture window-space positions/sizes (top->bottom)
        slots = []
        for c in cards:
            wx, wy = c.to_window(c.x, c.y)
            slots.append((wx, wy, c.width, c.height))

        overlay = FloatLayout(size=Window.size, pos=(0, 0))
        Window.add_widget(overlay)

        scatters = []
        for c, (x, y, w, h) in zip(cards, slots):
            box.remove_widget(c)
            c.size_hint = (None, None)
            c.size = (w, h)
            c.pos = (0, 0)
            scat = Scatter(do_rotation=False, do_scale=False, do_translation=False,
                           size_hint=(None, None), size=(w, h), pos=(x, y),
                           auto_bring_to_front=False)
            scat.add_widget(c)
            overlay.add_widget(scat)
            scatters.append(scat)

        self._spin_overlay = overlay
        self._spin_box = box
        self._spin_slots = slots
        self._spin_scatters = scatters
        self._spin_cards = cards
        self._spin_ticks = 0
        # کلِ انیمیشن حدوداً ۳ ثانیه؛ هر تیک کاملاً نرم
        self._spin_max = 10
        self._spin_interval = 0.28  # 10 * 0.28 ≈ 2.8s سپس finish
        self._spin_event = Clock.schedule_interval(self._spin_tick, self._spin_interval)
        Clock.schedule_once(lambda *a: self._spin_tick(0), 0.02)


    def _spin_tick(self, dt):
        scatters = getattr(self, "_spin_scatters", None)
        slots = getattr(self, "_spin_slots", None)
        overlay = getattr(self, "_spin_overlay", None)
        if not scatters or not slots or overlay is None:
            return False

        n = len(scatters)
        top = scatters[0]
        new_order = scatters[1:] + [top]
        self._spin_scatters = new_order
        self._spin_cards = self._spin_cards[1:] + [self._spin_cards[0]]

        # بردن کارت رفتنی به جلوی z-stack
        overlay.remove_widget(top)
        overlay.add_widget(top, index=0)

        anim_dur = max(0.18, self._spin_interval - 0.04)

        # بقیه نرم می‌رن یک اسلات بالاتر
        for i in range(1, n):
            sc = scatters[i]
            tx, ty, tw, th = slots[i - 1]
            Animation.cancel_all(sc, 'x', 'y', 'scale')
            Animation(x=tx, y=ty, duration=anim_dur, t='in_out_sine').start(sc)

        # کارت بالا با قوس نرم به پایین می‌افته (بدون pop تند)
        bx, by, bw, bh = slots[-1]
        Animation.cancel_all(top, 'x', 'y', 'scale')
        Animation(x=bx, y=by, duration=anim_dur, t='in_out_sine').start(top)

        self._spin_ticks += 1
        if self._spin_ticks >= self._spin_max:
            try:
                self._spin_event.cancel()
            except Exception:
                pass
            self._spin_event = None
            Clock.schedule_once(lambda *a: self._finish_spin(), anim_dur + 0.02)
            return False
        return True

    def _finish_spin(self):
        overlay = getattr(self, "_spin_overlay", None)
        scatters = getattr(self, "_spin_scatters", None)
        cards = getattr(self, "_spin_cards", None)
        slots = getattr(self, "_spin_slots", None)
        box = getattr(self, "_spin_box", None) or self.ids.ideas_box
        if not overlay or not scatters or not cards:
            self._spinning = False
            return

        n = len(scatters)
        winner_idx = random.randrange(n)
        winner = scatters[winner_idx]
        winner_card = cards[winner_idx]
        # winner اول قرار می‌گیره تا به اسلات بالا (slots[0]) بره، بقیه پایین‌ترش
        rest_scatters = [s for s in scatters if s is not winner]
        rest_cards = [c for c in cards if c is not winner_card]
        scatters = [winner] + rest_scatters
        cards = [winner_card] + rest_cards
        self._spin_scatters = scatters
        self._spin_cards = cards

        overlay.remove_widget(winner)
        overlay.add_widget(winner, index=0)

        for i, sc in enumerate(scatters):
            tx, ty, tw, th = slots[i]
            Animation.cancel_all(sc, 'x', 'y', 'scale')
            if sc is winner:
                a = (Animation(x=tx, y=ty, duration=0.35, t='out_back') &
                     Animation(scale=1.10, duration=0.20, t='out_quad'))
                a += Animation(scale=1.0, duration=0.16, t='out_quad')
                a.start(sc)
                Animation(opacity=1.0, duration=0.25).start(sc.children[0])
            else:
                Animation(x=tx, y=ty, duration=0.30, t='out_cubic').start(sc)
                Animation(opacity=0.28, duration=0.30).start(sc.children[0])

        Clock.schedule_once(lambda *a: self._commit_spin_order(), 0.55)

    def _commit_spin_order(self):
        overlay = getattr(self, "_spin_overlay", None)
        scatters = getattr(self, "_spin_scatters", None)
        cards = getattr(self, "_spin_cards", None)
        box = getattr(self, "_spin_box", None) or self.ids.ideas_box
        if overlay is None or not scatters or not cards:
            self._spinning = False
            return

        for sc, card in zip(scatters, cards):
            try:
                sc.remove_widget(card)
            except Exception:
                pass
            card.size_hint = (1, None)
            card.height = dp(170)

        # winner اول اضافه می‌شه → در BoxLayout عمودی به‌صورت پیش‌فرض بالا قرار می‌گیره
        for card in cards:
            box.add_widget(card)

        winner = cards[0]
        for c in cards:
            c.opacity = 1.0 if c is winner else 0.35

        try:
            Window.remove_widget(overlay)
        except Exception:
            pass
        self._spin_overlay = None
        self._spin_scatters = None
        self._spin_cards = None
        self._spin_slots = None
        self._spin_box = None
        self._spinning = False

        # قفل: فقط برنده قابل کلیک، بقیه کدر می‌مونن تا کاربر دوباره رندوم یا بک بزنه
        self._winner_card = winner
        self.locked = True




# ---------------------------------------------------------------------------
# IdeaDetailScreen — صفحه‌ی جزئیات هر ایده با محل ثبت خاطره
# ---------------------------------------------------------------------------
class IdeaDetailScreen(Screen):
    category_id = StringProperty("")
    idea_title = StringProperty("")

    def load_idea(self, category_id, idea):
        self.category_id = category_id or ""
        self.idea_title = (idea or {}).get("title", "")
        self.ids.detail_title.text = fa(self.idea_title)
        self.ids.detail_desc.raw_text = (idea or {}).get("desc", "") or ""

        # تگ‌ها
        tags_box = self.ids.detail_tags_box
        tags_box.clear_widgets()
        for txt, bg, fg in (idea or {}).get("tags", []):
            tag = FloatLayout(size_hint_x=None, width=dp(70))
            with tag.canvas.before:
                Color(*bg)
                rr = RoundedRectangle(pos=tag.pos, size=tag.size, radius=[dp(12)])
            def _upd(inst, _v, _rr=rr):
                _rr.pos = inst.pos; _rr.size = inst.size
            tag.bind(pos=_upd, size=_upd)
            lbl = Label(text=fa(txt), font_name=APP_FONT, font_size="11sp",
                        color=fg, halign="center", valign="middle",
                        size_hint=(None, None),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})
            def _sync(inst, ts, _tag=tag):
                inst.size = ts
                _tag.width = ts[0] + dp(20)
            lbl.bind(texture_size=_sync)
            _sync(lbl, lbl.texture_size)
            tag.add_widget(lbl)
            tags_box.add_widget(tag)
        tags_box.add_widget(BoxLayout())

        self._build_memory_area()
        self._build_done_button()

    def _build_memory_area(self):
        holder = self.ids.memory_holder
        holder.clear_widgets()
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        img_path = get_memory_image(uname, self.category_id, self.idea_title) if uname else ""

        wrap = ButtonBehavior_BoxLayout()
        wrap.size_hint = (1, 1)
        wrap.pos_hint = {"x": 0, "y": 0}

        # کادر شیشه‌ای خاکستری
        with wrap.canvas.before:
            Color(*neutral("glass_grey"))
            wrap._bg = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[dp(22)])
            Color(*neutral("glass_border"))
            wrap._brd = Line(rounded_rectangle=(wrap.x, wrap.y, wrap.width, wrap.height, dp(22)), width=1.4)

        def _upd(*a):
            wrap._bg.pos = wrap.pos
            wrap._bg.size = wrap.size
            wrap._brd.rounded_rectangle = (wrap.x, wrap.y, wrap.width, wrap.height, dp(22))
        wrap.bind(pos=_upd, size=_upd)

        inner = FloatLayout()
        wrap.add_widget(inner)

        if img_path and os.path.exists(img_path):
            img = Image(source=img_path, allow_stretch=True, keep_ratio=True,
                        size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
            inner.add_widget(img)
            tip = Label(text=fa("برای تغییر عکس بزنید"), font_name=APP_FONT,
                        font_size="11sp", color=(1, 1, 1, 0.85),
                        size_hint=(None, None), size=(dp(180), dp(22)),
                        pos_hint={"center_x": 0.5, "y": 0.02})
            inner.add_widget(tip)
        else:
            lbl = Label(text=fa("خاطره خود را اینجا بگذارید"),
                        font_name=APP_FONT, font_size="15sp", bold=True,
                        color=neutral("text_primary"),
                        halign="center", valign="middle",
                        size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
            lbl.bind(size=lbl.setter("text_size"))
            inner.add_widget(lbl)

        wrap.bind(on_release=lambda *a: self._pick_memory())
        holder.add_widget(wrap)

    def _toast(self, text):
        p = Popup(title="", separator_height=0,
                  content=Label(text=text, font_name=APP_FONT, halign="center",
                                color=(1, 1, 1, 1)),
                  size_hint=(0.8, 0.22))
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 2.0)

    def _pick_memory(self):
        if _PLYER_AVAILABLE:
            try:
                plyer_filechooser.open_file(on_selection=self._after_pick,
                                            filters=[["Images", "*.png", "*.jpg", "*.jpeg"]])
                return
            except Exception as e:
                self._toast(fa(f"گالری در دسترس نیست: {e}"))
        else:
            self._toast(fa("گالری فقط روی گوشی کار می‌کند"))

    def _after_pick(self, selection):
        if selection:
            Clock.schedule_once(lambda dt: self._apply_memory(selection[0]), 0)

    def _apply_memory(self, path):
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        if not uname:
            self._toast(fa("ابتدا وارد شوید"))
            return
        saved, msg = save_memory_image(uname, self.category_id, self.idea_title, path)
        if not saved:
            self._toast(fa(msg))
            return
        # refresh
        app.current_user = dict(get_account(uname))
        self._build_memory_area()
        self._toast(fa("خاطره ذخیره شد ✓"))




    def _build_done_button(self):
        try:
            holder = self.ids.done_btn_holder
        except Exception:
            return
        holder.clear_widgets()
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        done = is_idea_done(uname, self.category_id, self.idea_title) if uname else False

        wrap = BoxLayout(orientation="horizontal", size_hint=(1, 1),
                         padding=(dp(0), dp(0)))
        with wrap.canvas.before:
            # سبز دائمی وقتی انجام شده، سفید-شفاف وقتی هنوز نه
            if done:
                _c = Color(0.231, 0.722, 0.216, 1)  # #3BB837
            else:
                _c = Color(*neutral("surface"))
            _rr = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[dp(18)])
            _bc = Color(0.231, 0.722, 0.216, 1)
            _line = Line(rounded_rectangle=(wrap.x, wrap.y, wrap.width, wrap.height, dp(18)), width=1.6)
        def _upd(*a, _rr=_rr, _line=_line):
            _rr.pos = wrap.pos; _rr.size = wrap.size
            _line.rounded_rectangle = (wrap.x, wrap.y, wrap.width, wrap.height, dp(18))
        wrap.bind(pos=_upd, size=_upd)

        label_text = fa("انجام شد ✓") if done else fa("انجام دادم")
        text_color = (1, 1, 1, 1) if done else (0.231, 0.722, 0.216, 1)
        btn = Button(
            text=label_text, font_name=APP_FONT, font_size="17sp", bold=True,
            background_normal="", background_color=(0, 0, 0, 0),
            color=text_color,
        )
        if not done:
            btn.bind(on_release=lambda *a: self._mark_done())
        wrap.add_widget(btn)
        holder.add_widget(wrap)

    def _refresh_theme(self, *a):
        try:
            self._build_memory_area()
        except Exception:
            pass
        try:
            self._build_done_button()
        except Exception:
            pass

    def _mark_done(self):
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        if not uname:
            self._toast(fa("ابتدا وارد شوید"))
            return
        mark_idea_done(uname, self.category_id, self.idea_title)
        self._build_done_button()
        try:
            CelebrationPopup(text=fa("آفرین! این ایده انجام شد ✓")).open()
        except Exception as _e:
            print("[Celebration]", _e)
            self._toast(fa("آفرین! این ایده انجام شد ✓"))
        # refresh ideas list badge on return
        try:
            ideas_scr = app.root.get_screen("ideas")
            cat = next((c for c in CATEGORIES if c["id"] == ideas_scr.current_category_id), None)
            if cat:
                ideas_scr.load_category(cat)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Themed Toast — نوتیف گرد با تم و سایه
# ---------------------------------------------------------------------------
class _ShadowToast(ModalView):
    def __init__(self, text="", **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.auto_dismiss = True
        self.overlay_color = (0, 0, 0, 0)
        self._text = text
        self._build()

    def _build(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_WHITE
        accent = theme["accent"]

        root = FloatLayout(size_hint=(None, None))
        # کانتینر اصلی
        card = BoxLayout(orientation="horizontal", padding=[dp(18), dp(12)],
                         size_hint=(None, None))
        lbl = Label(text=self._text, font_name=APP_FONT, font_size="14sp",
                    bold=True, color=(1, 1, 1, 1),
                    halign="center", valign="middle",
                    size_hint=(None, None))
        lbl.bind(texture_size=lambda i, v: setattr(i, "size", v))
        card.add_widget(lbl)

        def _resize(*_a):
            w = min(max(lbl.texture_size[0] + dp(36), dp(120)), Window.width * 0.86)
            h = max(lbl.texture_size[1] + dp(24), dp(46))
            card.size = (w, h)
            root.size = (w + dp(16), h + dp(16))
            self.size = root.size
        lbl.bind(texture_size=_resize)

        with card.canvas.before:
            # سایه
            Color(0, 0, 0, 0.18)
            self._sh = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)])
            # پس‌زمینه با تم
            Color(accent[0], accent[1], accent[2], 0.96)
            self._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)])
        def _upd(*_a):
            self._sh.pos = (card.x + dp(2), card.y - dp(3))
            self._sh.size = card.size
            self._bg.pos = card.pos
            self._bg.size = card.size
        card.bind(pos=_upd, size=_upd)

        wrap = FloatLayout()
        card.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        wrap.add_widget(card)
        self.add_widget(wrap)
        self.pos_hint = {"center_x": 0.5, "y": 0.08}


def show_themed_toast(text, duration=2.0):
    """نوتیف گرد با رنگ تم و سایه؛ از پایین صفحه نمایش داده می‌شود."""
    t = _ShadowToast(text=text)
    t.open()
    Clock.schedule_once(lambda dt: t.dismiss(), duration)



# ---------------------------------------------------------------------------
# Personal ideas + done-state persistence (per user)
# ---------------------------------------------------------------------------
import json as _json_pi

PERSONAL_IDEAS_FILENAME = "personal_ideas.json"
DONE_IDEAS_FILENAME = "done_ideas.json"


def _user_data_dir(username: str) -> str:
    """پوشه‌ی داده‌های شخصی کاربر = دقیقاً همان storage_folder اختصاصی او.

    ساختار قدیمی <base>/users/<username> حذف شده است؛ چون هر پوشه فقط به یک
    اکانت تعلق دارد، فایل‌ها مستقیماً در ریشه‌ی پوشه ذخیره می‌شوند:
        <storage_folder>/personal_ideas.json
        <storage_folder>/done_ideas.json
        <storage_folder>/diary_notes.json
    اگر ساختار قدیمی وجود داشته باشد، یک‌بار به‌صورت خودکار مهاجرت می‌کند.
    """
    d = account_folder(username)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    # مهاجرت از ساختار قدیمی users/<safe>
    try:
        safe = "".join(ch for ch in (username or "_guest") if ch.isalnum() or ch in "_-") or "_guest"
        legacy = os.path.join(d, "users", safe)
        if os.path.isdir(legacy):
            for fn in os.listdir(legacy):
                src = os.path.join(legacy, fn)
                dst = os.path.join(d, fn)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.move(src, dst)
    except Exception:
        pass
    return d


def load_personal_ideas(username: str, category_id: str) -> list:
    if not username:
        return []
    path = os.path.join(_user_data_dir(username), PERSONAL_IDEAS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json_pi.load(f) or {}
    except Exception:
        data = {}
    return list(data.get(category_id, []))


def add_personal_idea(username: str, category_id: str, idea: dict) -> bool:
    if not username or not category_id:
        return False
    path = os.path.join(_user_data_dir(username), PERSONAL_IDEAS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json_pi.load(f) or {}
    except Exception:
        data = {}
    data.setdefault(category_id, []).append(idea)
    try:
        with open(path, "w", encoding="utf-8") as f:
            _json_pi.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("[personal_ideas] save failed:", e)
        return False


def load_done_ideas(username: str) -> set:
    if not username:
        return set()
    path = os.path.join(_user_data_dir(username), DONE_IDEAS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(_json_pi.load(f) or [])
    except Exception:
        return set()


def _done_key(category_id: str, title: str) -> str:
    return f"{category_id}||{title}"


def is_idea_done(username: str, category_id: str, title: str) -> bool:
    return _done_key(category_id, title) in load_done_ideas(username)


def mark_idea_done(username: str, category_id: str, title: str) -> None:
    if not username:
        return
    s = load_done_ideas(username)
    s.add(_done_key(category_id, title))
    path = os.path.join(_user_data_dir(username), DONE_IDEAS_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as f:
            _json_pi.dump(sorted(s), f, ensure_ascii=False)
    except Exception as e:
        print("[done_ideas] save failed:", e)


# ---------------------------------------------------------------------------
# AddPersonalIdeaScreen — صفحه‌ی افزودن ایده‌ی شخصی
# ---------------------------------------------------------------------------
class AddPersonalIdeaScreen(Screen):
    category_id = StringProperty("")
    header_text = StringProperty("")
    t_title_label = StringProperty("")
    t_desc_label = StringProperty("")
    t_cost_label = StringProperty("")
    t_age_label = StringProperty("")
    t_date_label = StringProperty("")
    t_save_btn = StringProperty("")
    t_title_hint = StringProperty("")
    t_desc_hint = StringProperty("")
    t_style_label = StringProperty("")
    t_style_hint = StringProperty("")

    def on_pre_enter(self, *a):
        self.header_text = fa("اضافه کردن ایده‌ی شخصی")
        self.t_title_label = fa("اسم ایده")
        self.t_desc_label = fa("توضیحات")
        self.t_cost_label = fa("هزینه")
        self.t_age_label = fa("بازه سنی")
        self.t_style_label = fa("سبک دیت")
        self.t_date_label = fa("تاریخ ثبت:")
        self.t_save_btn = fa("ذخیره")
        self.t_title_hint = fa("مثلاً: پیاده‌روی در پارک")
        self.t_desc_hint = fa("جزئیات ایده‌ات را بنویس…")
        self.t_style_hint = fa("مثلاً: رمانتیک، هیجانی، …")
        # reset inputs
        try:
            self.ids.title_input.set_raw_text("")
            self.ids.desc_input.set_raw_text("")
            if "style_input" in self.ids:
                self.ids.style_input.set_raw_text("")
            import datetime as _dt
            today = _dt.date.today().isoformat()
            if "date_label" in self.ids:
                self.ids.date_label.text = fa(today)
            self._selected_cost = fa("متوسط")
            self._selected_age = fa("۲۰ تا ۲۵ سال")
            self.ids.cost_btn.text = self._selected_cost
            self.ids.age_btn.text = self._selected_age
        except Exception as e:
            print("[AddIdea.pre_enter]", e)

    def open_cost_menu(self):
        self._open_menu(["ارزان", "متوسط", "گران"], self._set_cost)

    def open_age_menu(self):
        # بازه‌های سنی هماهنگ با تگ‌های سیستم (TAG_AGE_15_20 … TAG_AGE_30_35)
        self._open_menu(["۱۵ تا ۲۰ سال", "۲۰ تا ۲۵ سال", "۲۵ تا ۳۰ سال", "۳۰ تا ۳۵ سال"], self._set_age)

    def _set_cost(self, val):
        self._selected_cost = fa(val)
        self.ids.cost_btn.text = self._selected_cost

    def _set_age(self, val):
        self._selected_age = fa(val)
        self.ids.age_btn.text = self._selected_age

    def _open_menu(self, options, cb):
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        popup = Popup(title="", separator_height=0, size_hint=(0.75, None),
                      height=dp(60) * len(options) + dp(20),
                      background_color=(1, 1, 1, 1))
        for opt in options:
            btn = Button(text=fa(opt), font_name=APP_FONT, font_size="15sp",
                         size_hint_y=None, height=dp(48),
                         background_normal="", background_color=(0.95, 0.95, 0.97, 1),
                         color=(0.25, 0.20, 0.22, 1))
            btn.bind(on_release=lambda b, v=opt: (cb(v), popup.dismiss()))
            content.add_widget(btn)
        popup.content = content
        popup.open()

    def save_idea(self):
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        if not uname:
            show_themed_toast(fa("ابتدا وارد شوید"))
            return
        title = (self.ids.title_input.get_raw_text() or "").strip()
        desc = (self.ids.desc_input.get_raw_text() or "").strip()
        if not title:
            show_themed_toast(fa("عنوان ایده را وارد کنید"))
            return
        cost = getattr(self, "_selected_cost", "") or self.ids.cost_btn.text
        age_range = getattr(self, "_selected_age", "") or self.ids.age_btn.text
        style_txt = ""
        try:
            if "style_input" in self.ids:
                style_txt = (self.ids.style_input.get_raw_text() or "").strip()
        except Exception:
            style_txt = ""
        import datetime as _dt
        tags = [
            [cost, [0.95, 0.9, 0.75, 1], [0.4, 0.3, 0.1, 1]],
            [age_range, [0.85, 0.9, 0.98, 1], [0.2, 0.3, 0.55, 1]],
            ["شخصی", [0.85, 0.98, 0.88, 1], [0.15, 0.5, 0.25, 1]],
        ]
        if style_txt:
            tags.append([style_txt, [0.96, 0.86, 0.95, 1], [0.55, 0.10, 0.45, 1]])
        idea = {
            "title": title,
            "desc": desc,
            "border": [0.35, 0.55, 0.85, 1],
            "tags": tags,
            "style": style_txt,
            "date": _dt.date.today().isoformat(),
            "personal": True,
        }
        ok = add_personal_idea(uname, self.category_id, idea)
        if ok:
            show_themed_toast(fa("ایده‌ی شخصی ذخیره شد ✓"))
            Clock.schedule_once(lambda dt: self.go_back(), 0.35)
        else:
            show_themed_toast(fa("ذخیره‌سازی با خطا مواجه شد"))

    def go_back(self):
        app = App.get_running_app()
        app.root.transition = SlideTransition(direction="right")
        app.root.current = "ideas"
        try:
            scr = app.root.get_screen("ideas")
            # rebuild list to include new idea
            cat = next((c for c in CATEGORIES if c["id"] == scr.current_category_id), None)
            if cat:
                scr.load_category(cat)
        except Exception as e:
            print("[AddIdea.go_back]", e)


# ---------------------------------------------------------------------------
# دفترچه خاطرات — ذخیره‌ی نوت‌ها در پوشه‌ی اختصاصی کاربر
# ---------------------------------------------------------------------------
DIARY_FILENAME = "diary_notes.json"
DIARY_MIN_AGE = 15
DIARY_MAX_AGE = 20


def _diary_path(username: str) -> str:
    return os.path.join(_user_data_dir(username), DIARY_FILENAME)


def load_diary_notes(username: str) -> list:
    if not username:
        return []
    try:
        with open(_diary_path(username), "r", encoding="utf-8") as f:
            data = _json_pi.load(f) or []
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_diary_notes(username: str, notes: list) -> bool:
    if not username:
        return False
    try:
        with open(_diary_path(username), "w", encoding="utf-8") as f:
            _json_pi.dump(notes, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("[diary] save failed:", e)
        return False


def user_can_use_diary(user: dict) -> bool:
    try:
        age = int((user or {}).get("age", 0) or 0)
    except Exception:
        age = 0
    return DIARY_MIN_AGE <= age <= DIARY_MAX_AGE


# ---------------------------------------------------------------------------
# ویجت ویرایشگر دفترچه (RTL + خطوط افقی زیر متن + فونت BHoma)
# ---------------------------------------------------------------------------
class DiaryEditor(RTLTextInput):
    """ویرایشگر چندخطی برای نوت‌های دفترچه.

    مدل ویرایش مطابق بقیه‌ی برنامه (RTLTextInput): درج/حذف در انتهای متنِ منطقی.
    تغییر متن هر بار متن نمایشی را reshape/bidi می‌کند و رویدادی برای ذخیره‌ی
    خودکار می‌فرستد.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("multiline", True)
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)  # پس‌زمینه شفاف؛ خطوط را کنواس والد می‌کشد
        self.foreground_color = (0.20, 0.18, 0.22, 1)
        self.cursor_color = (0.55, 0.40, 0.20, 1)
        self.padding = [dp(14), dp(10), dp(14), dp(10)]
        try:
            self.font_name = DIARY_FONT
        except Exception:
            pass
        self.font_size = dp(16)


# ---------------------------------------------------------------------------
# پس‌زمینه‌ی خط‌دار (کاغذ دفترچه) — یک BoxLayout با کنواس سفارشی
# ---------------------------------------------------------------------------
class DiaryPaper(BoxLayout):
    line_color = ListProperty(list(NEUTRAL_LIGHT["paper_line"]))
    paper_color = ListProperty(list(NEUTRAL_LIGHT["paper"]))
    line_gap = NumericProperty(dp(28))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_col = Color(*self.paper_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._redraw, size=self._redraw,
                  line_color=self._redraw, paper_color=self._redraw, line_gap=self._redraw)
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    def _redraw(self, *a):
        try:
            self._bg_col.rgba = self.paper_color
            self._bg_rect.pos = self.pos
            self._bg_rect.size = self.size
        except Exception:
            pass
        # حذف خطوط قبلی (ایمن)
        try:
            for inst in list(self.canvas.after.children):
                if inst in self.canvas.after.children:
                    self.canvas.after.remove(inst)
        except Exception:
            try:
                self.canvas.after.clear()
            except Exception:
                pass
        gap = max(dp(20), float(self.line_gap or dp(28)))
        with self.canvas.after:
            Color(*self.line_color)
            x1 = self.x + dp(10)
            x2 = self.right - dp(10)
            y = self.y + dp(8)
            while y < self.top - dp(4):
                Line(points=[x1, y, x2, y], width=1.0)
                y += gap


# ---------------------------------------------------------------------------
# صفحه‌ی لیست نوت‌های دفترچه
# ---------------------------------------------------------------------------
class DiaryScreen(Screen):
    header_text = StringProperty("")
    empty_text = StringProperty("")
    add_text = StringProperty("")

    def on_pre_enter(self, *a):
        self.header_text = fa("دفترچه خاطرات")
        self.empty_text = fa("هنوز نوتی نداری. با + اولین خاطره‌ات رو بنویس.")
        self.add_text = fa("+ نوت جدید")
        self.refresh_list()

    def _uname(self):
        return (App.get_running_app().current_user or {}).get("username", "")

    def refresh_list(self):
        box = self.ids.notes_box
        box.clear_widgets()
        uname = self._uname()
        notes = load_diary_notes(uname)
        if not notes:
            box.add_widget(Label(text=self.empty_text or fa("هنوز نوتی نداری."),
                                 font_name=APP_FONT, font_size=dp(14),
                                 color=neutral("paper_sub"),
                                 size_hint_y=None, height=dp(60),
                                 halign="center"))
            return
        # جدیدترین بالا
        for idx, note in enumerate(reversed(notes)):
            real_index = len(notes) - 1 - idx
            row = _DiaryNoteRow(
                note_index=real_index,
                title_text=fa(note.get("title") or note.get("body", " ")[:40] or "بدون عنوان"),
                date_text=fa(note.get("updated_at", note.get("created_at", ""))),
                parent_screen=self,
            )
            box.add_widget(row)

    def _refresh_theme(self, *a):
        try:
            self.refresh_list()
        except Exception:
            pass

    def open_note(self, index):
        app = App.get_running_app()
        try:
            scr = app.root.get_screen("diary_note")
            scr.load_note(index)
        except Exception as e:
            print("[diary open_note]", e)
            return
        app.root.transition = SlideTransition(direction="left")
        app.root.current = "diary_note"

    def add_note(self):
        app = App.get_running_app()
        try:
            scr = app.root.get_screen("diary_note")
            scr.load_note(-1)  # نوت جدید
        except Exception as e:
            print("[diary add]", e)
            return
        app.root.transition = SlideTransition(direction="left")
        app.root.current = "diary_note"

    def delete_note(self, index):
        uname = self._uname()
        notes = load_diary_notes(uname)
        if 0 <= index < len(notes):
            del notes[index]
            save_diary_notes(uname, notes)
            self.refresh_list()

    def go_back(self):
        app = App.get_running_app()
        app.root.transition = SlideTransition(direction="right")
        app.root.current = "categories"


class _DiaryNoteRow(ButtonBehavior, BoxLayout):
    note_index = NumericProperty(-1)
    title_text = StringProperty("")
    date_text = StringProperty("")
    parent_screen = ObjectProperty(None, allownone=True)

    def on_release(self):
        if self.parent_screen:
            self.parent_screen.open_note(self.note_index)

    def ask_delete(self):
        if not self.parent_screen:
            return
        try:
            dlg = ConfirmDialog(
                message=fa("این نوت حذف بشه؟"),
                on_yes=lambda: self.parent_screen.delete_note(self.note_index),
            )
            dlg.open()
        except Exception as e:
            print("[diary row delete]", e)
            self.parent_screen.delete_note(self.note_index)


# ---------------------------------------------------------------------------
# صفحه‌ی ویرایش/ایجاد نوت — ذخیره‌ی خودکار
# ---------------------------------------------------------------------------
class DiaryNoteScreen(Screen):
    note_index = NumericProperty(-1)
    header_text = StringProperty("")
    title_hint = StringProperty("")
    body_hint = StringProperty("")
    saved_hint = StringProperty("")
    _autosave_ev = None
    _dirty = BooleanProperty(False)

    def on_pre_enter(self, *a):
        self.header_text = fa("نوشتن خاطره")
        self.title_hint = fa("عنوان (اختیاری)…")
        self.body_hint = fa("این‌جا خاطره‌ات رو بنویس…")
        self.saved_hint = fa("ذخیره خودکار فعال است")

    def _uname(self):
        return (App.get_running_app().current_user or {}).get("username", "")

    def load_note(self, index: int):
        self.note_index = int(index)
        notes = load_diary_notes(self._uname())
        title = ""
        body = ""
        if 0 <= self.note_index < len(notes):
            note = notes[self.note_index]
            title = note.get("title", "")
            body = note.get("body", "")
        # وقتی on_pre_enter هنوز اجرا نشده باشه، ids ممکنه آماده نباشه.
        def _apply(_dt=None):
            try:
                self.ids.title_in.set_raw_text(title)
                self.ids.body_in.set_raw_text(body)
                self._dirty = False
            except Exception as e:
                print("[diary load_note]", e)
        _apply()
        Clock.schedule_once(_apply, 0)

    def _now_str(self):
        try:
            import datetime as _dt
            return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ""

    def on_text_changed(self, *a):
        self._dirty = True
        # debounce ذخیره‌ی خودکار
        if self._autosave_ev is not None:
            try:
                self._autosave_ev.cancel()
            except Exception:
                pass
        self._autosave_ev = Clock.schedule_once(lambda dt: self._autosave(), 0.7)

    def _autosave(self):
        if not self._dirty:
            return
        uname = self._uname()
        if not uname:
            return
        try:
            title = self.ids.title_in.get_raw_text().strip()
            body = self.ids.body_in.get_raw_text()
        except Exception:
            return
        notes = load_diary_notes(uname)
        now = self._now_str()
        if 0 <= self.note_index < len(notes):
            notes[self.note_index]["title"] = title
            notes[self.note_index]["body"] = body
            notes[self.note_index]["updated_at"] = now
        else:
            if not title and not body.strip():
                return  # نوت خالی ذخیره نشه
            notes.append({
                "title": title,
                "body": body,
                "created_at": now,
                "updated_at": now,
            })
            self.note_index = len(notes) - 1
        save_diary_notes(uname, notes)
        self._dirty = False
        try:
            self.ids.saved_lbl.text = fa("ذخیره شد ✓  " + now)
        except Exception:
            pass

    def go_back(self):
        # ذخیره‌ی نهایی قبل از خروج
        try:
            if self._autosave_ev:
                self._autosave_ev.cancel()
        except Exception:
            pass
        self._autosave()
        app = App.get_running_app()
        app.root.transition = SlideTransition(direction="right")
        app.root.current = "diary"
        try:
            app.root.get_screen("diary").refresh_list()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# KV اضافه برای صفحات دفترچه
# ---------------------------------------------------------------------------
DIARY_KV = """
<_DiaryNoteRow>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(64)
    padding: dp(10), dp(6)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: app.theme_paper
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12),]
        Color:
            rgba: app.theme_paper_line
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(12))
            width: 1
    Button:
        size_hint_x: None
        width: dp(38)
        text: '🗑'
        font_name: app.font_name
        font_size: sp(16)
        background_normal: ''
        background_color: 0, 0, 0, 0
        color: 0.75, 0.30, 0.25, 1
        on_release: root.ask_delete()
    BoxLayout:
        orientation: 'vertical'
        Label:
            text: root.title_text
            font_name: app.diary_font
            font_size: sp(16)
            color: app.theme_paper_text
            halign: 'right'
            valign: 'middle'
            text_size: self.size
            shorten: True
        Label:
            text: root.date_text
            font_name: app.font_name
            font_size: sp(11)
            color: app.theme_paper_sub
            halign: 'right'
            valign: 'middle'
            text_size: self.size
            size_hint_y: None
            height: dp(16)

<DiaryScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(14)
        spacing: dp(10)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            Button:
                size_hint_x: None
                width: dp(48)
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.go_back()
                Image:
                    source: app.back_image
                    size_hint: None, None
                    size: dp(28), dp(28)
                    center: self.parent.center
                    allow_stretch: True
            Label:
                text: root.header_text
                font_name: app.diary_font
                font_size: sp(20)
                bold: True
                color: app.theme_title
                halign: 'right'
                valign: 'middle'
                text_size: self.size
            Button:
                size_hint_x: None
                width: dp(126)
                size_hint_y: None
                height: dp(42)
                pos_hint: {'center_y': 0.5}
                text: root.add_text
                font_name: app.font_name
                font_size: sp(14)
                bold: True
                color: 1, 1, 1, 1
                background_normal: ''
                background_down: ''
                background_color: 0, 0, 0, 0
                on_release: root.add_note()
                canvas.before:
                    Color:
                        rgba: 0.20, 0.55, 0.30, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [self.height / 2.0]
                    Color:
                        rgba: 1, 1, 1, 0.35
                    Line:
                        rounded_rectangle: (self.x + 1, self.y + 1, self.width - 2, self.height - 2, (self.height - 2) / 2.0)
                        width: 1.2
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: notes_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                padding: dp(2), dp(4)

<DiaryNoteScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            Button:
                size_hint_x: None
                width: dp(46)
                background_normal: ''
                background_color: 0, 0, 0, 0
                on_release: root.go_back()
                Image:
                    source: app.back_image
                    size_hint: None, None
                    size: dp(26), dp(26)
                    center: self.parent.center
            Label:
                text: root.header_text
                font_name: app.diary_font
                font_size: sp(18)
                bold: True
                color: app.theme_title
                halign: 'right'
                valign: 'middle'
                text_size: self.size
            Label:
                id: saved_lbl
                text: root.saved_hint
                font_name: app.font_name
                font_size: sp(11)
                color: 0.35, 0.50, 0.30, 1
                size_hint_x: None
                width: dp(150)
                halign: 'left'
                valign: 'middle'
                text_size: self.size
        RTLTextInput:
            id: title_in
            hint_text: root.title_hint
            font_name: app.diary_font
            font_size: sp(16)
            multiline: False
            size_hint_y: None
            height: dp(44)
            background_normal: ''
            background_active: ''
            background_color: app.theme_surface_soft
            foreground_color: app.theme_paper_text
            padding: dp(10), dp(10), dp(10), dp(10)
            on_text: root.on_text_changed()
        DiaryPaper:
            id: paper
            orientation: 'vertical'
            paper_color: app.theme_paper
            line_color: app.theme_paper_line
            DiaryEditor:
                id: body_in
                hint_text: root.body_hint
                on_text: root.on_text_changed()
"""


# ---------------------------------------------------------------------------
# KV صفحه‌ی افزودن ایده‌ی شخصی
# ---------------------------------------------------------------------------
ADD_IDEA_KV = """
<AddPersonalIdeaScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: "vertical"
        padding: dp(18), dp(20)
        spacing: dp(12)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            BoxLayout:
                size_hint_x: None
                width: dp(54)
                padding: dp(7)
                canvas.before:
                    Color:
                        rgba: 0.55, 0.58, 0.62, 0.35
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(14)]
                IconImageButton:
                    source: app.back_image
                    on_release: root.go_back()
            Label:
                text: root.header_text
                font_name: app.font_name
                font_size: sp(20)
                bold: True
                color: app.theme_title
                halign: "right"
                valign: "middle"
                text_size: self.size
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                padding: dp(4), dp(4)

                # -------- عنوان ایده --------
                Label:
                    text: root.t_title_label
                    font_name: app.font_name
                    font_size: sp(13)
                    color: 0.5, 0.42, 0.45, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size
                InputBox:
                    size_hint_y: None
                    height: dp(48)
                    canvas.before:
                        Color:
                            rgba: app.theme_input_bg
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16)]
                    RTLTextInput:
                        id: title_input
                        hint_text: root.t_title_hint
                        font_name: app.font_name
                        font_size: sp(15)
                        multiline: False
                        background_color: 0, 0, 0, 0
                        foreground_color: app.theme_text_primary
                        hint_text_color: app.theme_text_hint
                        cursor_color: 0.8, 0.5, 0.6, 1
                        padding: dp(14), dp(12)

                # -------- توضیحات --------
                Label:
                    text: root.t_desc_label
                    font_name: app.font_name
                    font_size: sp(13)
                    color: 0.5, 0.42, 0.45, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size
                InputBox:
                    size_hint_y: None
                    height: dp(120)
                    canvas.before:
                        Color:
                            rgba: app.theme_input_bg
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16)]
                    RTLTextInput:
                        id: desc_input
                        hint_text: root.t_desc_hint
                        font_name: app.font_name
                        font_size: sp(14)
                        multiline: True
                        background_color: 0, 0, 0, 0
                        foreground_color: app.theme_text_primary
                        hint_text_color: app.theme_text_hint
                        cursor_color: 0.8, 0.5, 0.6, 1
                        padding: dp(14), dp(12)

                # -------- هزینه --------
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(10)
                    Button:
                        id: cost_btn
                        text: ""
                        font_name: app.font_name
                        font_size: sp(14)
                        color: app.theme_text_primary
                        background_normal: ""
                        background_color: 0, 0, 0, 0
                        on_release: root.open_cost_menu()
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(14)]
                    Label:
                        text: root.t_cost_label
                        size_hint_x: None
                        width: dp(90)
                        font_name: app.font_name
                        font_size: sp(14)
                        color: app.theme_text_primary
                        halign: "right"
                        valign: "middle"
                        text_size: self.size

                # -------- بازه سنی --------
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(10)
                    Button:
                        id: age_btn
                        text: ""
                        font_name: app.font_name
                        font_size: sp(14)
                        color: app.theme_text_primary
                        background_normal: ""
                        background_color: 0, 0, 0, 0
                        on_release: root.open_age_menu()
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(14)]
                    Label:
                        text: root.t_age_label
                        size_hint_x: None
                        width: dp(90)
                        font_name: app.font_name
                        font_size: sp(14)
                        color: app.theme_text_primary
                        halign: "right"
                        valign: "middle"
                        text_size: self.size

                # -------- سبک دیت --------
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(10)
                    InputBox:
                        canvas.before:
                            Color:
                                rgba: app.theme_input_bg
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(14)]
                        RTLTextInput:
                            id: style_input
                            hint_text: root.t_style_hint
                            font_name: app.font_name
                            font_size: sp(14)
                            multiline: False
                            background_color: 0, 0, 0, 0
                            foreground_color: app.theme_text_primary
                            hint_text_color: app.theme_text_hint
                            cursor_color: 0.8, 0.5, 0.6, 1
                            padding: dp(14), dp(12)
                    Label:
                        text: root.t_style_label
                        size_hint_x: None
                        width: dp(90)
                        font_name: app.font_name
                        font_size: sp(14)
                        color: app.theme_text_primary
                        halign: "right"
                        valign: "middle"
                        text_size: self.size

                # -------- تاریخ (فقط نمایش) --------
                Label:
                    id: date_label
                    text: ""
                    font_name: app.font_name
                    font_size: sp(12)
                    color: 0.55, 0.48, 0.50, 1
                    size_hint_y: None
                    height: dp(22)
                    halign: "right"
                    text_size: self.size

        # -------- دکمه‌ی ذخیره --------
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            RoundedButton:
                text: root.t_save_btn
                font_name: app.font_name
                font_size: sp(16)
                bold: True
                on_release: root.save_idea()
"""


class RootManager(ScreenManager):
    pass


# ---------------------------------------------------------------------------
# AuthBase
# ---------------------------------------------------------------------------
class AuthBase(Screen):
    selected_gender = StringProperty("")
    selected_age = NumericProperty(20)
    selected_storage_path = StringProperty("")
    _toast_anim = None

    def _form(self):
        return self.ids.form

    def go_forgot_password(self):
        """پیش‌فرض: در فرم ساخت اکانت این لینک نمایش داده نمی‌شود."""
        return

    def reset_fields(self):
        f = self._form()
        f.username_input.set_raw_text("")
        f.password_input.set_raw_text("")
        f.password_input.password = True
        try:
            fi = f.ids.get("fullname_input") if hasattr(f, "ids") else None
            if fi is not None:
                try:
                    fi.set_raw_text("")
                except Exception:
                    fi.text = ""
        except Exception:
            pass
        f.age_slider.value = 20
        f.age_label.text = "20"
        self.selected_gender = ""
        self.selected_age = 20
        self.selected_storage_path = ""
        f.male_btn.selected = False
        f.female_btn.selected = False
        try:
            f.ids.eye_btn.reset()
        except Exception:
            pass
        try:
            f.ids.rules_checkbox.set_checked(False)
        except Exception:
            pass

    # ---- انتخاب پوشه‌ی حافظه (SAF روی اندروید، filechooser روی دسکتاپ) ----
    def pick_storage_folder(self):
        print("[pick_storage_folder] called")  # TODO: remove after debug
        # 1) تلاش برای Storage Access Framework روی اندروید
        try:
            from jnius import autoclass, cast  # type: ignore
            from android import activity  # type: ignore
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            current_activity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            intent.addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            )

            def on_activity_result(request_code, result_code, data):
                try:
                    if data is None:
                        show_themed_toast(fa("برای ادامه، دسترسی به حافظه لازم است"))
                        return
                    uri = data.getData()
                    if uri is None:
                        show_themed_toast(fa("پوشه‌ای انتخاب نشد"))
                        return
                    try:
                        current_activity.getContentResolver().takePersistableUriPermission(
                            uri,
                            Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                        )
                    except Exception:
                        pass
                    self._set_storage_path(uri.toString())
                except Exception as e:
                    show_themed_toast(fa(f"خطا در دریافت پوشه: {e}"))

            activity.bind(on_activity_result=on_activity_result)
            current_activity.startActivityForResult(intent, 0xF01D)
            return
        except Exception as e:
            # BUGFIX 3: silent-fail → visible-log
            print(f"[pick_storage_folder][SAF] {type(e).__name__}: {e}")

        # 2) fallback دسکتاپ: plyer.filechooser (انتخاب پوشه)
        try:
            if _PLYER_AVAILABLE:
                def _cb(selection):
                    if selection:
                        path = selection[0] if isinstance(selection, (list, tuple)) else str(selection)
                        # مطمئن شو اگر فایل انتخاب شد، پوشه‌ی والدش استفاده شود
                        try:
                            if os.path.isfile(path):
                                path = os.path.dirname(path)
                        except Exception:
                            pass
                        Clock.schedule_once(lambda dt: self._set_storage_path(path), 0)
                    else:
                        show_themed_toast(fa("پوشه‌ای انتخاب نشد"))
                try:
                    plyer_filechooser.choose_dir(on_selection=_cb)
                    return
                except Exception as e1:
                    print(f"[pick_storage_folder][plyer.choose_dir] {type(e1).__name__}: {e1}")
                    try:
                        plyer_filechooser.open_file(on_selection=_cb)
                        return
                    except Exception as e2:
                        print(f"[pick_storage_folder][plyer.open_file] {type(e2).__name__}: {e2}")
            else:
                print("[pick_storage_folder][plyer] not available")
        except Exception as e:
            # BUGFIX 3: silent-fail → visible-log
            print(f"[pick_storage_folder][plyer] {type(e).__name__}: {e}")

        # 3) fallback آخر: از SAVE_DIR استفاده کن
        self._set_storage_path(SAVE_DIR)
        show_themed_toast(fa("انتخابگر پوشه در دسترس نیست؛ مسیر پیش‌فرض تنظیم شد"))

    def _set_storage_path(self, path: str):
        self.selected_storage_path = path or ""
        try:
            f = self._form()
            f.ids.storage_path_label.text = (
                path if path else App.get_running_app().t_storage_none
            )
        except Exception:
            pass

    def open_rules(self):
        # ذخیره‌ی مبدا برای بازگشت
        try:
            self.manager.get_screen("rules")._from_screen = self.name
        except Exception:
            pass
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "rules"

    def set_gender(self, gender):
        f = self._form()
        self.selected_gender = gender
        f.male_btn.selected = (gender == "male")
        f.female_btn.selected = (gender == "female")
        App.get_running_app().set_theme(gender)

    def set_age(self, value):
        f = self._form()
        self.selected_age = int(value)
        f.age_label.text = str(int(value))

    def _collect(self):
        f = self._form()
        full_name = ""
        try:
            fi = f.ids.get("fullname_input") if hasattr(f, "ids") else None
            if fi is not None:
                try:
                    full_name = fi.get_raw_text().strip()
                except Exception:
                    full_name = (fi.text or "").strip()
        except Exception:
            full_name = ""
        return {
            "username": f.username_input.get_raw_text().strip(),
            "password": f.password_input.get_raw_text().strip(),
            "full_name": full_name,
            "age": self.selected_age,
            "gender": self.selected_gender,
            "storage_path": self.selected_storage_path or "",
            "rules_checked": bool(self._is_rules_checked()),
        }

    def _is_rules_checked(self):
        try:
            return bool(self._form().ids.rules_checkbox.checked)
        except Exception:
            return False

    def format_phone(self, ti):
        digits = "".join(ch for ch in (ti.text or "") if ch.isdigit())[:10]
        if len(digits) > 6:
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        elif len(digits) > 3:
            formatted = f"{digits[:3]}-{digits[3:]}"
        else:
            formatted = digits
        if formatted != ti.text:
            ti.text = formatted

    def show_toast(self, text, color=(0.82, 0.33, 0.08, 0.96)):
        """
        نمایش نوتیفیکیشن با انیمیشن یکسان در هر دو صفحه‌ی ورود و ساخت اکانت.
        قبلاً موقعیت نهایی بر اساس card_wrap.top محاسبه می‌شد؛ چون کارت
        صفحه‌ی ساخت اکانت داخل ScrollView و ارتفاعش متغیره، این باعث اختلاف
        رفتار بصری بین دو صفحه می‌شد. حالا target صرفاً بر اساس self.height
        محاسبه می‌شود تا دقیقاً در هر دو صفحه یکسان باشد.
        """
        toast = self.ids.toast_bar
        toast.bar_color = color
        toast.clear_widgets()
        lbl = Label(text=text, font_name=APP_FONT, font_size="15sp",
                    color=(1, 1, 1, 1), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))
        toast.add_widget(lbl)

        if self._toast_anim:
            self._toast_anim.stop(toast)

        toast.opacity = 1
        toast.top = self.height + dp(10)

        # هدف انیمیشن: کمی زیر بالای صفحه، مستقل از محتوای اسکرول
        target_top = self.height - dp(24)

        anim = (
            Animation(top=target_top, duration=0.35, t="out_cubic")
            + Animation(top=target_top, duration=2.00)
            + Animation(top=self.height + dp(10), opacity=0, duration=0.30, t="in_cubic")
        )
        self._toast_anim = anim
        anim.bind(on_complete=lambda *a: setattr(toast, "opacity", 0))
        anim.start(toast)

    # ---- ناوبری به صفحه‌ی راهنما ----
    def open_help(self):
        try:
            help_scr = self.manager.get_screen("help")
            help_scr.set_source(self.name)
        except Exception:
            pass
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "help"


# ---------------------------------------------------------------------------
# LoginScreen
# ---------------------------------------------------------------------------
class LoginScreen(AuthBase):
    def on_pre_enter(self, *args):
        app = App.get_running_app()
        # تم پیش‌فرض سفید تا کاربر جنسیت رو انتخاب نکرده
        app.set_theme("")
        if not app.skip_autologin:
            uname = get_session_username()
            if uname and username_exists(uname):
                acc = get_account(uname)
                Clock.schedule_once(lambda dt: self._enter_app(acc), 0.05)
                return
        self.reset_fields()

    def try_submit(self):
        d = self._collect()
        username = d["username"]
        password = d["password"]
        if not username or not password or not d["gender"]:
            self.show_toast(fa("لطفاً نام کاربری، رمز عبور، جنسیت و سن را وارد کنید"))
            return
        if not _is_valid_username(username):
            self.show_toast(fa("نام کاربری معتبر نیست"))
            return

        ok, msg, acc = verify_login(username, password, d["age"], d["gender"])
        if not ok:
            self.show_toast(fa(msg))
            return

        set_session(username)
        App.get_running_app().skip_autologin = False
        self._enter_app(acc)

    def go_signup(self):
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "signup"

    def go_forgot_password(self):
        """رفتن به صفحه‌ی بازیابی رمز (فقط از فرم ورود)."""
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "forgot_password"

    # ---- ورود سریع با انتخاب پوشه‌ی ذخیره‌سازی ----
    def login_by_folder(self):
        """
        باز کردن فایل‌چوزر برای انتخاب پوشه، سپس جستجو در دیتابیس برای پیدا کردن
        اکانتی که فیلد storage_folder یا basename پوشه‌اش با پوشه‌ی انتخاب‌شده
        مطابقت داشته باشد و ورود مستقیم بدون نیاز به رمز/جنسیت/سن.
        """
        def _finish(path):
            path = (path or "").strip()
            if not path:
                self.show_toast(fa("پوشه‌ای انتخاب نشد"))
                return
            # اگر فایل انتخاب شد، پوشه‌ی والدش
            try:
                if os.path.isfile(path):
                    path = os.path.dirname(path)
            except Exception:
                pass

            norm_sel = path.rstrip("/\\")

            # 1) خواندن مستقیم account.json از پوشه‌ی انتخاب‌شده (بدون نیاز به
            #    هیچ فایلی بیرون از همین پوشه).
            match = read_account_file(norm_sel)

            # 2) اگر خودِ پوشه account.json نداشت، یک سطح پایین‌تر را هم بگرد
            #    (مثلاً کاربر پوشه‌ی والد را انتخاب کرده باشد).
            if not match:
                try:
                    for name in os.listdir(norm_sel):
                        sub_path = os.path.join(norm_sel, name)
                        if os.path.isdir(sub_path):
                            cand = read_account_file(sub_path)
                            if cand:
                                match = cand
                                norm_sel = sub_path
                                break
                except Exception:
                    pass

            if not match:
                self.show_toast(fa("در این پوشه اکانتی (account.json) پیدا نشد"))
                return

            # مسیر پوشه را به‌روزرسانی و در ایندکس سبک ثبت کن تا دفعات بعد هم
            # ورود معمولی با نام کاربری کار کند.
            match["storage_folder"] = norm_sel
            try:
                register_account_folder(match.get("username", ""), norm_sel)
                write_account_file(match)
                set_last_storage_path(os.path.dirname(norm_sel) or norm_sel)
            except Exception:
                pass

            uname = match.get("username", "")
            if not uname:
                self.show_toast(fa("اطلاعات اکانت نامعتبر است"))
                return
            set_session(uname)
            App.get_running_app().skip_autologin = False
            self._enter_app(match)

        # 1) اندروید: مستقیماً SAF (دقیقاً مثل pick_storage_folder که روی APK کار می‌کند).
        #    plyer روی اندروید بدون خطا برمی‌گردد ولی عملاً کار نمی‌کند، پس
        #    نباید اول امتحان شود.
        try:
            from jnius import autoclass, cast  # type: ignore
            from android import activity  # type: ignore
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            current_activity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            intent.addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            )

            def on_activity_result(request_code, result_code, data):
                try:
                    if data is None:
                        Clock.schedule_once(lambda dt: _finish(""), 0)
                        return
                    uri = data.getData()
                    if uri is None:
                        Clock.schedule_once(lambda dt: _finish(""), 0)
                        return
                    try:
                        current_activity.getContentResolver().takePersistableUriPermission(
                            uri,
                            Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                        )
                    except Exception:
                        pass
                    Clock.schedule_once(lambda dt: _finish(uri.toString()), 0)
                except Exception:
                    Clock.schedule_once(lambda dt: _finish(""), 0)

            activity.bind(on_activity_result=on_activity_result)
            current_activity.startActivityForResult(intent, 0xF01E)
            return
        except Exception as e:
            print(f"[login_by_folder][SAF] {type(e).__name__}: {e}")

        # 2) fallback دسکتاپ/غیراندروید: plyer.filechooser
        try:
            if _PLYER_AVAILABLE:
                def _cb(selection):
                    p = ""
                    if selection:
                        p = selection[0] if isinstance(selection, (list, tuple)) else str(selection)
                    Clock.schedule_once(lambda dt: _finish(p), 0)
                try:
                    plyer_filechooser.choose_dir(on_selection=_cb)
                    return
                except Exception as e1:
                    print(f"[login_by_folder][plyer.choose_dir] {type(e1).__name__}: {e1}")
                    try:
                        plyer_filechooser.open_file(on_selection=_cb)
                        return
                    except Exception as e2:
                        print(f"[login_by_folder][plyer.open_file] {type(e2).__name__}: {e2}")
            else:
                print("[login_by_folder][plyer] not available")
        except Exception as e:
            print(f"[login_by_folder][plyer] {type(e).__name__}: {e}")

        self.show_toast(fa("انتخابگر پوشه در دسترس نیست"))

    def _enter_app(self, acc):
        app = App.get_running_app()
        app.skip_autologin = False
        current = dict(acc)
        app.current_user = current
        app.active_gender = acc.get("gender", "female")
        app.set_theme(app.active_gender)

        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "categories"


# ---------------------------------------------------------------------------
# SignupScreen
# ---------------------------------------------------------------------------
class SignupScreen(AuthBase):
    def on_pre_enter(self, *args):
        App.get_running_app().set_theme("")
        self.reset_fields()
        # یادآوری آخرین مسیر ذخیره‌سازی انتخاب‌شده در دفعات قبل
        last = get_last_storage_path()
        if last:
            self._set_storage_path(last)

    def try_submit(self):
        d = self._collect()
        username = d["username"]
        full_name = d.get("full_name", "")
        pw = d["password"]
        if (not username or not full_name or not pw or not d["gender"]
                or not d.get("storage_path") or not d.get("rules_checked")):
            self.show_toast(fa("لطفاً تمام اطلاعات را وارد کنید"))
            return
        if not _is_valid_username(username):
            self.show_toast(fa("نام کاربری باید حداقل ۳ کاراکتر و بدون فاصله باشد"))
            return
        if len(pw) < 4:
            self.show_toast(fa("رمز باید حداقل ۴ کاراکتر باشد"))
            return
        if username_exists(username):
            self.show_toast(fa("این نام کاربری قبلاً ثبت شده؛ از صفحه ورود استفاده کن"))
            return

        ok, msg = create_account(username, pw, d["age"], d["gender"],
                                 storage_path=d.get("storage_path", ""),
                                 full_name=full_name)
        if not ok:
            self.show_toast(fa(msg))
            return

        # ذخیره‌ی آخرین مسیر انتخابی برای دفعات بعد
        try:
            set_last_storage_path(d.get("storage_path", ""))
        except Exception:
            pass

        # پوشه‌ی اختصاصی کاربر و account.json داخل آن، در create_account ساخته
        # شده‌اند. اینجا فقط به کاربر اطلاع می‌دهیم اگر مسیر SAF بوده و داده‌ها
        # ناچاراً در پوشه‌ی محلی اکانت ذخیره شده‌اند.
        try:
            sp = (d.get("storage_path", "") or "")
            if _is_saf(sp) and not _saf_ready(sp):
                self.show_toast(fa("دسترسی به پوشه‌ی انتخابی ممکن نشد؛ داده‌ها در حافظه‌ی داخلی ذخیره شدند"))
        except Exception:
            pass

        self.show_toast(fa("اکانتتون با موفقیت ساخته شد"),
                        color=(0.20, 0.70, 0.32, 0.96))
        # ۲.۸ ثانیه بعد (تا نوتیف کامل دیده شود) برو به لاگین
        Clock.schedule_once(lambda dt: self._go_login(), 2.8)

    def go_login(self):
        self._go_login()

    def _go_login(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "login"


# ---------------------------------------------------------------------------
# RulesScreen — نمایش متن قوانین
# ---------------------------------------------------------------------------
class RulesScreen(Screen):
    _from_screen = "signup"

    def accept_rules(self):
        target = self._from_screen or "signup"
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = target
        # تیک زدن خودکار چک‌باکس قوانین در صفحه‌ی مبدا
        try:
            scr = self.manager.get_screen(target)
            scr._form().ids.rules_checkbox.set_checked(True)
        except Exception:
            pass





# ---------------------------------------------------------------------------
# EditProfileScreen — صفحه‌ی ویرایش پروفایل (سن، نام و نام‌خانوادگی، رمز عبور)
# ---------------------------------------------------------------------------
class EditProfileScreen(Screen):
    header_text = StringProperty("")
    t_fullname_label = StringProperty("")
    t_password_label = StringProperty("")
    t_password_hint = StringProperty("")
    t_age_label = StringProperty("")
    t_save_btn = StringProperty("")
    parent_screen = ObjectProperty(None, allownone=True)

    def on_pre_enter(self, *args):
        self.header_text = fa("ویرایش پروفایل")
        self.t_fullname_label = fa("نام و نام خانوادگی:")
        self.t_password_label = fa("رمز عبور جدید (اختیاری):")
        self.t_password_hint = fa("خالی بگذارید یعنی تغییر نکند")
        self.t_age_label = fa("سن:")
        self.t_save_btn = fa("ذخیره")
        # ids در on_pre_enter لزوماً هنوز کاملاً initialize نشده‌اند؛ با یک تیک
        # به تأخیر می‌اندازیم تا RTLTextInput._sync_display روی مقدار اولیه
        # درست اعمال شود.
        Clock.schedule_once(lambda dt: self.load_user(), 0)

    def load_user(self):
        app = App.get_running_app()
        user = dict(app.current_user or {})
        uname = user.get("username", "")
        if uname:
            fresh = get_account(uname)
            if fresh:
                user = dict(fresh)
                app.current_user = user
        # Non-editable displays
        try:
            self.ids.username_label.text = fa(f"نام کاربری: {user.get('username','')}")
            g = user.get("gender", "")
            g_txt = "☀️ خورشید (پسر)" if g == "male" else ("🌙 ماه (دختر)" if g == "female" else "")
            self.ids.gender_label.text = fa(f"جنسیت: {g_txt}")
            self.ids.fullname_input.set_raw_text(user.get("full_name", "") or "")
            self.ids.password_input.set_raw_text("")
            try:
                age_v = int(user.get("age", 20) or 20)
            except Exception:
                age_v = 20
            if age_v < 15: age_v = 15
            if age_v > 35: age_v = 35
            self.ids.age_slider.value = age_v
            self.ids.age_value_label.text = str(age_v)
        except Exception as e:
            print("[EditProfile] load_user failed:", e)

    def _on_age(self, v):
        try:
            self.ids.age_value_label.text = str(int(v))
        except Exception:
            pass

    def save_changes(self):
        app = App.get_running_app()
        uname = (app.current_user or {}).get("username", "")
        if not uname:
            show_themed_toast(fa("خطا: کاربر شناسایی نشد"))
            return
        try:
            new_full = (self.ids.fullname_input.get_raw_text() or "").strip()
            new_pass = self.ids.password_input.get_raw_text() or ""
            new_age = int(self.ids.age_slider.value)
        except Exception as e:
            show_themed_toast(fa(f"ورودی نامعتبر: {e}"))
            return

        db = load_db()
        acc = db["accounts"].get(uname)
        if not acc:
            show_themed_toast(fa("اکانت پیدا نشد"))
            return
        # Overwrite the editable fields only. Do NOT touch gender or username.
        acc["full_name"] = new_full
        acc["age"] = new_age
        if new_pass:
            acc["password"] = new_pass
        db["accounts"][uname] = acc
        save_db(db)

        # Sync current_user with fresh DB copy.
        app.current_user = dict(get_account(uname))
        show_themed_toast(fa("تغییرات با موفقیت ذخیره شد ✓"))
        Clock.schedule_once(lambda dt: self.go_back(), 0.35)

    def go_back(self):
        app = App.get_running_app()
        app.root.transition = SlideTransition(direction="right")
        app.root.current = "categories"
        # Refresh categories avatar area with latest data
        try:
            cats = app.root.get_screen("categories")
            cats.refresh_avatar_area()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HelpScreen — راهنمای اختیاری برای صفحه‌ی ورود / ساخت اکانت
# با همان تم پویا (theme_bg، theme_title، ...) طراحی شده و متن آن بر اساس
# صفحه‌ی مبدأ تغییر می‌کند.
# ---------------------------------------------------------------------------
class HelpScreen(Screen):
    help_text = StringProperty("")
    help_text_raw = StringProperty("")
    _from_screen = "login"

    def set_source(self, from_name: str):
        self._from_screen = from_name or "login"
        app = App.get_running_app()
        if self._from_screen == "signup":
            self.help_text = app.t_help_body_signup
            self.help_text_raw = app.t_help_body_signup_raw
        elif self._from_screen == "ideas":
            self.help_text = app.t_help_body_ideas
            self.help_text_raw = app.t_help_body_ideas_raw
        else:
            self.help_text = app.t_help_body_login
            self.help_text_raw = app.t_help_body_login_raw

    def on_pre_enter(self, *args):
        # اطمینان از اینکه متن راهنما بر اساس مبدأ به‌روز است
        self.set_source(self._from_screen)

    def go_back(self):
        target = self._from_screen or "login"
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = target

# ---------------------------------------------------------------------------
# InputBox — کانتینر گردِ باکس‌های ورودی
# باگ قبلی: فقط بخشی از مساحتِ بصریِ باکس فوکوس می‌گرفت. حالا هر لمس در هر نقطه
# از کل کادرِ گرد، فوکوس را به فیلد ورودیِ داخلش می‌دهد (رفتار استاندارد موبایل).
# این کلاس در همه‌ی باکس‌های ورودیِ برنامه به‌طور یکسان استفاده می‌شود.
# ---------------------------------------------------------------------------
class InputBox(BoxLayout):

    def find_input(self):
        """اولین TextInput داخل این کانتینر (جست‌وجوی عرضی)."""
        stack = list(self.children)
        while stack:
            w = stack.pop(0)
            if isinstance(w, TextInput):
                return w
            try:
                stack.extend(w.children)
            except Exception:
                pass
        return None

    def focus_input(self):
        ti = self.find_input()
        if ti is None or ti.disabled:
            return False
        try:
            ti.focus = True
        except Exception:
            return False
        try:
            if hasattr(ti, "_move_cursor_to_end"):
                ti._move_cursor_to_end()
            else:
                ti.cursor = (len(ti.text or ""), 0)
        except Exception:
            pass
        return True

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        btn = getattr(touch, "button", None)
        if btn is not None and btn != "left":
            return super().on_touch_down(touch)
        # اول به بچه‌ها فرصت بده (مثل دکمه‌ی چشمِ رمز)
        if super().on_touch_down(touch):
            return True
        # لمس روی ناحیه‌ی خالیِ کادر → فوکوس روی فیلد ورودی
        return bool(self.focus_input())


try:
    _Factory.register("InputBox", cls=InputBox)
except Exception:
    pass


# ---------------------------------------------------------------------------
# CelebrationPopup — پیام تبریک گرافیکی «انجام دادم»
# ---------------------------------------------------------------------------
class CelebrationPopup(ModalView):
    """مودالِ جشن با آیکون بزرگ، کانفتیِ رنگی و بسته‌شدنِ خودکارِ نرم."""

    def __init__(self, text="", emoji="🎉", duration=2.2, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.background = ""
        self.background_color = (0, 0, 0, 0)
        self.overlay_color = (0, 0, 0, 0.28)
        self.auto_dismiss = True
        self._msg = text or fa("آفرین!")
        self._emoji = emoji
        self._duration = max(1.5, min(2.5, float(duration)))
        self._closing = False
        self._build()

    # ---------------- ساخت ظاهر ----------------
    def _build(self):
        app = App.get_running_app()
        theme = app.current_theme if app else THEME_WHITE
        accent = theme["accent"]
        title_col = theme["title"]

        w = min(dp(320), Window.width * 0.86)
        h = dp(240)
        self.size = (w, h)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        root = FloatLayout(size_hint=(1, 1))

        card = FloatLayout(size_hint=(1, 1))
        with card.canvas.before:
            Color(0, 0, 0, 0.16)
            self._sh = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(28)])
            self._bg_col = Color(*neutral("surface_92"))
            self._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(28)])
            Color(accent[0], accent[1], accent[2], 0.85)
            self._ln = Line(rounded_rectangle=(card.x, card.y, card.width, card.height, dp(28)),
                            width=1.6)

        def _upd(*_a):
            self._sh.pos = (card.x + dp(2), card.y - dp(3))
            self._sh.size = card.size
            self._bg.pos = card.pos
            self._bg.size = card.size
            self._ln.rounded_rectangle = (card.x, card.y, card.width, card.height, dp(28))
        card.bind(pos=_upd, size=_upd)

        # لایه‌ی کانفتی (زیرِ متن)
        self._confetti_layer = FloatLayout(size_hint=(1, 1))
        card.add_widget(self._confetti_layer)

        # آیکون جشن با انیمیشن ورودِ فنری
        self._icon = Label(text=self._emoji, font_size=sp(56),
                           size_hint=(None, None), size=(dp(90), dp(90)),
                           pos_hint={"center_x": 0.5, "center_y": 0.68},
                           halign="center", valign="middle")
        self._icon.font_size = sp(18)
        self._icon.opacity = 0
        card.add_widget(self._icon)

        lbl = Label(text=self._msg, font_name=APP_FONT, font_size=sp(16), bold=True,
                    color=(title_col[0], title_col[1], title_col[2], 1),
                    halign="center", valign="middle",
                    size_hint=(0.86, None), height=dp(58),
                    pos_hint={"center_x": 0.5, "center_y": 0.28})
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        lbl.opacity = 0
        self._lbl = lbl
        card.add_widget(lbl)

        root.add_widget(card)
        self.add_widget(root)
        self.opacity = 0

    def _refresh_theme(self, *a):
        try:
            self._bg_col.rgba = neutral("surface_92")
        except Exception:
            pass
        try:
            _app = App.get_running_app()
            _t = (_app.current_theme if _app else THEME_WHITE)["title"]
            self._lbl.color = (_t[0], _t[1], _t[2], 1)
        except Exception:
            pass

    # ---------------- انیمیشن‌ها ----------------
    def on_open(self):
        Animation(opacity=1, duration=0.18, t="out_quad").start(self)
        # ورودِ فنریِ آیکون (اسکیل با font_size)
        self._icon.opacity = 1
        Animation(font_size=sp(58), duration=0.55, t="out_back").start(self._icon)
        Animation(opacity=1, duration=0.35, t="out_quad").start(self._lbl)
        Clock.schedule_once(lambda dt: self._pulse(), 0.55)
        self._spawn_confetti()
        Clock.schedule_once(lambda dt: self._close(), self._duration)

    def _pulse(self, *_a):
        if self._closing:
            return
        (Animation(font_size=sp(64), duration=0.35, t="in_out_sine")
         + Animation(font_size=sp(58), duration=0.35, t="in_out_sine")).start(self._icon)

    def _spawn_confetti(self):
        colors = [(0.98, 0.35, 0.45, 1), (0.99, 0.75, 0.20, 1),
                  (0.30, 0.72, 0.55, 1), (0.36, 0.55, 0.90, 1),
                  (0.66, 0.42, 0.86, 1)]
        for _i in range(18):
            d = random.uniform(dp(7), dp(13))
            dot = Widget(size_hint=(None, None), size=(d, d))
            col = random.choice(colors)
            with dot.canvas:
                Color(*col)
                el = Ellipse(pos=dot.pos, size=dot.size)
            dot._el = el
            dot.bind(pos=lambda w, v, _e=el: setattr(_e, "pos", v),
                     size=lambda w, v, _e=el: setattr(_e, "size", v))
            dot.pos_hint = {}
            dot.x = self.width * random.uniform(0.08, 0.9)
            dot.y = self.height * random.uniform(0.85, 1.05)
            self._confetti_layer.add_widget(dot)
            anim = Animation(y=self.height * random.uniform(-0.05, 0.12),
                             x=dot.x + random.uniform(-dp(26), dp(26)),
                             opacity=0,
                             duration=random.uniform(1.1, 1.9),
                             t="in_quad")
            Clock.schedule_once(lambda dt, _d=dot, _a=anim: _a.start(_d),
                                random.uniform(0, 0.45))

    def _close(self, *_a):
        if self._closing:
            return
        self._closing = True
        anim = Animation(opacity=0, duration=0.28, t="in_quad")
        anim.bind(on_complete=lambda *a: self.dismiss())
        anim.start(self)

    def on_touch_down(self, touch):
        # لمس کاربر → بسته شدنِ زودترِ نرم
        super().on_touch_down(touch)
        self._close()
        return True


try:
    _Factory.register("CelebrationPopup", cls=CelebrationPopup)
except Exception:
    pass


# ---------------------------------------------------------------------------
# KV صفحه‌ی «فراموشی رمز عبور»
# ---------------------------------------------------------------------------
FORGOT_KV = """
<ForgotPasswordScreen>:
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: app.theme_bubble1
        Ellipse:
            pos: self.width * 0.55, self.height * 0.78
            size: dp(220), dp(220)
        Color:
            rgba: app.theme_bubble2
        Ellipse:
            pos: -dp(70), -dp(50)
            size: dp(190), dp(190)
    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: max(self.minimum_height + dp(20), root.height)
            padding: dp(18), dp(18)
            spacing: dp(12)

            BoxLayout:
                size_hint_y: None
                height: dp(46)
                spacing: dp(10)
                BoxLayout:
                    size_hint_x: None
                    width: dp(54)
                    padding: dp(7)
                    canvas.before:
                        Color:
                            rgba: app.theme_accent
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(14)]
                    IconImageButton:
                        source: app.back_image
                        on_release: root.go_back()
                Label:
                    text: app.t_forgot_title
                    font_name: app.font_name
                    font_size: sp(19)
                    bold: True
                    color: app.theme_title
                    halign: "right"
                    valign: "middle"
                    text_size: self.size

            RTLLabel:
                id: forgot_desc
                raw_text: root.desc_raw
                font_name: app.font_name
                font_size: sp(14)
                color: 0.42, 0.36, 0.38, 1
                size_hint_y: None
                height: self.texture_size[1] + dp(8)

            InputBox:
                size_hint_y: None
                height: dp(50)
                canvas.before:
                    Color:
                        rgba: app.theme_input_bg
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(16)]
                RTLTextInput:
                    id: key_input
                    hint_text: app.t_forgot_hint
                    font_name: app.font_name
                    font_size: sp(15)
                    multiline: False
                    background_color: 0, 0, 0, 0
                    foreground_color: app.theme_text_primary
                    hint_text_color: app.theme_text_hint
                    cursor_color: 0.8, 0.5, 0.6, 1
                    padding: dp(14), dp(14)

            BoxLayout:
                id: check_holder
                size_hint_y: None
                height: dp(52)

            BoxLayout:
                id: reset_holder
                orientation: "vertical"
                size_hint_y: None
                height: dp(0)
                spacing: dp(10)

            Widget:
"""


# ---------------------------------------------------------------------------
# ForgotPasswordScreen — بازیابی/تغییر رمز با ریکاوری‌کی
# ---------------------------------------------------------------------------
class ForgotPasswordScreen(Screen):
    desc_raw = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._found_user = ""
        self._found_acc = {}
        self._check_color = None
        self._reset_built = False
        self._new_pw_input = None

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.desc_raw = (
            "«ریکاوری‌کی» یک کد ۲۴ کاراکتریِ یکتاست که هنگام ساخت اکانت برای تو ساخته شده و "
            "داخل فایل recovery_key.txt در همان پوشه‌ای ذخیره شده که موقع ساخت اکانت به‌عنوان "
            "محل ذخیره‌سازی انتخاب کرده‌ای.\n\n"
            "با وارد کردن این کد می‌توانی بدون نیاز به رمز قدیمی، رمز عبور اکانتت را تغییر بدهی. "
            "کافی است فایل را باز کنی، کد را کپی کنی و در کادر زیر بگذاری."
        )
        self._found_user = ""
        self._found_acc = {}
        try:
            self.ids.key_input.set_raw_text("")
        except Exception:
            pass
        self._build_check_button()
        self._hide_reset_box()

    # ---------------- دکمه‌ی بررسی ----------------
    def _build_check_button(self):
        holder = self.ids.check_holder
        holder.clear_widgets()
        wrap = BoxLayout(size_hint=(1, 1))
        with wrap.canvas.before:
            self._check_color = Color(*neutral("surface"))
            rr = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[dp(16)])
            Color(*neutral("border"))
            ln = Line(rounded_rectangle=(wrap.x, wrap.y, wrap.width, wrap.height, dp(16)),
                      width=1.3)

        def _upd(*_a):
            rr.pos = wrap.pos
            rr.size = wrap.size
            ln.rounded_rectangle = (wrap.x, wrap.y, wrap.width, wrap.height, dp(16))
        wrap.bind(pos=_upd, size=_upd)

        app = App.get_running_app()
        btn = Button(text=app.t_forgot_check, font_name=APP_FONT, font_size="16sp",
                     bold=True, background_normal="", background_down="",
                     background_color=(0, 0, 0, 0), color=neutral("text_primary"))
        self._check_btn = btn
        btn.bind(on_release=lambda *a: self.check_key())
        wrap.add_widget(btn)
        holder.add_widget(wrap)

    def _refresh_theme(self, *a):
        try:
            self._build_check_button()
        except Exception:
            pass

    def check_key(self):
        key = ""
        try:
            key = self.ids.key_input.get_raw_text().strip()
        except Exception:
            pass
        if not key:
            show_themed_toast(fa("ریکاوری‌کی را وارد کنید"))
            return
        uname, acc = find_account_by_recovery_key(key)
        if not uname:
            show_themed_toast(fa("ریکاوری‌کی نامعتبر است"))
            return
        self._found_user = uname
        self._found_acc = acc
        # انیمیشن نرمِ سفید → سبز روی پس‌زمینه‌ی دکمه
        if self._check_color is not None:
            Animation(r=0.231, g=0.722, b=0.216, a=1,
                      duration=0.45, t="in_out_quad").start(self._check_color)
        try:
            self._check_btn.color = (1, 1, 1, 1)
        except Exception:
            pass
        self._show_reset_box()

    # ---------------- باکس رمز جدید ----------------
    def _hide_reset_box(self):
        holder = self.ids.reset_holder
        holder.clear_widgets()
        holder.height = dp(0)
        holder.opacity = 0
        self._reset_built = False
        self._new_pw_input = None

    def _show_reset_box(self):
        if self._reset_built:
            return
        app = App.get_running_app()
        holder = self.ids.reset_holder
        holder.clear_widgets()
        holder.opacity = 0

        lbl = Label(text=app.t_forgot_newpw, font_name=APP_FONT, font_size="14sp",
                    bold=True, color=neutral("text_primary"),
                    size_hint_y=None, height=dp(24),
                    halign="right", valign="middle")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
        holder.add_widget(lbl)

        box = InputBox(size_hint_y=None, height=dp(50))
        with box.canvas.before:
            Color(*(app.theme_input_bg if app else (0.96, 0.94, 0.95, 1)))
            rr = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(16)])
        box.bind(pos=lambda w, v, _r=rr: setattr(_r, "pos", v),
                 size=lambda w, v, _r=rr: setattr(_r, "size", v))
        pw = RTLTextInput(hint_text=app.t_forgot_newpw, font_name=APP_FONT,
                          font_size="15sp", multiline=False, password=True,
                          background_color=(0, 0, 0, 0),
                          foreground_color=neutral("text_primary"),
                          hint_text_color=(0.65, 0.6, 0.62, 1),
                          cursor_color=(0.8, 0.5, 0.6, 1),
                          padding=(dp(14), dp(14)))
        self._new_pw_input = pw
        box.add_widget(pw)
        holder.add_widget(box)

        btn_wrap = BoxLayout(size_hint_y=None, height=dp(50))
        with btn_wrap.canvas.before:
            Color(0.231, 0.722, 0.216, 1)
            rr2 = RoundedRectangle(pos=btn_wrap.pos, size=btn_wrap.size, radius=[dp(16)])
        btn_wrap.bind(pos=lambda w, v, _r=rr2: setattr(_r, "pos", v),
                      size=lambda w, v, _r=rr2: setattr(_r, "size", v))
        submit = Button(text=app.t_forgot_submit, font_name=APP_FONT, font_size="16sp",
                        bold=True, background_normal="", background_down="",
                        background_color=(0, 0, 0, 0), color=(1, 1, 1, 1))
        submit.bind(on_release=lambda *a: self.submit_new_password())
        btn_wrap.add_widget(submit)
        holder.add_widget(btn_wrap)

        holder.height = dp(24) + dp(50) + dp(50) + dp(20)
        holder.y -= dp(14)
        self._reset_built = True
        Animation(opacity=1, duration=0.35, t="out_quad").start(holder)
        Animation(y=holder.y + dp(14), duration=0.35, t="out_back").start(holder)

    def submit_new_password(self):
        new_pw = ""
        try:
            new_pw = (self._new_pw_input.get_raw_text() or "").strip()
        except Exception:
            pass
        if not new_pw:
            show_themed_toast(fa("رمز جدید را وارد کنید"))
            return
        key = ""
        try:
            key = self.ids.key_input.get_raw_text().strip()
        except Exception:
            pass
        ok, msg, uname = change_password_by_recovery_key(key, new_pw)
        if not ok:
            show_themed_toast(fa(msg))
            return
        show_themed_toast(fa("رمز عبور با موفقیت تغییر کرد ✓"))
        Clock.schedule_once(lambda dt: self._back_to_login(), 1.6)

    def _back_to_login(self):
        try:
            self.manager.transition = SlideTransition(direction="right")
            self.manager.current = "login"
        except Exception:
            pass

    def go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "login"


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class LahzeSazApp(App):
    current_user = {}
    active_gender = ""
    skip_autologin = False

    font_name = StringProperty(APP_FONT)
    diary_font = StringProperty(DIARY_FONT)
    boy_image = StringProperty(BOY_IMAGE)
    girl_image = StringProperty(GIRL_IMAGE)
    back_image = StringProperty(BACK_IMAGE if os.path.exists(BACK_IMAGE) else "")
    random_image = StringProperty(RANDOM_IMAGE if os.path.exists(RANDOM_IMAGE) else "")
    question_image = StringProperty(QUESTION_IMAGE if os.path.exists(QUESTION_IMAGE) else "")

    theme_bg = ListProperty(list(THEME_WHITE["bg"]))
    theme_accent = ListProperty(list(THEME_WHITE["accent"]))
    theme_accent_soft = ListProperty(list(THEME_WHITE["accent_soft"]))
    theme_card_border = ListProperty(list(THEME_WHITE["card_border"]))
    theme_title = ListProperty(list(THEME_WHITE["title"]))
    theme_input_bg = ListProperty(list(THEME_WHITE["input_bg"]))
    theme_bubble1 = ListProperty(list(THEME_WHITE["bubble1"]))
    theme_bubble2 = ListProperty(list(THEME_WHITE["bubble2"]))
    theme_cat_sub = ListProperty(list(THEME_WHITE["cat_sub"]))
    theme_surface = ListProperty(list(NEUTRAL_LIGHT["surface"]))
    theme_surface_92 = ListProperty(list(NEUTRAL_LIGHT["surface_92"]))
    theme_surface_soft = ListProperty(list(NEUTRAL_LIGHT["surface_soft"]))
    theme_surface_glass = ListProperty(list(NEUTRAL_LIGHT["surface_glass"]))
    theme_glass_grey = ListProperty(list(NEUTRAL_LIGHT["glass_grey"]))
    theme_glass_border = ListProperty(list(NEUTRAL_LIGHT["glass_border"]))
    theme_text_primary = ListProperty(list(NEUTRAL_LIGHT["text_primary"]))
    theme_text_secondary = ListProperty(list(NEUTRAL_LIGHT["text_secondary"]))
    theme_text_body = ListProperty(list(NEUTRAL_LIGHT["text_body"]))
    theme_text_strong = ListProperty(list(NEUTRAL_LIGHT["text_strong"]))
    theme_text_hint = ListProperty(list(NEUTRAL_LIGHT["text_hint"]))
    theme_border = ListProperty(list(NEUTRAL_LIGHT["border"]))
    theme_divider = ListProperty(list(NEUTRAL_LIGHT["divider"]))
    theme_paper = ListProperty(list(NEUTRAL_LIGHT["paper"]))
    theme_paper_line = ListProperty(list(NEUTRAL_LIGHT["paper_line"]))
    theme_paper_text = ListProperty(list(NEUTRAL_LIGHT["paper_text"]))
    theme_paper_sub = ListProperty(list(NEUTRAL_LIGHT["paper_sub"]))
    current_theme = THEME_WHITE
    dark_mode = BooleanProperty(False)
    _theme_anim = None

    t_title = StringProperty("")
    t_subtitle = StringProperty("")
    t_signup_title = StringProperty("")
    t_signup_sub = StringProperty("")
    t_username = StringProperty("")
    t_password = StringProperty("")
    t_phone = StringProperty("")
    t_gender = StringProperty("")
    t_female = StringProperty("")
    t_male = StringProperty("")
    t_age = StringProperty("")
    t_login_btn = StringProperty("")
    t_signup_btn = StringProperty("")
    t_signup_link = StringProperty("")
    t_login_link = StringProperty("")
    t_password_confirm = StringProperty("")
    t_fullname = StringProperty("")
    t_login_username = StringProperty("")
    t_shared = StringProperty("")
    t_cat_title = StringProperty("")
    t_cat_sub = StringProperty("")
    t_storage_label = StringProperty("")
    t_storage_none = StringProperty("")
    t_rules_accept = StringProperty("")
    t_rules_title = StringProperty("")
    t_rules_body = StringProperty("")
    t_rules_ok_btn = StringProperty("")
    t_folder_login_link = StringProperty("")
    t_forgot_link = StringProperty("")
    t_forgot_title = StringProperty("")
    t_forgot_desc = StringProperty("")
    t_forgot_hint = StringProperty("")
    t_forgot_check = StringProperty("")
    t_forgot_newpw = StringProperty("")
    t_forgot_submit = StringProperty("")
    t_help_title = StringProperty("")
    t_help_body_login = StringProperty("")
    t_help_body_signup = StringProperty("")
    t_help_body_ideas = StringProperty("")
    t_help_body_login_raw = StringProperty("")
    t_help_body_signup_raw = StringProperty("")
    t_help_body_ideas_raw = StringProperty("")
    t_rules_body_raw = StringProperty("")
    t_help_back_btn = StringProperty("")

    def build(self):
        self.title = "لحظه‌ساز"
        self.t_title = fa("لحظه‌ساز")
        self.t_subtitle = fa("هر دیت یه لحظه خاطره‌انگیز")
        self.t_signup_title = fa("ساخت حساب")
        self.t_signup_sub = fa("یک حساب جدید بساز")
        self.t_username = fa("ساخت نام کاربری")
        self.t_password = fa("رمز عبور را وارد کنید")
        self.t_password_confirm = fa("تکرار رمز")
        self.t_fullname = fa("نام و نام خانوادگی")
        self.t_login_username = fa("ورود با نام کاربری")
        self.t_phone = fa("")
        self.t_gender = fa("جنسیت")
        self.t_female = fa("دختر")
        self.t_male = fa("پسر")
        self.t_age = fa("سن")
        self.t_login_btn = fa("ورود")
        self.t_signup_btn = fa("ساخت اکانت")
        self.t_signup_link = fa("اکانت نداری ؟ همین الان بسازش")
        self.t_login_link = fa("اکانت داری ؟ پس چرا معطلی")
        self.t_shared = fa("اطلاعات شما به‌صورت محلی روی همین دستگاه ذخیره می‌شود")
        self.t_cat_title = fa("دسته‌بندی ایده‌ها")
        self.t_cat_sub = fa("یکی رو انتخاب کن تا ایده‌ها رو ببینی")
        self.t_storage_label = fa("محل انتخاب حافظه در دستگاه")
        self.t_storage_none = fa("هنوز انتخاب نشده")
        # فقط کلمه‌ی «قوانین» آبی، زیرخط‌دار و کلیک‌پذیر است (ref)
        # کل جمله به‌صورت لینک کلیک‌پذیر، آبی و زیرخط‌دار
        self.t_rules_accept = (
            "[ref=rules][color=4073d9][u]"
            + fa("من تمام قوانین را مطالعه کردم و از ساخت اکانت در این برنامه اطمینان و صلاحیت کامل دارم")
            + "[/u][/color][/ref]"
        )
        self.t_rules_title = fa("قوانین برنامه")
        self.t_rules_body_raw = (
            "تمامی ایده‌ها که برنامه‌ی لحظه‌ساز در اختیار شما قرار داده است، ایده‌هایی مناسب "
            "برای سنین متفاوت انتخاب شده‌اند و اگر در اجرای یکی از این ایده‌ها شخصی آسیب "
            "جسمانی یا روحی ببیند، مسئولیت آن با خود اوست و به سازنده و برنامه‌ی لحظه‌ساز "
            "ربطی ندارد.\n\n"
            "چنانچه در ساخت اکانت از شرایط برنامه سوءاستفاده شود و سن یا جنسیت نادرست انتخاب "
            "گردد و در ادامه مشکلی — از جمله نمایش ایده‌های نامناسب برای سن واقعی کاربر — "
            "پیش بیاید، مسئولیت آن بر عهده‌ی خود کاربر است.\n\n"
            "همچنین در بخش انتخاب حافظه دقت کافی داشته باشید، زیرا در صورت پاک شدن ناگهانی "
            "یا غیرعمدی این حافظه، هیچ راه بازگشتی برای اکانت شما و جزئیات داخل آن وجود نخواهد داشت."
        )
        self.t_rules_body = fa(
            "تمامی ایده‌ها که برنامه‌ی لحظه‌ساز در اختیار شما قرار داده است، ایده‌هایی مناسب "
            "برای سنین متفاوت انتخاب شده‌اند و اگر در اجرای یکی از این ایده‌ها شخصی آسیب "
            "جسمانی یا روحی ببیند، مسئولیت آن با خود اوست و به سازنده و برنامه‌ی لحظه‌ساز "
            "ربطی ندارد.\n\n"
            "چنانچه در ساخت اکانت از شرایط برنامه سوءاستفاده شود و سن یا جنسیت نادرست انتخاب "
            "گردد و در ادامه مشکلی — از جمله نمایش ایده‌های نامناسب برای سن واقعی کاربر — "
            "پیش بیاید، مسئولیت آن بر عهده‌ی خود کاربر است.\n\n"
            "همچنین در بخش انتخاب حافظه دقت کافی داشته باشید، زیرا در صورت پاک شدن ناگهانی "
            "یا غیرعمدی این حافظه، هیچ راه بازگشتی برای اکانت شما و جزئیات داخل آن وجود نخواهد داشت."
        )
        self.t_rules_ok_btn = fa("قوانین را مطالعه کردم")

        # متن‌های راهنما (اختیاری)
        self.t_folder_login_link = fa("ورود با فولدر محل ذخیره اطلاعات")
        self.t_forgot_link = fa("فراموشی رمز عبور؟")
        self.t_forgot_title = fa("بازیابی رمز عبور")
        self.t_forgot_desc = fa(
            "«ریکاوری‌کی» یک کد ۲۴ کاراکتریِ یکتاست که هنگام ساخت اکانت برای تو ساخته شده "
            "و داخل فایل recovery_key.txt در همان پوشه‌ای ذخیره شده که موقع ساخت اکانت "
            "به‌عنوان محل ذخیره‌سازی انتخاب کردی.\n\n"
            "با وارد کردن این کد می‌تونی بدون نیاز به رمز قدیمی، رمز عبور اکانتت رو عوض کنی. "
            "کافیه فایل رو باز کنی، کد رو کپی کنی و در کادر زیر بذاری."
        )
        self.t_forgot_hint = fa("ریکاوری‌کی را اینجا وارد یا پیست کنید")
        self.t_forgot_check = fa("بررسی")
        self.t_forgot_newpw = fa("رمز جدید")
        self.t_forgot_submit = fa("ثبت")
        self.t_help_title = fa("راهنما")
        self.t_help_back_btn = fa("بازگشت")
        self.t_help_body_login = fa(
            "به صفحه‌ی ورود خوش اومدی.\n\n"
            "برای ورود کافیه نام کاربری و رمز عبوری که موقع ساخت اکانت انتخاب کردی رو "
            "وارد کنی، جنسیت و سن رو هم مثل همون موقع مشخص کنی و در نهایت روی دکمه‌ی «ورود» بزنی.\n\n"
            "اگه نام کاربری یا رمز رو فراموش کردی، می‌تونی از گزینه‌ی «ورود با فولدر محل ذخیره "
            "اطلاعات» (که دقیقاً زیر لینک ساخت اکانت قرار داره) استفاده کنی؛ کافیه همون پوشه‌ای "
            "که موقع ساخت اکانت به‌عنوان محل ذخیره انتخاب کرده بودی (یا پوشه‌ی به نام خودت داخلش) "
            "رو انتخاب کنی تا برنامه تو رو به‌طور خودکار وارد اکانتت کنه.\n\n"
            "استفاده از این راهنما کاملاً اختیاریه."
        )
        self.t_help_body_login_raw = (
            "به صفحه‌ی ورود خوش اومدی.\n\n"
            "برای ورود کافیه نام کاربری و رمز عبوری که موقع ساخت اکانت انتخاب کردی رو "
            "وارد کنی، جنسیت و سن رو هم مثل همون موقع مشخص کنی و در نهایت روی دکمه‌ی «ورود» بزنی.\n\n"
            "اگه نام کاربری یا رمز رو فراموش کردی، می‌تونی از گزینه‌ی «ورود با فولدر محل ذخیره "
            "اطلاعات» (که دقیقاً زیر لینک ساخت اکانت قرار داره) استفاده کنی؛ کافیه همون پوشه‌ای "
            "که موقع ساخت اکانت به‌عنوان محل ذخیره انتخاب کرده بودی (یا پوشه‌ی به نام خودت داخلش) "
            "رو انتخاب کنی تا برنامه تو رو به‌طور خودکار وارد اکانتت کنه.\n\n"
            "استفاده از این راهنما کاملاً اختیاریه."
        )
        self.t_help_body_signup = fa(
            "به صفحه‌ی ساخت اکانت خوش اومدی. اینجا می‌تونی برای اولین بار حسابت رو بسازی.\n\n"
            "• یک نام کاربری معتبر انتخاب کن (حداقل ۳ کاراکتر و بدون فاصله).\n"
            "• جنسیت و سنت رو انتخاب کن؛ ایده‌های نمایش‌داده‌شده بر اساس همین‌ها شخصی‌سازی می‌شن.\n"
            "• محل ذخیره‌سازی رو انتخاب کن؛ برنامه داخل همون مسیر یک پوشه‌ی اختصاصی به نام کاربری تو "
            "می‌سازه و اطلاعاتت رو اونجا نگه می‌داره. با همین پوشه بعداً می‌تونی از قابلیت «ورود با "
            "فولدر ذخیره‌سازی» هم استفاده کنی.\n"
            "• قبل از زدن دکمه‌ی ساخت اکانت، تیک «مطالعه‌ی قوانین» رو بزن.\n\n"
            "استفاده از این راهنما کاملاً اختیاریه."
        )
        self.t_help_body_signup_raw = (
            "به صفحه‌ی ساخت اکانت خوش اومدی. اینجا می‌تونی برای اولین بار حسابت رو بسازی.\n\n"
            "• یک نام کاربری معتبر انتخاب کن (حداقل ۳ کاراکتر و بدون فاصله).\n"
            "• جنسیت و سنت رو انتخاب کن؛ ایده‌های نمایش‌داده‌شده بر اساس همین‌ها شخصی‌سازی می‌شن.\n"
            "• محل ذخیره‌سازی رو انتخاب کن؛ برنامه داخل همون مسیر یک پوشه‌ی اختصاصی به نام کاربری تو "
            "می‌سازه و اطلاعاتت رو اونجا نگه می‌داره. با همین پوشه بعداً می‌تونی از قابلیت «ورود با "
            "فولدر ذخیره‌سازی» هم استفاده کنی.\n"
            "• قبل از زدن دکمه‌ی ساخت اکانت، تیک «مطالعه‌ی قوانین» رو بزن.\n\n"
            "استفاده از این راهنما کاملاً اختیاریه."
        )

        self.t_help_body_ideas = fa(
            "به صفحه‌ی ایده‌ها خوش اومدی. این راهنما مخصوصِ همین صفحه و کل مسیر دیت‌ساختن توئه.\n\n"
            "دکمه‌ی «راهنما» (همین علامت سؤالی که بالای صفحه می‌بینی) هر جای برنامه که ظاهر می‌شه، توضیحِ همون صفحه رو باز می‌کنه. در صفحه‌ی ورود و ساخت اکانت هم دقیقاً همین آیکون وجود داره و از اونجا به راهنمای مخصوصِ اون صفحه‌ها می‌رسی؛ پس اگه یه بار سؤالی داشتی، حتماً همون علامت سؤالِ بالای صفحه رو امتحان کن.\n\n"
            "در صفحه‌ی دسته‌بندی، آواتار پروفایل بالای صفحه، تصویرِ گردی است که با کلیک روش پنجره‌ی پروفایل باز می‌شه؛ اگه با همدم لینک شدی، دو تا آواتار کنار هم دیده می‌شن. داخل پنجره‌ی پروفایل، بالا سمت راست یه دکمه‌ی چرخشیِ کوچیک هست که تنظیمات رو باز می‌کنه (خروج، حذف اکانت، قطع همدم). پایین‌ترش دکمه‌ی «ویرایش پروفایل» قرار داده شده که تو رو به صفحه‌ای می‌بره برای تغییرِ سن، نام و نام خانوادگی و رمز عبور — نام کاربری و جنسیت در اون صفحه فقط برای نمایش هست و قابل ویرایش نیست. پایین‌تر هم دو دکمه‌ی «بازگشت» (برای بستن پنجره) و «همدم» (برای مدیریت لینک با همدم) هست.\n\n"
            "بخش «همدم» بهت اجازه می‌ده اکانتت رو به اکانتِ همدمِ خودت وصل کنی. برای ساختِ لینک، تو از منوی همدم یه کدِ لینکِ اختصاصی می‌سازی و به طرف مقابل می‌دی؛ اون طرف با وارد کردنِ همون کد، اکانتش به تو وصل می‌شه. توجه کن که سیستم فقط لینکِ یک دختر و یک پسر رو قبول می‌کنه؛ همدمِ هم‌جنس مجاز نیست. اگه دیگه نمی‌خوای همدم باشی، از منوی تنظیمات (همون دکمه‌ی چرخشیِ داخل پروفایل) می‌تونی گزینه‌ی «قطعِ همدم» یا «ترکِ اکانت مشترک» رو بزنی و مستقل بشی.\n\n"
            "در صفحه‌ی دسته‌بندی‌ها پنج دسته می‌بینی: «هیجانی و فعال» برای دیت‌های پرتحرک و ماجراجویانه، «خلاقانه و هنری» برای فعالیت‌های آرت و ساخت‌وساز، «سفره‌ی دو نفره» برای دیت‌های آشپزی و غذا، «طبیعت‌گردی» برای بیرون شهر و طبیعت، و «دیت‌های خانگی» برای وقت گذروندن داخل خونه (فقط برای بالای ۲۰ سال). با انتخاب هر دسته وارد صفحه‌ی ایده‌ها می‌شی و لیستِ کاملی از ایده‌ها با تگ سن، هزینه و زمان می‌بینی.\n\n"
            "در صفحه‌ی ایده‌ها بالا-چپ دکمه‌ی رندومِ تاس‌مانند رو می‌بینی؛ با زدنش کارت‌ها می‌چرخن و یه ایده به‌طور شانسی برات انتخاب می‌شه. کنارش دکمه‌ی بازگشت هست که تو رو به دسته‌بندی برمی‌گردونه. کلیک روی هر کارتِ ایده صفحه‌ی جزئیاتِ اون ایده رو باز می‌کنه؛ اونجا می‌تونی توضیحِ کاملِ ایده رو بخونی و یه عکس به‌عنوانِ خاطره‌ی این دیت ثبت کنی که همیشه به همون ایده گره خورده باقی می‌مونه.\n\n"
            "همه‌ی این راهنماها اختیاری هستن و برنامه بدونشون هم قابل استفاده‌ست."
        )
        self.t_help_body_ideas_raw = (
            "به صفحه‌ی ایده‌ها خوش اومدی. این راهنما مخصوصِ همین صفحه و کل مسیر دیت‌ساختن توئه.\n\n"
            "دکمه‌ی «راهنما» (همین علامت سؤالی که بالای صفحه می‌بینی) هر جای برنامه که ظاهر می‌شه، توضیحِ همون صفحه رو باز می‌کنه. در صفحه‌ی ورود و ساخت اکانت هم دقیقاً همین آیکون وجود داره و از اونجا به راهنمای مخصوصِ اون صفحه‌ها می‌رسی؛ پس اگه یه بار سؤالی داشتی، حتماً همون علامت سؤالِ بالای صفحه رو امتحان کن.\n\n"
            "در صفحه‌ی دسته‌بندی، آواتار پروفایل بالای صفحه، تصویرِ گردی است که با کلیک روش پنجره‌ی پروفایل باز می‌شه؛ اگه با همدم لینک شدی، دو تا آواتار کنار هم دیده می‌شن. داخل پنجره‌ی پروفایل، بالا سمت راست یه دکمه‌ی چرخشیِ کوچیک هست که تنظیمات رو باز می‌کنه (خروج، حذف اکانت، قطع همدم). پایین‌ترش دکمه‌ی «ویرایش پروفایل» قرار داده شده که تو رو به صفحه‌ای می‌بره برای تغییرِ سن، نام و نام خانوادگی و رمز عبور — نام کاربری و جنسیت در اون صفحه فقط برای نمایش هست و قابل ویرایش نیست. پایین‌تر هم دو دکمه‌ی «بازگشت» (برای بستن پنجره) و «همدم» (برای مدیریت لینک با همدم) هست.\n\n"
            "بخش «همدم» بهت اجازه می‌ده اکانتت رو به اکانتِ همدمِ خودت وصل کنی. برای ساختِ لینک، تو از منوی همدم یه کدِ لینکِ اختصاصی می‌سازی و به طرف مقابل می‌دی؛ اون طرف با وارد کردنِ همون کد، اکانتش به تو وصل می‌شه. توجه کن که سیستم فقط لینکِ یک دختر و یک پسر رو قبول می‌کنه؛ همدمِ هم‌جنس مجاز نیست. اگه دیگه نمی‌خوای همدم باشی، از منوی تنظیمات (همون دکمه‌ی چرخشیِ داخل پروفایل) می‌تونی گزینه‌ی «قطعِ همدم» یا «ترکِ اکانت مشترک» رو بزنی و مستقل بشی.\n\n"
            "در صفحه‌ی دسته‌بندی‌ها پنج دسته می‌بینی: «هیجانی و فعال» برای دیت‌های پرتحرک و ماجراجویانه، «خلاقانه و هنری» برای فعالیت‌های آرت و ساخت‌وساز، «سفره‌ی دو نفره» برای دیت‌های آشپزی و غذا، «طبیعت‌گردی» برای بیرون شهر و طبیعت، و «دیت‌های خانگی» برای وقت گذروندن داخل خونه (فقط برای بالای ۲۰ سال). با انتخاب هر دسته وارد صفحه‌ی ایده‌ها می‌شی و لیستِ کاملی از ایده‌ها با تگ سن، هزینه و زمان می‌بینی.\n\n"
            "در صفحه‌ی ایده‌ها بالا-چپ دکمه‌ی رندومِ تاس‌مانند رو می‌بینی؛ با زدنش کارت‌ها می‌چرخن و یه ایده به‌طور شانسی برات انتخاب می‌شه. کنارش دکمه‌ی بازگشت هست که تو رو به دسته‌بندی برمی‌گردونه. کلیک روی هر کارتِ ایده صفحه‌ی جزئیاتِ اون ایده رو باز می‌کنه؛ اونجا می‌تونی توضیحِ کاملِ ایده رو بخونی و یه عکس به‌عنوانِ خاطره‌ی این دیت ثبت کنی که همیشه به همون ایده گره خورده باقی می‌مونه.\n\n"
            "همه‌ی این راهنماها اختیاری هستن و برنامه بدونشون هم قابل استفاده‌ست."
        )

        Builder.load_string(KV + DIARY_KV + ADD_IDEA_KV + FORGOT_KV)
        sm = RootManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(SignupScreen(name="signup"))
        sm.add_widget(RulesScreen(name="rules"))
        sm.add_widget(HelpScreen(name="help"))
        sm.add_widget(ForgotPasswordScreen(name="forgot_password"))
        sm.add_widget(CategoriesScreen(name="categories"))
        sm.add_widget(IdeasScreen(name="ideas"))
        sm.add_widget(IdeaDetailScreen(name="idea_detail"))
        sm.add_widget(EditProfileScreen(name="edit_profile"))
        sm.add_widget(AddPersonalIdeaScreen(name="add_idea"))
        sm.add_widget(DiaryScreen(name="diary"))
        sm.add_widget(DiaryNoteScreen(name="diary_note"))
        return sm

    def neutral_color(self, key):
        return neutral(key, bool(self.dark_mode))

    def _apply_neutrals(self):
        """رنگ‌های خنثی (پس‌زمینه/متن/بوردر) را با حالت روشن/تیره هماهنگ می‌کند."""
        dark = bool(self.dark_mode)
        for key in ("surface", "surface_92", "surface_soft", "surface_glass",
                    "glass_grey", "glass_border", "text_primary", "text_secondary",
                    "text_body", "text_strong", "text_hint", "border", "divider",
                    "paper", "paper_line", "paper_text", "paper_sub"):
            try:
                setattr(self, "theme_" + key, list(neutral(key, dark)))
            except Exception:
                pass

    def refresh_neutral_widgets(self, *a):
        """ویجت‌هایی که با پایتون/canvas ساخته شده‌اند را با تمِ فعلی رفرش می‌کند."""
        def _walk(w):
            fn = getattr(w, "_refresh_theme", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
            for c in list(getattr(w, "children", []) or []):
                _walk(c)
        try:
            for w in list(Window.children):
                _walk(w)
        except Exception:
            pass

    def on_dark_mode(self, *a):
        self._apply_neutrals()
        Clock.schedule_once(lambda dt: self.refresh_neutral_widgets(), 0)

    def set_theme(self, gender: str):
        dark = bool(self.dark_mode)
        self._apply_neutrals()
        if gender == "male":
            target = THEME_BLUE_DARK if dark else THEME_BLUE
        elif gender == "female":
            target = THEME_PINK_DARK if dark else THEME_PINK
        else:
            target = THEME_BLACK if dark else THEME_WHITE
        if target is self.current_theme:
            self._refresh_avatars()
            Clock.schedule_once(lambda dt: self.refresh_neutral_widgets(), 0)
            return
        self.current_theme = target
        if self._theme_anim:
            self._theme_anim.stop(self)
        anim = Animation(
            theme_bg=list(target["bg"]),
            theme_accent=list(target["accent"]),
            theme_accent_soft=list(target["accent_soft"]),
            theme_card_border=list(target["card_border"]),
            theme_title=list(target["title"]),
            theme_input_bg=list(target["input_bg"]),
            theme_bubble1=list(target["bubble1"]),
            theme_bubble2=list(target["bubble2"]),
            theme_cat_sub=list(target["cat_sub"]),
            duration=0.45, t="in_out_quad",
        )
        self._theme_anim = anim
        anim.start(self)
        Clock.schedule_once(lambda dt: setattr(Window, "clearcolor", target["window_bg"]), 0.22)
        # رنگ دکمه‌های جنسیت باید با تمِ جدید هماهنگ شود — هم فوراً و هم پس از
        # اعمال کاملِ انیمیشنِ تم.
        self._refresh_avatars()
        Clock.schedule_once(lambda dt: self._refresh_avatars(), 0)
        Clock.schedule_once(lambda dt: self._refresh_avatars(), 0.5)
        # رفرشِ ویجت‌های پایتونی (پاپ‌آپ‌ها/کارت‌ها) تا رنگ‌های خنثی فوراً عوض شوند
        self.refresh_neutral_widgets()
        Clock.schedule_once(lambda dt: self.refresh_neutral_widgets(), 0)
        Clock.schedule_once(lambda dt: self.refresh_neutral_widgets(), 0.5)

    def _refresh_avatars(self):
        for scr in ("login", "signup"):
            try:
                s = self.root.get_screen(scr)
                s.ids.form.male_btn._draw_bg()
                s.ids.form.female_btn._draw_bg()
            except Exception:
                pass
        try:
            cats = self.root.get_screen("categories")
            if hasattr(cats, "_profile_refs"):
                for b in cats._profile_refs:
                    b._draw_ring()
        except Exception:
            pass


if __name__ == "__main__":
    LahzeSazApp().run()

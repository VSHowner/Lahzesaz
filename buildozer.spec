[app]

# (str) عنوان برنامه — همانی که زیر آیکون روی گوشی نمایش داده می‌شود
title = لحظه‌ساز

# (str) نام پکیج — فقط حروف کوچک انگلیسی، عدد و آندرلاین (بدون فاصله)
package.name = lahzesaz

# (str) دامنه‌ی پکیج به‌صورت معکوس (com.yourname.appname)
package.domain = com.lahzesaz

# (str) پوشه‌ی سورس؛ همان جایی که main.py قرار دارد
source.dir = .

# (str) فایل اصلی اجرای برنامه
source.main = main.py

# (list) پسوندهایی که باید داخل پکیج نهایی قرار بگیرند
# .py برای کد، .kv برای فایل‌های Kv جداگانه (اگر داشتید)،
# .png/.jpg برای assets و لوگو، .ttf برای فونت‌های فارسی (Vazirmatn / BHoma)، .json برای دیتای احتمالی
source.include_exts = py,png,jpg,jpeg,ttf,otf,kv,json,atlas

# (list) پوشه‌هایی که علاوه بر کد باید کامل کپی شوند
# assets  -> آیکون‌های UI
# fonts   -> فونت‌های فارسی
# logo    -> لوگوی اصلی برنامه (هم برای آیکون، هم اگر داخل UI استفاده شود)
source.include_patterns = assets/*,assets/**/*,fonts/*,fonts/**/*,logo/*,logo/**/*

# (list) پوشه‌ها/فایل‌هایی که باید از پکیج نهایی حذف شوند
source.exclude_dirs = tests, bin, venv, __pycache__, .git, .buildozer, .github

# (str) شماره نسخه‌ی برنامه
version = 1.0

# (list) نیازمندی‌های پایتون/کتابخانه‌ای برنامه.
# python3==3.11  -> نسخه‌ی پایتون به‌صورت صریح قفل شده تا p4a خودش
#                   جدیدترین ریسیپی را انتخاب نکند (build تکرارپذیر شود).
#                   این نسخه با تگ پین‌شده‌ی p4a پایین‌تر سازگار است.
#   kivy==2.3.0        -> فریم‌ورک اصلی
#   arabic_reshaper==3.0.0 -> بازچینی حروف فارسی/عربی (fa()). پین شده چون
#                   نسخه‌های آزاد ممکنه رفتار/ساختار متفاوتی داشته باشن.
#   python-bidi==0.4.2 -> راست‌به‌چپ کردن متن (get_display). این نسخه دقیقاً
#                   با importِ فعلی کد (`from bidi.algorithm import get_display`)
#                   سازگاره. نسخه‌های جدیدتر (0.5+) بازنویسی بزرگی داشتن و
#                   ساختار ماژول عوض شده؛ اگه پین نشه، ممکنه روی دستگاه
#                   ImportError بخوره و بی‌صدا (طبق try/except خودِ main.py)
#                   غیرفعال بشه — که دقیقاً باعث می‌شه متن فارسی چسبیده و
#                   راست‌به‌چپ نشه (علامتی که قبلاً دیدی).
#   requests         -> آپلود عکس پروفایل (upload_avatar)
#   plyer            -> دوربین و فایل‌چوزر (camera, filechooser)
#   pyjnius          -> دسترسی به API اندروید (device id، SAF، ...)
#   openssl          -> پشتیبانی https برای requests
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,arabic_reshaper==3.0.0,python-bidi==0.4.2,requests,plyer,pyjnius,openssl

# (str) آیکون برنامه — لوگوی اصلی پروژه
icon.filename = %(source.dir)s/logo/logo.png

# (str) تصویر پرسپلش (صفحه‌ی بارگذاری اولیه‌ی نیتیو، قبل از بوت‌شدن کامل پایتون)
# به‌جای لوگوی پیش‌فرض کیوی (پرنده + "Loading...")، از لوگوی خودمان استفاده می‌شود
# تا کاربر یک صفحه‌ی برند‌شده ببیند، نه صفحه‌ی جنریک p4a.
presplash.filename = %(source.dir)s/logo/logo.png

# (str) رنگ پس‌زمینه‌ی پرسپلش — دقیقاً برابر با Window.clearcolor تنظیم‌شده در main.py
# (0.97, 0.97, 0.98, 1) => #F7F7FA
# این هماهنگی باعث می‌شود گذار از پرسپلش نیتیو به اولین فریم Kivy کاملاً یکدست
# و بدون پرش/فلش دیده شود (پرش معمولاً وقتی حس می‌شود که رنگ پس‌زمینه فرق کند).
android.presplash_color = #F7F7FA

# (str) جهت صفحه: portrait / landscape / all
orientation = portrait

# (bool) فول‌اسکرین یا نه
fullscreen = 0

# (list) فونت‌های فارسی به‌عنوان دیتا اضافه می‌شوند (fonts/Vazirmatn-Regular.ttf, fonts/BHoma.ttf)
# از طریق source.include_patterns بالا هم پوشش داده می‌شوند؛ این خط برای اطمینان بیشتر است.
android.add_assets = fonts

# -----------------------------------------------------------------------
# تنظیمات اندروید
# -----------------------------------------------------------------------

# (int) حداقل نسخه‌ی API اندروید که برنامه روی آن نصب می‌شود
android.minapi = 21

# (int) نسخه‌ی API هدف (باید با آخرین نیازمندی‌های گوگل‌پلی هماهنگ باشد)
android.api = 34

# (str) نسخه‌ی NDK اندروید
android.ndk = 25c

# (list) مجوزهای اندروید مورد نیاز برنامه
#   INTERNET                -> آپلود عکس پروفایل (requests)
#   CAMERA                  -> گرفتن عکس با دوربین (plyer.camera)
#   READ_EXTERNAL_STORAGE / WRITE_EXTERNAL_STORAGE -> خواندن/نوشتن عکس‌ها و دیتابیس JSON (اندرویدهای قدیمی‌تر)
#   READ_MEDIA_IMAGES       -> دسترسی به گالری در اندروید 13+
android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES

# (str) معماری‌های هدف برای build (هر دو معماری رایج امروزی)
android.archs = arm64-v8a,armeabi-v7a

# (bool) قبول خودکار لایسنس‌های Android SDK هنگام build
android.accept_sdk_license = True

# (str) نام کلاس اصلی جاوا/پایتون اکتیویتی (پیش‌فرض خوب است، تغییر ندهید)
# android.entrypoint = org.kivy.android.PythonActivity

# (bool) اجازه‌ی بک‌آپ خودکار توسط اندروید
android.allow_backup = True

# -----------------------------------------------------------------------
# تنظیمات python-for-android
# -----------------------------------------------------------------------

# (str) به‌جای شاخه‌ی ناپایدار master، یک تگ پایدار و پین‌شده استفاده می‌شود.
# تگ v2024.01.21 آخرین ریلیزی است که با kivy 2.3.0 و ریسیپی python3 نسخه‌ی 3.11
# و NDK 25b تست شده است. اگر بعداً خواستید ارتقا دهید، فقط همین یک خط را عوض کنید.
p4a.branch = v2024.01.21

# (bool) استفاده از حالت release به‌جای debug (برای انتشار نهایی این را True کنید
# و کلید امضا را هم تنظیم کنید)
# android.release = False

# -----------------------------------------------------------------------
# تنظیمات عمومی buildozer
# -----------------------------------------------------------------------

[buildozer]

# (int) سطح لاگ: 0 = خطا، 1 = اطلاعات، 2 = دیباگ (خیلی وربوز)
log_level = 2

# (int) اگر buildozer به‌عنوان root اجرا شود هشدار ندهد (فقط برای CI/کانتینر توصیه می‌شود)
warn_on_root = 1

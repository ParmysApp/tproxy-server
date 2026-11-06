# نصب پنل Telegram WEB Proxy

این فورک شامل تغییرات لازم در relay است؛ patch جداگانه لازم نیست. نصب‌کنندهٔ یک‌مرحله‌ای پیش از تغییر سیستم بررسی می‌کند پورت‌های 80 و 443 آزاد باشند و سرویس x-ui فعال نباشد. اگر پورت‌ها درگیر باشند، نصب را متوقف می‌کند تا تنظیم سرویس دیگر را خراب نکند.

## پیش‌نیاز

- Ubuntu 22.04+ یا Debian 12+، معماری x86_64
- سرور اختصاصی برای این سرویس؛ TCP پورت‌های 80 و 443 آزاد
- دامنه‌ای که A record آن به IP همین سرور اشاره می‌کند
- یک وب‌سایت واقعی/متعلق به خودت که پوشه‌اش `index.html` داشته باشد
- دسترسی root

نصب پایهٔ upstream جایگزین تنظیم فعال Caddy می‌شود؛ این روش را روی سروری که سایت یا پنل دیگری دارد اجرا نکن. اسکریپت ایمنی، پورت‌های درگیر را تشخیص می‌دهد و متوقف می‌شود.

## نصب

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/USERNAME/tproxy-server.git /opt/tproxy-server
mkdir -p /root/my-site
nano /root/my-site/index.html
cd /opt/tproxy-server
sudo bash install.sh --hostname proxy.example.com --email you@example.com --site-dir /root/my-site
```

`USERNAME`، دامنه و ایمیل را عوض کن. صفحهٔ سایت باید متعلق به خودت باشد؛ از محتوای یکسان و عمومی برای همهٔ نصب‌ها استفاده نکن. هنگام نصب secret را تولید/وارد کن و برای استفاده در تلگرام نگه دار. نصب‌کنندهٔ پنل گذرواژه را در خروجی نشان می‌دهد.

## دسترسی امن به پنل

پنل فقط روی localhost گوش می‌دهد. از رایانهٔ خودت تونل SSH بساز:

```bash
ssh -L 8765:127.0.0.1:8765 root@SERVER_IP
```

مرورگر را روی `http://127.0.0.1:8765` باز کن و گذرواژهٔ نصب را وارد کن.

## سرویس‌ها

```bash
sudo systemctl status webproxy-panel mtproxy tproxy-server tproxy-firewall
sudo journalctl -u webproxy-panel -f
```

فایل‌های `/etc/tproxy-panel/proxies.json` و `/etc/tproxy-panel/panel.env` محرمانه‌اند؛ آن‌ها را commit یا منتشر نکن.
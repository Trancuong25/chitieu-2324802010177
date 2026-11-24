# Quản lý chi tiêu cá nhân · 2324802010177 · Trần Minh Cường

Flask/Jinja2 + PostgreSQL. Gunicorn chỉ nghe `127.0.0.1:8000`, Nginx công bố cổng 80, chạy trong mạng ảo nội bộ.

## Chức năng
- Đăng ký, đăng nhập, đăng xuất (mật khẩu băm Werkzeug, form POST có CSRF token, SQL dùng tham số).
- Thêm, sửa, xóa, xem khoản chi của riêng mình; có tổng chi tháng này và theo danh mục.

## Cài lại từ đầu trên VPS (Ubuntu 24.04)
Thay `192.168.X.0/24` bằng dải mạng ảo của bạn.

### 1. Gói và mã nguồn
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip postgresql nginx ufw git
sudo git clone <LINK_REPO> /opt/chitieu
sudo chown -R cuongadmin:cuongadmin /opt/chitieu
cd /opt/chitieu
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. CSDL và user riêng
```bash
openssl rand -hex 24          # lưu lại làm mật khẩu CSDL
sudo -u postgres psql
```
```sql
CREATE ROLE expense_app LOGIN PASSWORD 'MAT_KHAU_VUA_TAO';
CREATE DATABASE expense_db OWNER expense_app;
\q
```
```bash
cp .env.example .env
openssl rand -hex 32          # dán vào SECRET_KEY
nano .env                     # điền SECRET_KEY và mật khẩu DB (STUDENT_ID đã có sẵn)
chmod 600 .env
set -a; source .env; set +a
psql "$DATABASE_URL" -f schema.sql
unset DATABASE_URL SECRET_KEY
```

### 3. systemd và Nginx
```bash
sed -i 's/cuongadmin/cuongadmin/' deploy/expense.service
sudo cp deploy/expense.service /etc/systemd/system/
sudo cp deploy/nginx-chitieu.conf /etc/nginx/sites-available/chitieu
sudo ln -s /etc/nginx/sites-available/chitieu /etc/nginx/sites-enabled/chitieu
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now expense
sudo nginx -t && sudo systemctl reload nginx
systemctl is-active expense nginx postgresql
```

### 4. ufw (chạy đúng thứ tự, giữ sẵn một phiên SSH)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.X.0/24 to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw enable
sudo ufw status verbose
sudo ss -tlnp
```

### 5. Kiểm tra
Mở `http://<IP VPS>` trên laptop: đăng ký → đăng nhập → thêm → sửa → xóa. Chạy `sudo reboot` và kiểm tra app tự chạy lại.

## AI và nguồn
AI hỗ trợ sinh mã mẫu và lệnh triển khai; người thực hiện tự kiểm tra và giải thích từng tệp.
Nguồn: docs của Flask, Werkzeug, PostgreSQL, Gunicorn, Ubuntu (Nginx, UFW).

# 📋 Hướng Dẫn Sử Dụng & Phát Triển VNSTOCK Dashboard

## 🔗 Thông tin dự án

| Thông tin | Nội dung |
|---|---|
| 📁 Thư mục dự án | `c:\Users\DTGK\Desktop\BTHANH\stock_dashboard` |
| 🌐 Local URL | http://localhost:8000 |
| ☁️ Render URL | https://vnstock-thanhdata.onrender.com |
| 🐙 GitHub Repo | https://github.com/bthanhdang96-source/vnstock-thanhdata |

---

## 🚀 Mỗi khi mở Antigravity — Làm theo thứ tự này

### Bước 1: Mở Terminal trong VS Code
Ấn **Ctrl + ` ** (backtick) hoặc vào menu `Terminal → New Terminal`

### Bước 2: Chạy server local
Copy-paste lệnh này vào Terminal và ấn Enter:

```bash
cd c:\Users\DTGK\Desktop\BTHANH\stock_dashboard
..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --host 0.0.0.0 --reload
```

✅ Server chạy thành công khi thấy:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Bước 3: Mở trình duyệt
Truy cập **http://localhost:8000** để xem Dashboard đang chạy.

---

## 📊 Mỗi khi muốn cập nhật dữ liệu mới nhất

### Cách 1: Sync trên máy local (Khuyến nghị)
1. Vào http://localhost:8000
2. Bấm nút **"Sync Historical Data"** — chờ thanh tiến trình hoàn tất
3. Sau khi xong, commit và đẩy lên GitHub + Render:

```bash
git add cache_hose_data.json
git commit -m "Update: Refresh market data"
git push
```

4. Render tự động deploy trong ~2 phút, vào https://vnstock-thanhdata.onrender.com để kiểm tra.

---

## 💻 Khi chỉnh sửa code và muốn đẩy lên GitHub/Render

```bash
git add .
git commit -m "Mô tả ngắn về thay đổi"
git push
```

> Render sẽ **tự động redeploy** sau khi nhận được commit mới (~2-3 phút).

---

## 🗂️ Cấu trúc thư mục dự án

```
stock_dashboard/
├── main.py                   # Backend FastAPI (server, API, sync logic)
├── requirements.txt          # Danh sách thư viện Python
├── cache_hose_data.json      # Cache dữ liệu thị trường (commit lên GitHub)
├── .gitignore                # Danh sách file không đẩy lên GitHub
├── static/
│   ├── index.html            # Giao diện chính
│   ├── style.css             # Toàn bộ styles (Bento 2.0 / Zinc Dark)
│   └── app.js                # Logic frontend (D3.js heatmap, API calls)
└── data/
    └── history/              # Cache CSV từng mã cổ phiếu (KHÔNG lên GitHub)
        ├── VCB.csv
        ├── FPT.csv
        └── ...
```

---

## 🛠️ Xử lý lỗi thường gặp

### ❌ Lỗi: Port 8000 đang được dùng
```bash
# Tắt toàn bộ Python đang chạy rồi start lại
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --host 0.0.0.0 --reload
```

### ❌ Lỗi: "Chưa có dữ liệu, vui lòng Sync"
→ Bấm nút **Sync Historical Data** trên Dashboard và chờ hoàn tất.

### ❌ Render deploy OK nhưng không có data
→ Chạy Sync trên máy local xong, commit và push `cache_hose_data.json`:
```bash
git add cache_hose_data.json ; git commit -m "Update cache" ; git push
```

### ❌ Git báo "Author identity unknown"
```bash
git config user.email "bthanhdang96@users.noreply.github.com"
git config user.name "BThanhDang"
```

---

## 📐 Quy tắc thiết kế giao diện (Bento 2.0)

Mọi thay đổi UI cần tuân thủ:
- **Nền**: `Zinc-950` (off-black `#0a0a0b`)
- **Font chữ**: `Geist Sans` (text) / `Geist Mono` (số liệu)
- **Card container**: "Liquid Glass Panel" — viền mờ `1px`, backdrop blur
- **Màu Tăng/Giảm**: Xanh lá pastel / Đỏ pastel (không dùng neon chói)
- **Heatmap neutral**: `Zinc-700` (`#3f3f46`) cho mã đứng giá

---

## 📌 Các tính năng đã hoàn thiện

| Tính năng | Mô tả |
|---|---|
| ✅ Heatmap Thị trường | Có 2 chế độ: Cổ phiếu / Ngành; Timeframe: 1D/1W/1M/1Q/1Y |
| ✅ Top Tăng/Giảm | Lọc đúng HOSE (không có UPCOM/HNX) |
| ✅ Bộ lọc Tiềm năng | RSI ≤ 35 + StochK ≤ 20 (Quá bán) hoặc Uptrend (Giá > MA100 & MA50 > MA100) |
| ✅ Incremental Sync | Chỉ tải ngày còn thiếu, tiết kiệm API |
| ✅ Deploy Render | Tự động deploy khi push GitHub |

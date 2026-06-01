# 活動管理與權限系統

FastAPI + Jinja2 + MongoDB Atlas 的活動管理網站，支援三種角色、活動報名、全站/活動聊天室與管理員後台。

## 功能

- **一般使用者**：註冊登入、瀏覽進行中活動、選位置報名、聊天
- **高級使用者**：建立/編輯活動、設定位置人數、上傳圖片、啟動/關閉活動
- **管理員**：調整使用者權限、篩選歷史活動

## 環境設定

1. 建立並啟用虛擬環境（Windows PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 複製 `.env.example` 為 `.env` 並填入 MongoDB 連線資訊
3. 安裝依賴：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. 啟動：

```powershell
.\run.ps1
# 或
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

5. 開啟 http://127.0.0.1:8000

首次啟動會依 `.env` 建立 bootstrap 管理員（預設 `admin@example.com` / `admin123456`）。

## 角色說明

| 角色 | 代碼 |
|------|------|
| 一般使用者 | `user` |
| 高級使用者 | `advanced_user` |
| 管理員 | `admin` |

管理員可在 `/admin/users` 調整其他使用者角色。

## 部署到 Render

**Exit 127** 通常是啟動指令錯誤（例如用了 Windows 的 `run.ps1`，或 Render 預設的 `gunicorn` 但專案未安裝）。

在 Render Dashboard → 你的 Web Service → **Settings** 設定：

| 項目 | 值 |
|------|-----|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

**Environment Variables**（必填）：

- `MONGODB_URI` — MongoDB Atlas 連線字串
- `MONGODB_DB_NAME` — `activity_app`
- `SECRET_KEY` — 隨機長字串
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` — 首位管理員

也可直接使用本 repo 的 [`render.yaml`](render.yaml) 建立服務。

> Render 為 Linux 環境，請勿使用 `run.ps1` 或 `.venv\Scripts\python.exe` 作為啟動指令。

## 目錄結構

- `app/main.py` — 應用入口
- `app/routers/` — 路由（auth、activities、admin、chat）
- `app/services/` — 業務邏輯
- `app/templates/` — Jinja2 模板
- `app/static/` — 靜態資源與上傳圖片

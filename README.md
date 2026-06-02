# 活動管理與權限系統

FastAPI + Jinja2 + MongoDB Atlas 的活動管理網站，支援三種角色、活動報名、全站/活動聊天室與管理員後台。

## 功能

- **一般使用者**：註冊登入（需 Email 驗證碼）、瀏覽進行中活動、選位置報名、聊天
- **高級使用者**：建立/編輯活動、設定位置人數、上傳圖片、啟動/關閉活動
- **管理員**：調整使用者權限、設為管理員、刪除使用者、代為確認 Email 驗證、篩選歷史活動

## 環境設定

1. 建立並啟用虛擬環境（Windows PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 複製 `.env.example` 為 `.env` 並填入 MongoDB 連線資訊與 SMTP 設定（註冊驗證碼寄信）
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

管理員可在 `/admin/users` 調整其他使用者角色、設為管理員、刪除使用者，或代為確認尚未驗證 Email 的帳號。操作前會跳出確認提示，完成後頁面頂部會顯示成功或失敗訊息。

## Email 驗證

註冊後系統會寄出 6 位數驗證碼，使用者須在 `/register/verify` 輸入後才能登入。若未設定任何寄信方式，驗證碼會寫入伺服器 log（僅供本機開發）。

### 本機開發（Gmail SMTP）

| 環境變數 | 說明 |
|---------|------|
| `SMTP_HOST` | SMTP 主機（Gmail：`smtp.gmail.com`） |
| `SMTP_PORT` | 埠號（Gmail：`587`，使用 STARTTLS） |
| `SMTP_USER` | Gmail 完整信箱 |
| `SMTP_PASSWORD` | Gmail [應用程式密碼](https://myaccount.google.com/apppasswords)（16 碼，可含空格） |
| `SMTP_FROM` | 寄件者顯示名稱（建議與 `SMTP_USER` 相同信箱） |

### Render 部署（Resend API，免費方案必用）

Render **免費方案**自 2025 年 9 月起封鎖 SMTP 埠 25/465/587，Gmail SMTP 無法連線。請改用 [Resend](https://resend.com) 的 HTTPS API（走 443 埠，不受限制）：

1. 至 [Resend](https://resend.com) 註冊並建立 API Key
2. 在 Resend 驗證寄件網域，或測試階段使用 `onboarding@resend.dev`
3. 在 Render Dashboard → Environment 設定：

| 環境變數 | 說明 |
|---------|------|
| `RESEND_API_KEY` | Resend API Key（`re_...`） |
| `EMAIL_FROM` | 寄件者，例如 `活動管理系統 <onboarding@resend.dev>` |

> 若設定了 `RESEND_API_KEY`，系統優先使用 Resend，不再走 SMTP。

| 環境變數 | 說明 |
|---------|------|
| `VERIFICATION_CODE_EXPIRE_MINUTES` | 驗證碼有效分鐘數（預設 15） |

## 部署到 Render

**Exit 127** 通常是啟動指令錯誤（例如用了 Windows 的 `run.ps1`，或 Render 預設的 `gunicorn` 但專案未安裝）。

在 Render Dashboard → 你的 Web Service → **Settings** 設定：

| 項目 | 值 |
|------|-----|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/health` |

**Environment Variables**（必填）：

- `MONGODB_URI` — MongoDB Atlas 連線字串
- `MONGODB_DB_NAME` — `activity_app`
- `SECRET_KEY` — 隨機長字串
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` — 首位管理員
- `RESEND_API_KEY` / `EMAIL_FROM` — 驗證信寄送（Render 免費方案必設，見上方 Email 驗證）

也可直接使用本 repo 的 [`render.yaml`](render.yaml) 建立服務。

> Render 為 Linux 環境，請勿使用 `run.ps1` 或 `.venv\Scripts\python.exe` 作為啟動指令。

## 目錄結構

- `app/main.py` — 應用入口
- `app/routers/` — 路由（auth、activities、admin、chat）
- `app/services/` — 業務邏輯
- `app/templates/` — Jinja2 模板
- `app/static/` — 靜態資源與上傳圖片

# Deploy lên Vercel + Railway (FREE tier)

> Mục tiêu: deploy thử nghiệm miễn phí để bạn bè truy cập test.
> Stack: **Vercel** (Next.js frontend) + **Railway** (FastAPI backend + PostgreSQL + Redis).

> **Miễn phí theo ý nghĩa "thử nghiệm"**:
> - Vercel Hobby: 0 USD/tháng, miễn phí vĩnh viễn cho cá nhân.
> - Railway: cấp $5 credit mỗi tháng, đủ chạy 1 service nhỏ + 1 Postgres + 1 Redis (~30 ngày).
> Nếu bạn bè dùng nhiều có thể cạn credit — khi đó cần upgrade hoặc chuyển sang Render/Fly.io.

---

## 0. Chuẩn bị tài khoản (làm thủ công, 1 lần)

| Dịch vụ      | URL                          | Cần làm                              |
|--------------|------------------------------|--------------------------------------|
| GitHub       | <https://github.com>         | Tạo repo mới (để trống, không tạo README/license) |
| Railway      | <https://railway.app>        | Sign in bằng GitHub                  |
| Vercel       | <https://vercel.com>         | Sign in bằng GitHub                  |

---

## 1. Push code lên GitHub (làm thủ công)

1. Tạo repo mới trên GitHub, ví dụ `smart-project-manager` (visibility: **Public** hoặc **Private** đều được).
2. Trên máy local, trong thư mục gốc project:

   ```bash
   cd smart-project-manager
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/smart-project-manager.git
   git push -u origin main
   ```

> Nếu chưa cài Git: tải từ <https://git-scm.com/download/win> hoặc dùng **GitHub Desktop** (<https://desktop.github.com>).

---

## 2. Tạo project Railway

1. Vào <https://railway.app/new>.
2. Chọn **Deploy from GitHub repo** → chọn repo `smart-project-manager` bạn vừa push.
3. Khi Railway hỏn **Root Directory**, để mặc định trước (sẽ chỉnh ở bước 4).

### 2.1. Add PostgreSQL

- Trong project Railway, bấm **+ New** → **Database** → **PostgreSQL**.
- Sau khi tạo xong, bấm vào service Postgres → tab **Variables** → copy giá trị `DATABASE_URL`.
  - Railway tự động share biến này cho mọi service trong cùng project dưới tên `DATABASE_URL` (Postgres plugin), nên thường **không cần copy thủ công**.

### 2.2. Add Redis

- Tương tự: **+ New** → **Database** → **Redis**.
- Biến `REDIS_URL` được inject tự động cho cùng project.

### 2.3. Tạo service backend

1. **+ New** → **GitHub Repo** → chọn lại repo `smart-project-manager`.
2. Bấm vào service mới tạo → tab **Settings**:
   - **Root Directory**: `backend`
   - **Watch Paths**: `backend/**`  *(để không redeploy khi frontend đổi)*
3. Tab **Variables** → thêm các biến sau:

   | Biến                          | Giá trị                                                                 |
   |------------------------------|-------------------------------------------------------------------------|
   | `DATABASE_URL`               | *(Postgres plugin tự inject, hoặc copy từ Postgres service)*            |
   | `REDIS_URL`                  | *(Redis plugin tự inject, hoặc copy từ Redis service)*                  |
   | `JWT_SECRET_KEY`             | *(generate: `python -c "import secrets;print(secrets.token_urlsafe(64))"`)* |
   | `CORS_ORIGINS`               | `https://<your-app>.vercel.app` *(điền sau khi deploy frontend)*         |
   | `PUBLIC_BASE_URL`            | `https://<your-service>.up.railway.app`                                 |
   | `DEBUG`                      | `false`                                                                 |
   | `USE_CELERY`                 | `false` *(nếu không dùng background job)*                               |
   | `SENTRY_DSN`                 | *(để trống hoặc DSN thật nếu có)*                                       |
   | `SENTRY_ENV`                 | `production`                                                            |
   | `ANTHROPIC_API_KEY`          | *(để trống nếu chưa có; sẽ dùng stub fallback)*                         |
   | `OPENAI_API_KEY`             | *(để trống nếu chưa có)*                                                |
   | `RATE_LIMIT_ENABLED`         | `true`                                                                  |
   | `PORT`                       | Railway tự set, **không cần thêm**                                       |

4. Tab **Deploy** → bấm **Deploy** (hoặc push code mới sẽ tự trigger).

> Khi deploy thành công, Railway sẽ cấp URL dạng `https://<service-name>.up.railway.app`.
> Truy cập `https://<service-name>.up.railway.app/docs` để xem API docs.

### 2.4. Chạy migration + seed (QUAN TRỌNG)

Sau khi backend deploy lần đầu, cần tạo schema trong Postgres:

1. Trong service backend, tab **Settings** → **Deploy** → **Custom Start Command** tạm thời đổi thành:

   ```
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

2. Bấm **Redeploy**. Xem log đến khi thấy `Running upgrade ...` → nghĩa là schema đã tạo xong.

3. **(Tùy chọn) Seed data mẫu**: thêm Custom Start Command:

   ```
   alembic upgrade head && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. Sau khi migration xong, **đổi lại Custom Start Command về**:

   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

   (Hoặc xóa Custom Start Command để dùng `startCommand` trong `railway.toml`.)

> **Cách khác (nhanh hơn, không cần đổi start command)**: dùng Railway CLI:
> ```bash
> npm i -g @railway/cli
> railway login
> railway run alembic upgrade head
> railway run python seed.py
> ```

---

## 3. Deploy Frontend lên Vercel

1. Vào <https://vercel.com/new>.
2. **Import** repo `smart-project-manager`.
3. Khi Vercel hỏi **Root Directory**, bấm **Edit** → chọn `frontend`.
4. **Framework Preset** tự nhận là **Next.js** — để nguyên.
5. Mở **Environment Variables**, thêm:

   | Biến                      | Giá trị (production)                                          |
   |--------------------------|--------------------------------------------------------------|
   | `NEXT_PUBLIC_API_URL`   | `https://<service-name>.up.railway.app`                       |
   | `NEXT_PUBLIC_WS_URL`    | `wss://<service-name>.up.railway.app`                         |
   | `NEXTAUTH_URL`          | `https://<your-app>.vercel.app`                               |
   | `NEXTAUTH_SECRET`       | *(generate: `openssl rand -base64 32`)*                       |
   | `NEXT_PUBLIC_SENTRY_DSN`| *(để trống nếu chưa có)*                                     |

6. Bấm **Deploy**. Vercel sẽ build và cấp URL dạng `https://<your-app>.vercel.app`.

---

## 4. Kết nối 2 phía: CORS

Sau khi có URL frontend (`https://<your-app>.vercel.app`):

1. Quay lại Railway → service backend → **Variables**.
2. Sửa `CORS_ORIGINS` thành:

   ```
   https://<your-app>.vercel.app
   ```

3. Bấm **Redeploy** để áp dụng.

4. Nếu dùng Vercel preview deployments (mỗi PR có URL riêng), thêm vào:

   ```
   https://<your-app>.vercel.app,https://*-<your-team>.vercel.app
   ```

---

## 5. Kiểm tra cuối cùng

| Bước | URL cần mở | Kỳ vọng |
|------|-----------|---------|
| 1 | `https://<service>.up.railway.app/health` | Trả về `{"status":"healthy"}` |
| 2 | `https://<service>.up.railway.app/docs` | Thấy Swagger UI |
| 3 | `https://<your-app>.vercel.app` | Trang login hiện ra, không có lỗi CORS trong DevTools |
| 4 | Đăng ký tài khoản mới trên Vercel app | Hoạt động → ghi vào Postgres |

---

## 6. Cập nhật code sau này

```bash
# Sửa code trên local
git add .
git commit -m "feat: ..."
git push origin main
```

- **Vercel** auto-deploy mỗi lần push vào `main`.
- **Railway** cũng auto-deploy (xem tab **Deploys** trong service).

Để rollback: trong Railway hoặc Vercel → tab **Deployments** → bấm **⋯** trên bản cũ → **Redeploy**.

---

## 7. Troubleshooting

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-----------|----------|
| 500 ngay khi mở app | `alembic upgrade head` chưa chạy | Xem mục 2.4 |
| CORS error trong console | Sai `CORS_ORIGINS` | Đặt đúng URL Vercel, **không có dấu `/` ở cuối** |
| Frontend gọi API 404 | Sai `NEXT_PUBLIC_API_URL` | Kiểm tra lại biến, **redeploy** (Vercel cache build) |
| `WebSocket connection failed` | Sai `NEXT_PUBLIC_WS_URL` | Phải dùng `wss://` (không phải `ws://`) trên HTTPS |
| Railway hết credit | Free tier giới hạn | Tạm dừng Postgres/Redis khi không dùng, hoặc nâng cấp |
| Migration fail vì thiếu `alembic_version` | DB mới chưa có bảng | Xóa DB và tạo lại, hoặc chạy `alembic stamp head` rồi `alembic upgrade head` |

---

## 8. Cấu trúc file đã thêm / sửa

```
smart-project-manager/
├── .gitignore                    (mở rộng)
├── backend/
│   ├── .env.example              (thêm chú thích cho production)
│   ├── railway.toml              (MỚI — config Railway)
│   └── app/main.py               (CORS giờ chỉ dùng CORS_ORIGINS khi DEBUG=false)
└── frontend/
    ├── .env.example              (thêm chú thích cho production)
    └── vercel.json               (MỚI — config Vercel, headers bảo mật)
```

Toàn bộ phần còn lại của code đã sẵn sàng cho production:
- `backend/app/config.py` đọc mọi biến từ env.
- `frontend/lib/api.ts` dùng `NEXT_PUBLIC_API_URL`.
- `frontend/hooks/useWebSocket.ts`, `useUserWebSocket.ts`, `useProjectPresence.ts` dùng `NEXT_PUBLIC_WS_URL`.
- `.env` đã bị `.gitignore` loại trừ.

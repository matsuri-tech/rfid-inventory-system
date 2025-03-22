# Dockerfile
FROM python:3.10-slim

# 作業ディレクトリ
WORKDIR /app

# 依存ファイルコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー
COPY . .

# 起動コマンド（Cloud Run 本番用）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]


dev:
	kill -9 $$(lsof -t -i:8000) 2>/dev/null || true
	INNGEST_DEV=1 ./reachai/bin/alembic upgrade head
	INNGEST_DEV=1 ./reachai/bin/python -m uvicorn app.main:app --reload & \
	inngest dev -u http://127.0.0.1:8000/api/inngest
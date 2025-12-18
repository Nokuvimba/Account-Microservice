APP = app.main:app

install:
	@pip install -r requirements.txt

run:
	@python -m uvicorn $(APP) --host 0.0.0.0 --port 8000 --reload

test:
	@pytest

docker-build:
	docker compose up --build

docker-down:
	docker compose down	

exportLogin:
	export LOGIN_BASE_URL=http://localhost:8000

runAccount:
	python -m uvicorn app.main:app --reload --port 8002


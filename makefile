APP = app.main:app

install:
	@pip install -r requirements.txt

run:
	@python -m uvicorn $(APP) --host 0.0.0.0 --port 8000 --reload

test:
	@pytest
.PHONY: install lint test up down logs clean

install:
	uv pip install --upgrade pip
	uv pip install .[dev]

lint:
	pre-commit run --all-files

test:
	pytest --maxfail=1 --disable-warnings -q

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f

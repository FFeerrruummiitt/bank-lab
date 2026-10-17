.PHONY: up stop logs test seed
up:
	python3 scripts/init_env.py
	docker compose up -d --build --wait
	docker compose exec -T backend python manage.py seed_demo
stop:
	docker compose stop
logs:
	docker compose logs -f backend
test:
	docker compose exec -T backend python manage.py test bank --noinput
seed:
	docker compose exec -T backend python manage.py seed_demo

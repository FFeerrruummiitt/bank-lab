.PHONY: up stop logs test seed monitoring-check
up:
	python3 scripts/init_env.py
	docker compose up -d --build --wait
	docker compose exec -T backend python manage.py seed_demo
stop:
	docker compose stop
logs:
	docker compose logs -f backend
test:
	docker compose exec -T -e BANK_LOG_DIR= backend python manage.py test bank --noinput
seed:
	docker compose exec -T backend python manage.py seed_demo
monitoring-check:
	python3 scripts/check_monitoring.py

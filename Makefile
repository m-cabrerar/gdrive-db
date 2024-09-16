run:
	docker compose up --build 

sql:
	docker exec -it google_test-db-1 psql -U user -d gdrive_db

down:
	docker compose down
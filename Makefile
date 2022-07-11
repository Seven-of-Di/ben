setup:
	conda create -f environment.yml

activate:
	conda activate ben

gameserver:
	cd ./src; python gameserver.py

webserver:
	cd ./src; python webserver.py

docker_build:
	docker buildx build --platform linux/x86_64 .

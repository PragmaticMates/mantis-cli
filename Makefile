sdist-and-upload:
	make sdist
	make upload

sdist:
	python3 setup.py sdist

upload:
	twine upload dist/$(shell ls -t -1 dist | head -n 1)

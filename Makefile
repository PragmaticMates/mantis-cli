sdist:
	python3 setup.py sdist
	twine upload dist/$(shell ls -t -1 dist | head -n 1)
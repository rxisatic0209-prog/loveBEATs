.PHONY: run test smoke simulate-heart-rate

run:
	. .venv/bin/activate && uvicorn app.main:app --reload

test:
	. .venv/bin/activate && python -m unittest discover -s tests

smoke:
	. .venv/bin/activate && python scripts/smoke_test.py

simulate-heart-rate:
	. .venv/bin/activate && python scripts/heart_rate_simulator.py

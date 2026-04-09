.PHONY: run test smoke smoke-persona-agent simulate-heart-rate

run:
	. .venv/bin/activate && uvicorn app.main:app --reload

test:
	. .venv/bin/activate && python -m unittest discover -s tests

smoke:
	. .venv/bin/activate && python scripts/smoke_test.py

smoke-persona-agent:
	. .venv/bin/activate && python scripts/persona_agent_smoke.py

simulate-heart-rate:
	. .venv/bin/activate && python scripts/heart_rate_simulator.py

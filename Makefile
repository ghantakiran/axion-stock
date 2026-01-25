.PHONY: install test lint run docker-build docker-run clean

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=src --cov=app --cov-report=term-missing

# Lint code
lint:
	ruff check src/ app/ tests/

# Format code
format:
	ruff format src/ app/ tests/

# Run CLI
run:
	python main.py --amount 10000 --verbose

# Run Streamlit app
app:
	streamlit run app/streamlit_app.py

# Run backtest
backtest:
	python main.py --amount 10000 --backtest --verbose

# Build Docker image
docker-build:
	docker build -t axion:latest .

# Run Docker container
docker-run:
	docker run -p 8501:8501 --env-file .env axion:latest

# Clean cache and build artifacts
clean:
	rm -rf cache/*.pkl
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf *.egg-info
	rm -rf dist build

# Refresh data cache
refresh:
	python main.py --amount 10000 --no-cache --verbose

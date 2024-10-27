VENV_DIR = .venv
PYTHON = python3
PIP = $(VENV_DIR)/bin/pip
PYTHON_BIN = $(VENV_DIR)/bin/python

.PHONY: install
install: $(VENV_DIR)/bin/activate
	@echo "Environment setup complete. Use 'source $(VENV_DIR)/bin/activate' to activate the environment."

$(VENV_DIR)/bin/activate: requirements.txt
	$(PYTHON) -m venv --system-site-packages $(VENV_DIR)
	$(PIP) install -r requirements.txt
	touch $(VENV_DIR)/bin/activate

.PHONY: run
run: $(VENV_DIR)/bin/activate
	$(PYTHON_BIN) fish.py

.PHONY: clean
clean:
	rm -rf $(VENV_DIR)
	@echo "Virtual environment removed."

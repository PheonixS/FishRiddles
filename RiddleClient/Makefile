VENV_DIR = .venv
PYTHON = python3
PIP = $(VENV_DIR)/bin/pip
PYTHON_BIN = $(VENV_DIR)/bin/python
PROJECT_DIR = $(shell pwd)
PYTHON_FULL_PATH = $(PROJECT_DIR)/$(PYTHON_BIN)
VENV_DIR_FULL_PATH = $(PROJECT_DIR)/$(VENV_DIR)
SYSTEMD_USER_PATH = $(HOME)/.config/systemd/user

I2C_CHECK_SERVICE_NAME = i2c-check.service
I2C_CHECK_SERVICE_SOURCE_PATH = scripts/$(I2C_CHECK_SERVICE_NAME)
I2C_CHECK_SERVICE_INSTALL_PATH = $(SYSTEMD_USER_PATH)/$(I2C_CHECK_SERVICE_NAME)
I2C_CHECK_SERVICE_SCRIPT = check_i2c_device.sh
I2C_CHECK_SERVICE_SOURCE_SCRIPT_PATH = scripts/$(I2C_CHECK_SERVICE_SCRIPT)
I2C_CHECK_SERVICE_SCRIPT_FULL_PATH = $(PROJECT_DIR)/$(I2C_CHECK_SERVICE_SOURCE_SCRIPT_PATH)

RIDDLE_CLIENT_SERVICE_NAME = riddleclient.service
RIDDLE_CLIENT_SERVICE_SOURCE_PATH = scripts/$(RIDDLE_CLIENT_SERVICE_NAME)
RIDDLE_CLIENT_SERVICE_INSTALL_PATH = $(SYSTEMD_USER_PATH)/$(RIDDLE_CLIENT_SERVICE_NAME)

FACE_MODEL_PATH = .opencv_models/res10_300x300_ssd_iter_140000_fp16.caffemodel
FACE_PROTO_PATH = .opencv_models/deploy.prototxt
AGE_MODEL_PATH = .opencv_models/age_net.caffemodel
AGE_PROTO_PATH = .opencv_models/age_deploy.prototxt

FACE_MODEL_URL = https://raw.githubusercontent.com/spmallick/learnopencv/17c758d3f394efa0d24e67b41dc03e45ff76b791/FaceDetectionComparison/models/res10_300x300_ssd_iter_140000_fp16.caffemodel
FACE_PROTO_URL = https://raw.githubusercontent.com/spmallick/learnopencv/17c758d3f394efa0d24e67b41dc03e45ff76b791/FaceDetectionComparison/models/deploy.prototxt
AGE_MODEL_URL = https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/7c024d9d453c9b35a72a984d8821b5832ef17401/age_net.caffemodel
AGE_PROTO_URL = https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/7c024d9d453c9b35a72a984d8821b5832ef17401/age_deploy.prototxt

SED_INPLACE := $(shell if sed --version 2>/dev/null | grep -q GNU; then echo '-i'; else echo '-i ""'; fi)

.PHONY: install
install: $(VENV_DIR)/bin/activate
	@echo "Environment setup complete. Use 'source $(VENV_DIR)/bin/activate' to activate the environment."

$(VENV_DIR)/bin/activate: requirements.txt
	$(PYTHON) -m venv --system-site-packages $(VENV_DIR)
	$(PIP) install -r requirements.txt
	touch $(VENV_DIR)/bin/activate

models: $(FACE_MODEL_PATH) $(FACE_PROTO_PATH) $(AGE_MODEL_PATH) $(AGE_PROTO_PATH)

$(FACE_MODEL_PATH):
	curl -o $(FACE_MODEL_PATH) $(FACE_MODEL_URL)

$(FACE_PROTO_PATH):
	curl -o $(FACE_PROTO_PATH) $(FACE_PROTO_URL)

$(AGE_MODEL_PATH):
	curl -o $(AGE_MODEL_PATH) $(AGE_MODEL_URL)

$(AGE_PROTO_PATH):
	curl -o $(AGE_PROTO_PATH) $(AGE_PROTO_URL)

.PHONY: run
run: $(VENV_DIR)/bin/activate models
	$(PYTHON_BIN) fish.py

.PHONY: clean
clean:
	rm -rf $(VENV_DIR)
	@echo "Virtual environment removed."

.PHONY: install-daemon
install-daemon: $(I2C_CHECK_SERVICE_SOURCE_PATH) $(RIDDLE_CLIENT_SERVICE_SOURCE_PATH)
	install -d -m 755 $(SYSTEMD_USER_PATH)
	install -m 644 $(I2C_CHECK_SERVICE_SOURCE_PATH) $(I2C_CHECK_SERVICE_INSTALL_PATH)
	install -m 644 $(RIDDLE_CLIENT_SERVICE_SOURCE_PATH) $(RIDDLE_CLIENT_SERVICE_INSTALL_PATH)
	sed $(SED_INPLACE) -e 's|%PYTHON_PATH%|$(PYTHON_FULL_PATH)|g' $(RIDDLE_CLIENT_SERVICE_INSTALL_PATH) \
					   -e 's|%PROJECT_ROOT_PATH%|$(PROJECT_DIR)|g' $(RIDDLE_CLIENT_SERVICE_INSTALL_PATH) \
					   -e 's|%VENV_PATH%|$(VENV_DIR_FULL_PATH)|g' $(RIDDLE_CLIENT_SERVICE_INSTALL_PATH) \
					   -e 's|%SCRIPT_FULL_PATH%|$(I2C_CHECK_SERVICE_SCRIPT_FULL_PATH)|g' $(I2C_CHECK_SERVICE_INSTALL_PATH)
	systemctl --user daemon-reload
	systemctl --user enable $(I2C_CHECK_SERVICE_NAME)
	systemctl --user start $(I2C_CHECK_SERVICE_NAME)
	@echo "$(I2C_CHECK_SERVICE_NAME) installed and started successfully."
	systemctl --user enable $(RIDDLE_CLIENT_SERVICE_NAME)
	systemctl --user start $(RIDDLE_CLIENT_SERVICE_NAME)
	@echo "$(RIDDLE_CLIENT_SERVICE_NAME) installed and started successfully."

.PHONY: uninstall-daemon
uninstall-daemon:
	systemctl --user stop $(RIDDLE_CLIENT_SERVICE_NAME)
	systemctl --user disable $(RIDDLE_CLIENT_SERVICE_NAME)
	systemctl --user stop $(I2C_CHECK_SERVICE_NAME)
	systemctl --user disable $(I2C_CHECK_SERVICE_NAME)
	rm $(I2C_CHECK_SERVICE_INSTALL_PATH)
	rm $(RIDDLE_CLIENT_SERVICE_INSTALL_PATH)
	systemctl --user daemon-reload
	@echo "$(SERVICE_NAME) uninstalled successfully."

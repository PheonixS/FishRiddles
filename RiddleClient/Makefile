VENV_DIR = .venv
PYTHON = python3
PIP = $(VENV_DIR)/bin/pip
PYTHON_BIN = $(VENV_DIR)/bin/python

FACE_MODEL_PATH = .opencv_models/res10_300x300_ssd_iter_140000_fp16.caffemodel
FACE_PROTO_PATH = .opencv_models/deploy.prototxt
AGE_MODEL_PATH = .opencv_models/age_net.caffemodel
AGE_PROTO_PATH = .opencv_models/age_deploy.prototxt

FACE_MODEL_URL = https://raw.githubusercontent.com/spmallick/learnopencv/17c758d3f394efa0d24e67b41dc03e45ff76b791/FaceDetectionComparison/models/res10_300x300_ssd_iter_140000_fp16.caffemodel
FACE_PROTO_URL = https://raw.githubusercontent.com/spmallick/learnopencv/17c758d3f394efa0d24e67b41dc03e45ff76b791/FaceDetectionComparison/models/deploy.prototxt
AGE_MODEL_URL = https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/7c024d9d453c9b35a72a984d8821b5832ef17401/age_net.caffemodel
AGE_PROTO_URL = https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/7c024d9d453c9b35a72a984d8821b5832ef17401/age_deploy.prototxt

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

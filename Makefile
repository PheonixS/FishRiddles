.PHONY: RiddleClient
RiddleClient:
	@echo "RiddleClient: installing"
	$(MAKE) -C RiddleClient install

.PHONY: RiddleClient-daemon-install
RiddleClient-daemon-install:
	@echo "RiddleClient: installing daemon mode"
	$(MAKE) -C RiddleClient install-daemon

.PHONY: RiddleClient-daemon-uninstall
RiddleClient-daemon-uninstall:
	@echo "RiddleClient: uninstalling daemon mode"
	$(MAKE) -C RiddleClient uninstall-daemon

PORT ?= /dev/cu.usbmodem2101
MP    = mpremote connect $(PORT)
SRC   = $(filter-out src/credentials.example.py,$(wildcard src/*.py))
P    ?= demo
comma := ,

.PHONY: help install ota repl reset preview sandbox stop ls log info

help:
	@echo "USB:   make install | repl | reset | preview P=<pattern> | sandbox | stop"
	@echo "Wi-Fi: make ota | log | info   (or python3 tools/ota.py --help)"

src/credentials.py:
	@echo "Create src/credentials.py first:  cp src/credentials.example.py src/credentials.py" && exit 1

install: src/credentials.py     ## copy everything over USB and reboot
	$(MP) fs cp $(SRC) : + reset

ota:                            ## push changed files over Wi-Fi and reboot
	python3 tools/ota.py push

repl:
	$(MP) repl

reset:
	$(MP) reset

# preview/sandbox/stop mount src/ from this computer, so they always use your
# local code and config. Ctrl-C stops the animation on the board and blanks the LEDs.
RUN = PORT=$(PORT) tools/board_run.sh

preview:                        ## make preview P=comets [B=0.2]   (Ctrl-C to stop)
	@$(RUN) exec "import patterns; patterns.preview('$(P)'$(if $(B),$(comma) brightness=$(B)))"

sandbox:                        ## run experiments/sandbox.py on the board  (Ctrl-C to stop)
	@$(RUN) run experiments/sandbox.py

stop:                           ## stop whatever is running on the board and turn the LEDs off
	@$(RUN) exec "from leds import Display; Display().off()" && echo "stopped, LEDs off"

ls:
	$(MP) fs ls

log:
	python3 tools/ota.py log

info:
	python3 tools/ota.py info

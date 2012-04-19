INST_DIR = ~/.qgis/python/plugins/quantumnik_dev

#PYRCC = /System/Library/Frameworks/Python.framework/Versions/2.5/bin/pyrcc4
#PYUIC = /System/Library/Frameworks/Python.framework/Versions/2.5/bin/pyuic4

PYRCC = pyrcc4
PYUIC = pyuic4

RC_PY_FILE = resources.py

all: $(RC_PY_FILE) imageexport_ui.py text_editor_ui.py

install: all
	mkdir -p $(INST_DIR)
	cp *.py $(INST_DIR)/
	cp *.png $(INST_DIR)/
	chmod -R 777 $(INST_DIR)/

clean:
	rm -f $(RC_PY_FILE)
	rm -f *.pyc

$(RC_PY_FILE): resources.qrc
	$(PYRCC) -o $(RC_PY_FILE) resources.qrc

imageexport_ui.py: imageexport.ui
	$(PYUIC) -o imageexport_ui.py imageexport.ui

text_editor_ui.py: text_editor.ui
	$(PYUIC) -o text_editor_ui.py text_editor.ui
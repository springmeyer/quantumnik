# -*- coding: utf-8 -*-

import os
import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from text_editor_ui import Ui_DockWidget

class TextEditor(QDockWidget, Ui_DockWidget):
    def __init__(self, parent=None):
        QDockWidget.__init__(self, parent.iface.mainWindow())
        # Set up the user interface from Designer. 
        self.parent = parent
        self.setupUi(self)
        #self.textEdit.setText("hello")
    
    def closeEvent(self, event):
        self.parent.dock_window = None
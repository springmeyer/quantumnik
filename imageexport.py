# -*- coding: utf-8 -*-

import os
import sys
import sync
import time
import tempfile
import render_wrapper
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from imageexport_ui import Ui_ImageExport

try:
    import mapnik2 as mapnik
except ImportError:
    import mapnik

class ImageExport(QDialog, Ui_ImageExport):
    def __init__(self, parent, flags=None):
        QDialog.__init__(self, parent.iface.mainWindow(), flags)
        # Set up the user interface from Designer. 
        self.parent = parent
        self.setupUi(self)
        QObject.connect(self.image_output_button, SIGNAL("clicked()"), self.setSaveFile)
        QObject.connect(self.tmp_render, SIGNAL("clicked(bool)"), self.toggle_tmp_render)
        QObject.connect(self.auto_open, SIGNAL("clicked(bool)"), self.toggle_auto_open)
        QObject.connect(self.transparent_background, SIGNAL("clicked(bool)"), self.toggle_transparent_background)
        #self.width.setText("600")
        #self.height.setText("400")
        self.format.setCurrentIndex(self.format.findText("png"))
        self.use_auto_open = False
        self.use_tmp_file = False
        self.use_transparent_background = False

        #QObject.connect(self.format, SIGNAL("textChanged(QString)"), self.switch_format)
        #QObject.connect(self.format, SIGNAL("textIndexChanged(QString)"), self.switch_format)
        #QObject.connect(self.format, SIGNAL("textChanged(QString)"), self.switch_format)
        QObject.connect(self.format, SIGNAL("highlighted(QString)"), self.switch_format)
            
        # setup drop
        self.image_output_path.__class__.dragEnterEvent = self.path_drag
        self.image_output_path.__class__.dropEvent = self.path_drop

        if self.parent.last_image_path:
            self.image_output_path.setText(self.parent.last_image_path)
        else:
            from qgis.core import QgsProject as project
            project_name = os.path.basename(str(project.instance().fileName()))
            if project_name:
                project_name = project_name.split('.')[0]
            else:
                project_name = 'mapnik_map'
            # todo - use temp directory!
            self.image_output_path.setText("~/quantumnik/%s.%s" % (project_name,self.format.currentText()))

        #add the custom paper sizes to the combobox
        self.add_sizes()

        if self.parent.from_mapfile:
            self.resolution.setEnabled(False)
            self.resolution.setText("Not supported")
        else:
            self.resolution.setText("90")
        # set up QSettings
        self.settings = QSettings("dbsgeo","Quantumnik")
        
    def switch_format(self,new_format):
        path = self.image_output_path.text()
        parts = path.split('.') 
        if len(parts) > 1:            
            new_text = path.replace('.%s' % parts[1],'.%s' % new_format)
            self.image_output_path.setText(new_text)        
        
    def toggle_transparent_background(self, isChecked):
        self.use_transparent_background = isChecked

    def toggle_auto_open(self, isChecked):
        self.use_auto_open = isChecked
    
    def toggle_tmp_render(self, isChecked):
        self.image_output_path.setEnabled(not isChecked)
        self.image_output_button.setEnabled(not isChecked)
        self.use_tmp_file = isChecked        
        
    def add_sizes(self):
        from print2pixel import north_america as na,iso,jis,ansi
        names = []
        for item in na.items():
            name = QString("NA: %s %s (in)" % item)
            self.sizes.addItem(name)
        for item in ansi.items():
            name = QString("ANSI: %s %s (in)" % item)
            self.sizes.addItem(name)
        for item in iso.items():
            name = QString("ISO: %s %s (mm)" % item)
            self.sizes.addItem(name)
        for item in jis.items():
            name = QString("Japanese: %s %s (mm)" % item)
            self.sizes.addItem(name)
        #self.sizes.setItemText(0, QApplication.translate("ImageExport", "test", None, QApplication.UnicodeUTF8))

    def path_drag(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def path_drop(self, event):
        urls = event.mimeData().urls();
        file = str(urls[0].path())
        self.image_output_path.setText(file)
        self.parent.last_image_path = file
        event.acceptProposedAction()
        #event.ignore()

    def dimensions(self):
        #if self.use_map_dimensions:
        return self.parent.canvas.width(),self.parent.canvas.height()
        #else:
        #    pass
            #paper = 
            #size = 
            #w,h = 

    def setSaveFile(self):
        map_path = str(self.settings.value("path/last_map_path",QVariant(".")).toString())
        mapFile = QFileDialog.getSaveFileName(self, "Name for the file", \
          map_path, "Image (*.png *.jpeg *.pdf *.svg *.ps)","Filter list for selecting files from a dialog box")
        self.image_output_path.setText(mapFile)
        self.parent.last_image_path = mapFile
        if mapFile:
            self.settings.setValue("path/last_map_path",QVariant(os.path.dirname(str(mapFile))))

    def view_file(self,file_name,app=None):
        import platform
        if '~' in file_name:
            file_name = os.path.expanduser(file_name)
        try:
            if os.name == 'nt':
                if app:
                    QMessageBox.information(self.parent.iface.mainWindow(),"Information", 'Overriding default image viewer not yet supported on Win32')
                os.system('start %s' % file_name.replace('/','\\'))
                #os.system('start "%s"' % os.path.dirname(file_name))
            elif platform.uname()[0] == 'Linux':
                if app:
                    os.system('%s "%s"' % (app, file_name))
                else:
                    # todo - this is unlikely to work...
                    os.system('gthumb %s' % file_name)
            elif platform.uname()[0] == 'Darwin':
                if app:
                    os.system('open %s -a "%s"' % (file_name, app))
                else:
                    os.system('open "%s"' % file_name)
        except Exception, e:
            QMessageBox.information(self.parent.iface.mainWindow(),"Information", 'Problem auto-opening image: %s' % e)
    
    # http://diotavelli.net/PyQtWiki/Threading,_Signals_and_Slots
    def render_thread(self,m,out,format):
        worky,result = render_wrapper.render_to_file(m,out,format)
        if worky:
            if self.use_auto_open:
                self.view_file(out)
            else:
                QMessageBox.information(self.parent.iface.mainWindow(),"Information", "Rendered to %s" % out)
        else:
            QMessageBox.information(self.parent.iface.mainWindow(),"Error", 'Sorry, export failed likely because your Mapnik install does not support the %s format. Error was: %s' % (format,result))

    def accept(self):
        w,h = self.dimensions()
        if self.parent.from_mapfile:
            m = self.parent.mapnik_map
        else:
            m = sync.EasyCanvas(self.parent,self.parent.canvas,int(self.resolution.text())).to_mapnik()
        e = self.parent.canvas.extent()
        bbox = mapnik.Envelope(e.xMinimum(),e.yMinimum(),e.xMaximum(),e.yMaximum())
        m.zoom_to_box(bbox)

        format = str(self.format.currentText())
        
        if self.use_transparent_background:
            m.background = mapnik.Color('transparent')
        elif not self.parent.from_mapfile:
            m.background = self.parent.background 
        
        if self.use_tmp_file:
            (handle, out) = tempfile.mkstemp('.%s' % format, 'quantumnik_output')
            os.close(handle)
        else:
            out = str(self.image_output_path.text())
        
        self.render_thread(m,out,format)
        
        #import thread
        #thread.start_new_thread(self.render_thread, (m,out,format))
        #return

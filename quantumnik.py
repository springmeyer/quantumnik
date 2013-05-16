# -*- coding: utf-8 -*-

import os
import tempfile
import resources
import relativism
from qgis.gui import *
from qgis.core import *
from PyQt4.QtGui import *
from PyQt4.QtCore import *

try:
    import mapnik2 as mapnik
except ImportError:
    import mapnik

# repair compatibility with mapnik2 development series
if hasattr(mapnik,'Box2d'):
    mapnik.Envelope = mapnik.Box2d

MAPNIK_VERSION = None

if hasattr(mapnik,'mapnik_version'):
    MAPNIK_VERSION = mapnik.mapnik_version()

import sync
    
# Use pdb for debugging
#import pdb
# These lines allow you to set a breakpoint in the app
#pyqtRemoveInputHook()
#pdb.set_trace()

#TODO - support for Composer
# http://trac.osgeo.org/qgis/changeset/13361


try:
    from pygments import highlight
    from pygments.lexers import XmlLexer
    from pygments.formatters import HtmlFormatter
    HIGHLIGHTING = True
except:
    HIGHLIGHTING = False

from imageexport import ImageExport
from text_editor import TextEditor

NAME = 'Quantumnik'
    

class Quantumnik(QObject):
    def __init__(self, iface):
        QObject.__init__(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        # Fake canvas to use in tab to overlay the quantumnik layer
        self.qCanvas = None
        self.qCanvasPan = None
        self.qCanvasZoomIn = None
        self.qCanvasZoomOut = None
        self.tabWidget = None

        self.mapnik_map = None
        self.using_mapnik = False
        self.from_mapfile = False
        self.loaded_mapfile = None
        self.been_warned = False
        self.last_image_path = None
        self.dock_window = None
        self.keyAction = None
        self.keyAction2 = None
        self.keyAction3 = None

    def initGui(self):
        self.action = QAction(QIcon(":/mapnikglobe.png"), QString("Create Mapnik Canvas"),
                              self.iface.mainWindow())
        self.action.setWhatsThis("Create Mapnik Canvas")
        self.action.setStatusTip("%s: render with Mapnik" % NAME)
        QObject.connect(self.action, SIGNAL("triggered()"), self.toggle)

        self.action4 = QAction(QString("View live xml"), self.iface.mainWindow())
        QObject.connect(self.action4, SIGNAL("triggered()"), self.view_xml)

        self.action3 = QAction(QString("Export Mapnik xml"),
                               self.iface.mainWindow())
        QObject.connect(self.action3, SIGNAL("triggered()"), self.save_xml)

        self.action5 = QAction(QString("Load Mapnik xml"),
                               self.iface.mainWindow())
        QObject.connect(self.action5, SIGNAL("triggered()"), self.load_xml)

        self.action6 = QAction(QString("Load Cascadenik mml"),
                               self.iface.mainWindow())
        QObject.connect(self.action6, SIGNAL("triggered()"), self.load_mml)

        self.action7 = QAction(QString("Export Map Graphics"), self.iface.mainWindow())
        QObject.connect(self.action7, SIGNAL("triggered()"),
                        self.export_image_gui)

        self.helpaction = QAction(QIcon(":/mapnikhelp.png"),"About",
                                  self.iface.mainWindow())
        self.helpaction.setWhatsThis("%s Help" % NAME)
        QObject.connect(self.helpaction, SIGNAL("triggered()"), self.helprun)
        
        self.iface.addToolBarIcon(self.action)


        self.iface.addPluginToMenu("&%s" % NAME, self.action)
        self.iface.addPluginToMenu("&%s" % NAME, self.helpaction)
        self.iface.addPluginToMenu("&%s" % NAME, self.action3)
        self.iface.addPluginToMenu("&%s" % NAME, self.action4)
        self.iface.addPluginToMenu("&%s" % NAME, self.action5)
        self.iface.addPluginToMenu("&%s" % NAME, self.action6)
        self.iface.addPluginToMenu("&%s" % NAME, self.action7)

        # > QGIS 1.2
        if hasattr(self.iface,'registerMainWindowAction'):
            self.keyAction2 = QAction(QString("Switch to QGIS"), self.iface.mainWindow())
            self.iface.registerMainWindowAction(self.keyAction2, "Ctrl+[")
            self.iface.addPluginToMenu("&%s" % NAME, self.keyAction2)
            QObject.connect(self.keyAction2, SIGNAL("triggered()"),self.switch_tab_qgis)
    
            self.keyAction3 = QAction(QString("Switch to Mapnik"), self.iface.mainWindow())
            self.iface.registerMainWindowAction(self.keyAction3, "Ctrl+]")
            self.iface.addPluginToMenu("&%s" % NAME, self.keyAction3)
            QObject.connect(self.keyAction3, SIGNAL("triggered()"),self.switch_tab_mapnik)
        
    def unload(self):
        self.iface.removePluginMenu("&%s" % NAME,self.action)
        self.iface.removePluginMenu("&%s" % NAME,self.helpaction)
        self.iface.removePluginMenu("&%s" % NAME,self.action3)
        self.iface.removePluginMenu("&%s" % NAME,self.action4)
        self.iface.removePluginMenu("&%s" % NAME,self.action5)
        self.iface.removePluginMenu("&%s" % NAME,self.action6)
        self.iface.removePluginMenu("&%s" % NAME,self.action7)
        self.iface.removeToolBarIcon(self.action)
        if self.keyAction:
            self.iface.unregisterMainWindowAction(self.keyAction)
        if self.keyAction2:
            self.iface.unregisterMainWindowAction(self.keyAction2)
        if self.keyAction3:
            self.iface.unregisterMainWindowAction(self.keyAction3)

    def export_image_gui(self):
        flags = Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowStaysOnTopHint
        export = ImageExport(self,flags)
        export.show()

    def view_xml(self,m=None):
        if not self.dock_window:
            self.dock_window = TextEditor(self)
            self.iface.mainWindow().addDockWidget( Qt.BottomDockWidgetArea,
                                                   self.dock_window )
            if not self.using_mapnik:
                # http://trac.osgeo.org/qgis/changeset/12955 - render starting signal
                QObject.connect(self.canvas, SIGNAL("renderComplete(QPainter *)"),
                                self.checkLayers)
        
        self.dock_window.show()
        if self.loaded_mapfile:
            # if we have loaded a map xml or mml
            # so lets just display the active file
            xml = open(self.loaded_mapfile,'rb').read()
        else:
            if not m:
                # regenerate from qgis objects
                e_c = sync.EasyCanvas(self,self.canvas)
                m = e_c.to_mapnik()
            if hasattr(mapnik,'save_map_to_string'):
                xml = mapnik.save_map_to_string(m)
            else:
                (handle, mapfile) = tempfile.mkstemp('.xml', 'quantumnik-map-')
                os.close(handle)
                mapnik.save_map(m,str(mapfile))
                xml = open(mapfile,'rb').read()
        e = self.canvas.extent()
        bbox = '%s %s %s %s' % (e.xMinimum(),e.yMinimum(),
                                e.xMaximum(),e.yMaximum())
        cmd = '\n<!-- nik2img.py mapnik.xml out.png -d %s %s -e %s -->\n' % (self.canvas.width(), self.canvas.height(), bbox)
        try:
            if self.mapnik_map:
                cmd += '<!-- <MinScaleDenominator>%s</MinScaleDenominator> -->\n' % (self.mapnik_map.scale_denominator())
        except:
            pass

        code = xml + cmd
        if HIGHLIGHTING:
            highlighted = highlight(code, XmlLexer(), HtmlFormatter(linenos=False, nowrap=False, full=True))
            self.dock_window.textEdit.setHtml(highlighted)
        else:
            self.dock_window.textEdit.setText(xml + cmd)

    def helprun(self):
        infoString = QString("Written by Dane Springmeyer\nhttps://github.com/springmeyer/quantumnik")
        QMessageBox.information(self.iface.mainWindow(),"About %s" % NAME,infoString)

    def toggle(self):
        if self.using_mapnik:
            self.stop_rendering()
        else:
            self.start_rendering()

    def proj_warning(self):
        self.been_warned = True
        ren = self.canvas.mapRenderer()
        if not ren.hasCrsTransformEnabled() and self.canvas.layerCount() > 1:
            if hasattr(self.canvas.layer(0),'crs'):
                if not self.canvas.layer(0).crs().toProj4() == ren.destinationCrs().toProj4():
                    QMessageBox.information(self.iface.mainWindow(),"Warning","The projection of the map and the first layer do not match. Mapnik may not render the layer(s) correctly.\n\nYou likely need to either enable 'On-the-fly' CRS transformation or set the Map projection in your Project Properties to the projection of your layer(s).")
            else:
                if not self.canvas.layer(0).srs().toProj4() == ren.destinationSrs().toProj4():
                    QMessageBox.information(self.iface.mainWindow(),"Warning","The projection of the map and the first layer do not match. Mapnik may not render the layer(s) correctly.\n\nYou likely need to either enable 'On-the-fly' CRS transformation or set the Map projection in your Project Properties to the projection of your layer(s).")
        
    def save_xml(self):
        # need to expose as an option!
        relative_paths = True
        
        mapfile = QFileDialog.getSaveFileName(None, "Save file dialog", 
                                              'mapnik.xml', "Mapfile (*.xml)")
        if mapfile:
            e_c = sync.EasyCanvas(self,self.canvas)
            mapfile_ = str(mapfile)
            base_path = os.path.dirname(mapfile_)
            e_c.base_path = base_path
            m = e_c.to_mapnik()
            mapnik.save_map(m,mapfile_)

            if relative_paths:
                relativism.fix_paths(mapfile_,base_path)
    
    def make_bundle(self): pass  
        # todo: accept directory name
        # move mapfile and all file based datasources
        # into that folder and stash some docs inside
        # provide option to zip and upload to url on the fly
        
    def set_canvas_from_mapnik(self):
        # set up keyboard shortcut
        # > QGIS 1.2
        if hasattr(self.iface,'registerMainWindowAction'):
            if not self.keyAction:
                # TODO - hotkey does not work on linux....
                self.keyAction = QAction(QString("Refresh " + NAME), self.iface.mainWindow())
                self.iface.registerMainWindowAction(self.keyAction, "Ctrl+r")
                self.iface.addPluginToMenu("&%s" % NAME, self.keyAction)
                QObject.connect(self.keyAction, SIGNAL("triggered()"),self.toggle)
        
        self.mapnik_map.zoom_all()
        e = self.mapnik_map.envelope()
        crs = QgsCoordinateReferenceSystem()
        srs = self.mapnik_map.srs
        if srs == '+init=epsg:900913':
            # until we can look it up in srs.db...
            merc = "+init=EPSG:900913"
            crs.createFromProj4(QString(merc))
        elif 'init' in srs:
            # TODO - quick hack, needs regex and fallbacks
            epsg = srs.split(':')[1]
            crs.createFromEpsg(int(epsg))
        else:
            if srs == '+proj=latlong +datum=WGS84':
                # expand the Mapnik srs a bit 
                # http://trac.mapnik.org/ticket/333
                srs = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
            crs.createFromProj4(QString(srs))
        if hasattr(self.canvas.mapRenderer(),'setDestinationCrs'):
            self.canvas.mapRenderer().setDestinationCrs(crs)
        else:
            self.canvas.mapRenderer().setDestinationSrs(crs)
        if not crs.isValid():
            QMessageBox.information(self.iface.mainWindow(),
                                    "Warning","Projection not understood")
            return
        QObject.connect(self.canvas, SIGNAL("renderComplete(QPainter *)"),
                        self.render_dynamic)
        self.canvas.setExtent(QgsRectangle(e.minx,e.miny,e.maxx,e.maxy))
        self.canvas.refresh()

    def set_mapnik_to_canvas(self):
        QObject.connect(self.canvas, SIGNAL("renderComplete(QPainter *)"),
                        self.render_dynamic)
        self.canvas.refresh()
        
    def refresh_loaded_mapfile(self):
        if self.mapfile_format == 'Cascadenik mml':
            self.load_mml(refresh=True)
        else:
            self.load_xml(refresh=True)
        
    def load_mml(self,refresh=False):
        self.from_mapfile = True
        self.mapfile_format = 'Cascadenik mml'
        if self.loaded_mapfile and refresh:
            mapfile = self.loaded_mapfile
        else:
            mapfile = QFileDialog.getOpenFileName(None, "Open file dialog",
                                                  '', "Cascadenik MML (*.mml)")
        if mapfile:
            self.mapnik_map = mapnik.Map(1,1)
            import cascadenik
            if hasattr(cascadenik,'VERSION'):
                major = int(cascadenik.VERSION.split('.')[0])
                if major < 1:
                    from cascadenik import compile
                    compiled = '%s_compiled.xml' % os.path.splitext(str(mapfile))[0]
                    open(compiled, 'w').write(compile(str(mapfile)))
                    mapnik.load_map(self.mapnik_map, compiled)
                elif major == 1:
                    output_dir = os.path.dirname(str(mapfile))
                    cascadenik.load_map(self.mapnik_map,str(mapfile),output_dir,verbose=False)
                elif major > 1:
                    raise NotImplementedError('This nik2img version does not yet support Cascadenik > 1.x, please upgrade nik2img to the latest release')
            else:
                from cascadenik import compile
                compiled = '%s_compiled.xml' % os.path.splitext(str(mapfile))[0]
                #if os.path.exits(compiled):
                    #pass
                open(compiled, 'w').write(compile(str(mapfile)))
                mapnik.load_map(self.mapnik_map, compiled)

            if self.loaded_mapfile and refresh:
                self.set_mapnik_to_canvas()            
            else:
                self.set_canvas_from_mapnik()
            self.loaded_mapfile = str(mapfile)
  
    def load_xml(self,refresh=False):
        # TODO - consider putting into its own layer:
        # https://trac.osgeo.org/qgis/ticket/2392#comment:4
        self.from_mapfile = True
        self.mapfile_format = 'xml mapfile'
        if self.loaded_mapfile and refresh:
            mapfile = self.loaded_mapfile
        else:
            mapfile = QFileDialog.getOpenFileName(None, "Open file dialog",
                                                  '', "XML Mapfile (*.xml)")
        if mapfile:
            self.mapnik_map = mapnik.Map(1,1)
            mapnik.load_map(self.mapnik_map,str(mapfile))
            if self.loaded_mapfile and refresh:
                self.set_mapnik_to_canvas()            
            else:
                self.set_canvas_from_mapnik()
            self.loaded_mapfile = str(mapfile)
  
    def finishStopRender(self):
        self.iface.mapCanvas().setMinimumSize(QSize(0, 0))

    def stop_rendering(self):
        # Disconnect all the signals as we disable the tool
        QObject.disconnect(self.qCanvas, SIGNAL("renderComplete(QPainter *)"),
                           self.render_dynamic)
        QObject.disconnect(self.qCanvas,
                           SIGNAL("xyCoordinates(const QgsPoint&)"),
                           self.updateCoordsDisplay)
        QObject.disconnect(self.canvas, SIGNAL("renderComplete(QPainter *)"),
                           self.checkLayers)
        QObject.disconnect(self.canvas, SIGNAL("extentsChanged()"),
                           self.checkExtentsChanged)
        QObject.disconnect(self.canvas, SIGNAL("mapToolSet(QgsMapTool *)"), 
                           self.mapToolSet)
        self.using_mapnik = False
        # If the current tab is quantumnik then we need to update the extent
        # of the main map when exiting to make sure they are in sync
        if self.tabWidget.currentIndex() == 1:
            self.mapnikMapCoordChange()
        # Need to restore the main map instead of the mapnik tab
        tabWidgetSize = self.tabWidget.size()
        mapCanvasExtent = self.iface.mapCanvas().extent()
        self.iface.mapCanvas().setMinimumSize(tabWidgetSize)
        self.iface.mainWindow().setCentralWidget(self.iface.mapCanvas())
        self.iface.mapCanvas().show()
        # Set the canvas extent to the same place it was before getting
        # rid of the tabs
        self.iface.mapCanvas().setExtent(mapCanvasExtent)
        self.canvas.refresh()

        # null out some vars
        self.qCanvasPan = None
        self.qCanvasZoomIn = None
        self.qCanvasZoomOut = None
        # We have to let the main app swizzle the screen and then 
        # hammer it back to the size we want
        QTimer.singleShot(1, self.finishStopRender)

  
    def create_mapnik_map(self):
        if not self.been_warned:
            self.proj_warning()
        self.easyCanvas = sync.EasyCanvas(self,self.canvas)
        self.mapnik_map = self.easyCanvas.to_mapnik()
        if self.dock_window:
            self.view_xml(self.mapnik_map)

    @property
    def background(self):
        return sync.css_color(self.canvas.backgroundBrush().color())
        
    # Provide a hack to try and find the map coordinate status bar element
    # to take over while the mapnik canvas is in play.
    def findMapCoordsStatus(self):
        coordStatusWidget = None
        sb = self.iface.mainWindow().statusBar()
        for x in sb.children():
            # Check if we have a line edit
            if isinstance(x, QLineEdit):
                # Now check if the text does not contain a ':'
                if not ':' in x.text():
                    # we have our coord status widget
                    coordStatusWidget = x
        return coordStatusWidget

    def finishStartRendering(self):
        self.tabWidget.setMinimumSize(QSize(0, 0))
        self.canvas.refresh()

    def start_rendering(self):
        if self.from_mapfile and not self.canvas.layerCount():
            self.refresh_loaded_mapfile()
        else:
            self.from_mapfile = False
            # http://trac.osgeo.org/qgis/changeset/12926
            # TODO - if not dirty we don't need to create a new map from scratch...
            self.create_mapnik_map()
            # Need to create a tab widget to toss into the main window
            # to hold both the main canvas as well as the mapnik rendering
            mapCanvasSize = self.canvas.size()
            mapCanvasExtent = self.iface.mapCanvas().extent()
            newWidget = QTabWidget(self.iface.mainWindow())
            sizePolicy = QSizePolicy(QSizePolicy.Expanding,
                                     QSizePolicy.Preferred)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
            sizePolicy.setHeightForWidth(newWidget.sizePolicy().hasHeightForWidth())
            newWidget.setSizePolicy(sizePolicy)         
            newWidget.setSizeIncrement(QSize(0, 0))
            newWidget.setBaseSize(mapCanvasSize)
            newWidget.resize(mapCanvasSize)
            # Very important: Set the min size of the tabs to the size of the
            # original canvas.  We will then let the main app take control 
            # and then use a one shot timer to set the min size back down.  It
            # is a hack, but allows us to keep the canvas and tab size correct.
            newWidget.setMinimumSize(mapCanvasSize)
            
            # This is the new blank canvas that we will use the qpainter
            # from to draw the mapnik image over.
            self.qCanvas = QgsMapCanvas(self.iface.mainWindow())
            self.qCanvas.setCanvasColor(QColor(255,255,255))
            self.qCanvas.enableAntiAliasing(True)
            self.qCanvas.useImageToRender(False)
            self.qCanvas.show()

            # A set of map tools for the mapnik canvas
            self.qCanvasPan = QgsMapToolPan(self.qCanvas)
            self.qCanvasZoomIn = QgsMapToolZoom(self.qCanvas,False)
            self.qCanvasZoomOut = QgsMapToolZoom(self.qCanvas,True)
            self.mapToolSet(self.canvas.mapTool())

            # Add the canvas items to the tabs
            newWidget.addTab(self.canvas, "Main Map")
            newWidget.addTab(self.qCanvas, "Mapnik Rendered Map")
            self.tabWidget = newWidget
            # Add the tabs as the central widget
            self.iface.mainWindow().setCentralWidget(newWidget)
            # Need to set the extent of both canvases as we have just resized
            # things
            self.canvas.setExtent(mapCanvasExtent)
            self.qCanvas.setExtent(mapCanvasExtent)
            # Hook up to the tabs changing so we can make sure to update the 
            # rendering in a lazy way... i.e. a pan in the main canvas will 
            # not cause a redraw in the mapnik tab until the mapnik tab
            # is selected.
            self.connect(self.tabWidget,SIGNAL("currentChanged(int)"),
                         self.tabChanged)
            # Grab the maptool change signal so the mapnik canvas tool
            # can stay in sync. 
            # TODO: We need to get the in/out property for the zoom tool
            # exposed to the python bindings.  As it stands now, we can 
            # not tell what direction the tool is going when we get this
            # signal and it is a zoom tool.
            QObject.connect(self.canvas, SIGNAL("mapToolSet(QgsMapTool *)"), 
                            self.mapToolSet)
            # Catch any mouse movements over the mapnik canvas and 
            # sneek in and update the cord display
            ## This is a hack to find the status element to populate with xy
            self.mapCoords = self.findMapCoordsStatus()
            QObject.connect(self.qCanvas,
                            SIGNAL("xyCoordinates(const QgsPoint&)"),
                            self.updateCoordsDisplay)
            # Get the renderComplete signal for the qCanvas to allow us to 
            # render the mapnik image over it.
            QObject.connect(self.qCanvas, SIGNAL("renderComplete(QPainter *)"),
                            self.render_dynamic)
            # Get the renderComplete signal for the main canvas so we can tell
            # if there have been any layer changes and if we need to re-draw
            # the mapnik image.  This is mainly for when the mapnik tab is 
            # active but layer changes are happening.
            QObject.connect(self.canvas, SIGNAL("renderComplete(QPainter *)"),
                            self.checkLayers)
            QObject.connect(self.canvas, SIGNAL("extentsChanged()"),
                            self.checkExtentsChanged)
            self.using_mapnik=True
            # We use a single shot timer to let the main app resize the main
            # window with us holding a minsize we want, then we reset the
            # allowable min size after the main app has its turn.  Hack, but
            # allows for the window to be rezised with a new main widget.
            QTimer.singleShot(1, self.finishStartRendering)

    def updateCoordsDisplay(self, p):
        if self.mapCoords:
            capturePyString = "%.5f,%.5f" % (p.x(),p.y())
            capture_string = QString(capturePyString)
            self.mapCoords.setText(capture_string)

    def mapToolSet(self, tool):
        # something changed here in recent QGIS versions causing:
        # exceptions when closing QGIS because these objects are None
        if tool:
            if isinstance(tool,QgsMapToolPan):
                self.qCanvas.setMapTool(self.qCanvasPan)
            elif isinstance(tool,QgsMapToolZoom):
                # Yet another hack to find out if the tool we are using is a 
                # zoom in or out
                if tool.action().text() == QString("Zoom In"):
                    self.qCanvas.setMapTool(self.qCanvasZoomIn)
                else:
                    self.qCanvas.setMapTool(self.qCanvasZoomOut)
            else:
                self.qCanvas.setMapTool(self.qCanvasPan)

    def switch_tab_qgis(self):
        if self.tabWidget:
            self.tabWidget.setCurrentIndex(0)

    def switch_tab_mapnik(self):
        if self.tabWidget:
            self.tabWidget.setCurrentIndex(1)
        
    def tabChanged(self, index):
        if index == 0:
            self.mapnikMapCoordChange()
        else:
            self.mainMapCoordChange()

    def mainMapCoordChange(self):
        # print "coordChange"
        self.mapnik_map = self.easyCanvas.to_mapnik(self.mapnik_map)
        self.qCanvas.setExtent(self.iface.mapCanvas().extent())
        self.qCanvas.refresh()

    def mapnikMapCoordChange(self):
        # print "coordChange"
        self.canvas.setExtent(self.qCanvas.extent())
        self.canvas.refresh()

    # Here we are checking to see if we got a new extent on the main
    # canvas even though we are in the mapnik tab... in that case we have
    # done something like zoom to full extent etc.
    def checkExtentsChanged(self):
        if self.tabWidget:
            if self.tabWidget.currentIndex() == 1:
                self.mainMapCoordChange()


    # Here we are checking to see if we got a render complete on the main
    # canvas even though we are in the mapnik tab... in that case we have 
    # a new layer etc.
    def checkLayers(self, painter=None):
        if self.tabWidget:
            if self.tabWidget.currentIndex() == 1:
                # There was a change in the main canvas while we are viewing
                # the mapnik canvas (i.e. layer added/removed etc) so we 
                # need to refresh the mapnik map
                self.mapnik_map = self.easyCanvas.to_mapnik(self.mapnik_map)
                self.qCanvas.refresh()
                # We also make sure the main map canvas gets put back to the
                # current extent of the qCanvas incase the main map got changed
                # as a side effect since updates to it are lazy loaded on tab
                # change.
                self.canvas.setExtent(self.qCanvas.extent())
                # We make sure to update the XML viewer if
                # if is open
                if self.dock_window:
                    self.view_xml(self.mapnik_map)
        if self.dock_window:
            self.view_xml()
        
    def render_dynamic(self, painter):
        if self.mapnik_map:
            w = painter.device().width()
            h = painter.device().height()
            # using canvas dims leads to shift in QGIS < 1.3...
            #w = self.canvas.width()
            #h = self.canvas.height()
            try:
                self.mapnik_map.resize(w,h)
            except:
                self.mapnik_map.width = w
                self.mapnik_map.height = h
            if self.qCanvas:
                can = self.qCanvas
            else:
                can = self.canvas
            try:
                e = can.extent()
            except:
                can = self.canvas
                e = can.extent()
            bbox = mapnik.Envelope(e.xMinimum(),e.yMinimum(),
                                   e.xMaximum(),e.yMaximum())
            self.mapnik_map.zoom_to_box(bbox)
            im = mapnik.Image(w,h)
            mapnik.render(self.mapnik_map,im)
            if os.name == 'nt':
                qim = QImage()
                qim.loadFromData(QByteArray(im.tostring('png')))
                painter.drawImage(0,0,qim)
            else:
                qim = QImage(im.tostring(),w,h,QImage.Format_ARGB32)
                painter.drawImage(0,0,qim.rgbSwapped())
            can.refresh()

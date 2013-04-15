# -*- coding: utf-8 -*-

import os
import re
import math
import tempfile
from qgis.gui import *
from qgis.core import *
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from quantumnik import MAPNIK_VERSION

try:
    import mapnik2 as mapnik
except ImportError:
    import mapnik
    
#import pdb
#pyqtRemoveInputHook()
#pdb.set_trace()

# TODO - support composer
# http://trac.osgeo.org/qgis/changeset/12372

MAPNIK_PLUGINS = None

if MAPNIK_VERSION:
    MAPNIK_PLUGINS = list(mapnik.DatasourceCache.plugin_names())

# warn once about layers we cannot yet read...
INCOMPATIBLE_LAYER_WARNING = True

# warn once about plugins Mapnik does not have...
MISSING_PLUGIN_WARNING = True

# warn once that we don't yet support symbology-ng (aka rendererV2)
INCOMPATIBLE_RENDERER_WARNING = True

def is_number(s):
    """ Test if the value can be converted to a number.
    """
    try:
        float(s)
        return True
    except ValueError:
        return False

def check_plug(f):
    msg = "You will see this warning once per session...\n\nSorry your Mapnik version does not include the '%s' plugin.\n This plugin is needed by Mapnik to read the file: %s.\n\n If you downloaded a Mapnik installer, please contact the author about adding support for this Mapnik plugin.\n\n If you installed Mapnik from source rebuild Mapnik using the SCons option: INPUT_PLUGINS=%s,%s"
    def newf(*_args, **_kwds):
        global MISSING_PLUGIN_WARNING
        self = _args[0]
        if MAPNIK_PLUGINS:
            if not f.func_name in MAPNIK_PLUGINS:
                if MISSING_PLUGIN_WARNING:
                    MISSING_PLUGIN_WARNING = False
                    return self.message(msg % (f.func_name, self.source, f.func_name, ','.join(MAPNIK_PLUGINS)))
                else:
                    return None
        return f(*_args, **_kwds)
    return newf
        
def get_variant_value(variant):
    """'BitArray', 'Bitmap', 'Bool', 'Brush', 'ByteArray', 'Char', 'Color', 'Cursor', 'Date', 'DateTime', 'Double', 'Font', 'Icon', 'Image', 'Int', 'Invalid', 'KeySequence', 'Line', 'LineF', 'List', 'Locale', 'LongLong', 'Map', 'Matrix', 'Palette', 'Pen', 'Pixmap', 'Point', 'PointF', 'Polygon', 'Rect', 'RectF', 'RegExp', 'Region', 'Size', 'SizeF', 'SizePolicy', 'String', 'StringList', 'TextFormat', 'TextLength', 'Time', 'Transform', 'Type', 'UInt', 'ULongLong', 'Url',
    """
    if variant.type() == QVariant.Double:
        return variant.toDouble()[0]
    elif variant.type() == QVariant.Int:
        return variant.toInt()[0]
    elif variant.type() == QVariant.String:
        return unicode(variant.toString())
    elif variant.type() == QVariant.Bool:
        return variant.toBool()[0]
    elif variant.type() == QVariant.StringList:
        return variant.toList()[0]
    elif variant.type() == QVariant.List:
        return variant.toList()[0]
    else:
        raise TypeError('Field type not understood, value was: %s' % variant.toString())

class Ramp(object):
    def __init__(self,start,end,min,max):
        """ Ramp between two Mapnik Colors given a min and max value (int or float).
        """
        self.start = start
        self.end = end
        self.min = min
        self.max = max
    
    def scale(self,high,low,val):
        """ Ramp values by high and low bounds.
        """
        a,b = (val - self.min),(self.max - self.min)
        c,d = (self.max - val),(self.max - self.min)
        if 0 in [a,b,c,d]:
            return None
        highest = high * a/b
        lowest = low * c/d 
        return int(highest + lowest)

    def color_for_value(self,val):
        """ Scale each color by a given value.
        """
        red = self.scale(self.start.r,self.end.r,val) or 0
        green = self.scale(self.start.g,self.end.g,val) or 0
        blue = self.scale(self.start.b,self.end.b,val) or 0
        alpha = self.scale(self.start.a,self.end.a,val) or 1
        return red,green,blue,alpha
    
def css_color(qc):
    """ Turn a QColor into a mapnik::color."""
    # note, alpha is usually ignored in Mapnik and
    # and is handled in symbolizer 'CssParameter'
    # using the 'opacity' parameter
    try:
        col = mapnik.Color(str('rgba(%s,%s,%s,%s)' % (qc.red(),qc.green(),qc.blue(),qc.alpha())))
    except:
        col = mapnik.Color(str('rgb(%s,%s,%s)' % (qc.red(),qc.green(),qc.blue())))
    return col

def get_cap(cap):
    """ Turn a Qt Line Cap enum into a Mapnik one.
    """
    # TODO - convert into a dictionary dispatch
    # with proper default/fallback
    if cap == Qt.SquareCap:
        return mapnik.line_cap.SQUARE_CAP
    if cap == Qt.FlatCap:
        return mapnik.line_cap.BUTT_CAP
    else:
        return mapnik.line_cap.ROUND_CAP

def get_join(join):
    """ Turn a Qt Line Join enum into a Mapnik one.
    """
    # TODO - convert into a dictionary dispatch
    # with proper default/fallback
    if join == Qt.BevelJoin:
        return mapnik.line_join.BEVEL_JOIN
    elif join == Qt.RoundJoin:
        return mapnik.line_join.ROUND_JOIN
    else:
        return mapnik.line_join.MITER_JOIN
    # not sure what this one does...
    #return mapnik.line_join.MITER_REVERT_JOIN

def extent_string(e):
    """ Return a bbox string from a QGIS extent rectangle."""
    return str('%s,%s,%s,%s' % (e.xMinimum(),e.yMinimum(),e.xMaximum(),e.yMaximum()))

def extent_tuple(e):
    """ Return a bbox tuple from a QGIS extent rectangle."""
    return (e.xMinimum(),e.yMinimum(),e.xMaximum(),e.yMaximum())

def unique_filter(attr, low, idx, filter_type):
    """ Return a Mapnik filter expression string based on a single value.
    """
    d = {'attr':attr,'low':low}
    if low and filter_type == QVariant.String:
        expr = "[%(attr)s] = '%(low)s'" % d
    # TODO support more Qtype checking...
    elif is_number(str(low)) or low == 0:
        expr = "[%(attr)s] = %(low)s" % d
    elif not low and not low == 0:
        expr = "not [%(attr)s] <> ''" % d
    else:
        raise TypeError('unknown field value type: type=%s,val=%s,low=%s,filter_type=%s' % (type(attr),attr,low,filter_type))
    return unicode(expr)


def graduated_filter(attr, low, upp, idx, filter_type):
    """ Return a Mapnik filter expression string based on an upper and lower value pair.
    """
    d = {'attr':attr,'upp':upp,'low':low}
    if idx == 0:
       d['threshold'] = '>='
    else:
       d['threshold'] = '>'
    if low and upp:
        expr = "[%(attr)s] %(threshold)s %(low)s and [%(attr)s] <= %(upp)s" % d
    elif low:
        expr = "[%(attr)s] %(threshold)s %(low)s" % d            
    elif upp:
        expr = "[%(attr)s] <= %(upp)s" % d
    return unicode(expr)   

def to_wld(mapnik_map, x_rotation=0.0, y_rotation=0.0):
    """ Generate a World File string from a mapnik::Map."""
    extent = mapnik_map.envelope()
    pixel_x_size = (extent.maxx - extent.minx)/mapnik_map.width
    pixel_y_size = (extent.maxy - extent.miny)/mapnik_map.height
    upper_left_x_center = extent.minx + 0.5 * pixel_x_size + 0.5 * x_rotation
    upper_left_y_center = extent.maxy + 0.5 * (pixel_y_size*-1) + 0.5 * y_rotation
    wld_string = '''%.10f\n%.10f\n%.10f\n-%.10f\n%.10f\n%.10f\n''' % (
        pixel_x_size,
        y_rotation,
        x_rotation,
        pixel_y_size,
        upper_left_x_center,
        upper_left_y_center)
    return wld_string
                
class RasterRules(object):
    """ Class to contruct a set of Rules for QGIS Rasters.
    
    TODO: this is very preliminary and work needs to be done to:
    
     * try to sync colors closer
     * track down the cause of slight shifts between Mapnik and QGIS
    
    """
    def __init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor):
        self.layer = layer
        self.opacity = opacity
        self.scale_factor = scale_factor
        self.base_path = base_path
        self.raster_scale_factor = raster_scale_factor
    
    @property
    def raster_type(self):
        # TODO - need to investigate more QGIS types
        rt = self.layer.rasterType()
        if rt == QgsRasterLayer.Palette:
            return 'palette'
        elif rt == QgsRasterLayer.Multiband:
            return 'multiband'
        else: #GrayOrUndefined
            return 'undefined'
        
    def set(self,min_scale=None,max_scale=None):    
        r_list = []
        r = mapnik.Rule()
        if min_scale:
            r.min_scale = min_scale
        if max_scale:
            r.max_scale = max_scale
        raster = mapnik.RasterSymbolizer()
        raster.opacity = self.opacity
        #raster.scaling = 'bilinear'
        #raster.mode = 'normal'
        r.symbols.append(raster)
        r_list.append(r)
        return r_list

class BaseVectorRules(object):
    def __init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor,background):
        self.layer = layer
        self.opacity = opacity
        self.scale_factor = scale_factor
        self.base_path = base_path
        self.raster_scale_factor = raster_scale_factor
        self.background = background
        if hasattr(layer,'isUsingRendererV2') and layer.isUsingRendererV2():
            self.v2 = True
        else:
            self.v2 = False
    
    @property
    def point(self):
        return self.layer.geometryType() == QGis.Point

    @property
    def line(self):
        return self.layer.geometryType() == QGis.Line

    @property
    def polygon(self):
        return self.layer.geometryType() == QGis.Polygon

    @property
    def fields(self):
        return self.layer.dataProvider().fields()

    def features(self):
        # http://doc.qgis.org/head/qgsvectorlayer_8cpp-source.html
        if self.v2:
            # http://trac.osgeo.org/qgis/changeset/12347
            # http://trac.osgeo.org/qgis/changeset/12357
            return None # QgsFeatureRendererV2::fieldNameIndex not exposed?
        idx = self.layer.renderer().classificationAttributes()[0]
        return self.layer.dataProvider().uniqueValues(idx)


    # todo, merge filter_type and filter_name
    @property
    def filter_type(self):
        if self.v2:
            attr = self.layer.rendererV2.usedAttributes()[0]
            return type(get_variant_value(attr))
        attr = self.layer.renderer().classificationAttributes()
        field = self.fields[attr[-1]]
        return field.type()
    
    def filter_name(self,symbol):
        if self.layer.renderer().needsAttributes():
            attr = self.layer.renderer().classificationAttributes()
            
            # todo
            # if scale or rotation are not -1 then len(attr) > 1
            #scale_attr = symbol.scaleClassificationField()
            
            # if multiple, then the one that is used to filter seems
            # to be last.... vs the attr used to rotate,scale,etc
            # but we likely need to pass symbol to figure this out
            fld = self.fields[attr[-1]]
            return unicode(fld.name())

    def get_filter(self,sym,idx):
        filter_attr = self.filter_name(sym)
        filter_type = self.filter_type
        if self.symbolization in ("Unique Value","singleSymbol"):
            expr = unique_filter(filter_attr,unicode(sym.lowerValue()),idx,filter_type)
        elif self.symbolization in ("Graduated Symbol","graduatedSymbol","categorizedSymbol"):
            expr = graduated_filter(filter_attr,unicode(sym.lowerValue()),unicode(sym.upperValue()),idx,filter_type)
        # TODO - we can't let unicode or other errors throw exceptions...
        if MAPNIK_VERSION >= 800:
            return mapnik.Expression(str(expr))
        else:
            return mapnik.Filter(str(expr))

    @property
    def symbolization(self):
        if self.v2:
            if self.layer.rendererV2:
                return self.layer.rendererV2.type()
        if self.layer.renderer(): # layers will no geometries can lack a renderer
            return self.layer.renderer().name()

    @property
    def symbols(self):
        # todo - http://trac.osgeo.org/qgis/changeset/12328
        return self.layer.renderer().symbols()
                
class VectorLabels(BaseVectorRules):
    def __init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor,background):
        BaseVectorRules.__init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor,background)
  
    @property
    def face_name(self):
        return "DejaVu Sans Bold"
    
    @property
    def label(self):
        return self.layer.label()
          
    @property
    def field_name(self):
        return unicode(self.label.labelField(self.label.LabelField()))
    
    @property
    def attr(self):
        return self.label.layerAttributes()
    
    def family(self):
        pass
        # TODO
        # a.family() Lucida Grande
    
    def set(self,min_scale=None,max_scale=None):
        r_list = []
        a = self.attr
        r = mapnik.Rule()
        if min_scale or max_scale:
            if min_scale:
                r.min_scale = min_scale
            if max_scale:
                r.max_scale = max_scale
        elif self.label.scaleBasedVisibility():
            # these scales don't map correctly at first glance
            # need to look closer at different pixel assumptions...
            pixel_factor = (90.1/72)
            r.min_scale = self.layer.minimumScale() * pixel_factor
            r.max_scale = self.layer.maximumScale() * pixel_factor
        # note mapnik labels appear bigger so we reduce the size....
        text_size = a.size() * self.scale_factor * .8
        fill = css_color(a.color())
        field_name = str(self.field_name)
        if not field_name:
            return []
        if MAPNIK_VERSION >= 800:
            name = mapnik.Expression("[%s]" % field_name)
        else:
            name = field_name
        text = mapnik.TextSymbolizer(name,self.face_name,int(text_size),fill)
        if a.bufferEnabled():
            col = css_color(a.bufferColor())
            # silently fail with mapnik versions pre 0.6.0
            # which may not support alpha colors this same way
            try:
              col.a = int(.3*255) # force slighly transparent halos
            except:
              pass
            text.halo_fill = col
            text.halo_radius = int(a.bufferSize() * self.scale_factor) # float
        if a.borderWidth() > 0:
            text.halo_fill = css_color(a.borderColor())
        if a.multilineEnabled():
            text.wrap_width = 100 # better default?
        dx, dy = 0,0
        if self.line:
            # if the geometry is a line, then lets wrap text along it
            text.label_placement = mapnik.label_placement.LINE_PLACEMENT
            # put test above line rather than directly on top
            dy = text_size * .7
            # throw out labels if they are on sharp turns
            text.max_char_angle_delta = 20
            # make sure not to place duplicate labels to close together
            text.label_spacing = 50
            text.minimum_distance = 200
        elif self.point:
            # don't let points overlap with other stuff
            text.allow_overlap = False
            # to try to get more placed, displace text off of point geometry
            # this will push text to the upper right
            # todo - need to bump up more for Cairo text output as Cairo is slightly larger
            dx, dy = text_size * .8,text_size * .8  
        else:
            text.allow_overlap = False
        
        try:
            text.displacement(dx,dy)
        except:
            text.displacement = (dx,dy)            

        # defaults...
        if dy == 0:
            text.vertical_alignment = mapnik.vertical_alignment.MIDDLE
        elif dy > 0:
            text.vertical_alignment = mapnik.vertical_alignment.BOTTOM            
        elif dy < 0:
            text.vertical_alignment = mapnik.vertical_alignment.TOP
        text.avoid_edges = True

        # available in Mapnik >=0.7.0
        # only for point placment
        #try:
            #text.wrap_character = ';'
            #text.line_spacing = 20
            #text.character_spacing = 20
            # applies to both lines and points
            #text.text_transform = mapnik.text_transform.UPPERCASE
        #except: pass
        
        r.symbols.append(text)
        r_list.append(r)
        return r_list
               
class VectorRules(BaseVectorRules):
    def __init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor,background):
        self.idx = 0
        BaseVectorRules.__init__(self,layer,opacity,scale_factor,base_path,raster_scale_factor,background)
        
    def set(self,min_scale=None,max_scale=None):
        if self.symbolization is None:
            return []
        if self.symbolization == 'Single Symbol':
            # here we assume adjacent polygons and up the gamma slighly based on the
            # wild guess that this is desirable
            gamma = 0.7
            return [self.single(self.symbols[0],min_scale=min_scale,max_scale=max_scale,gamma=gamma)]
        elif self.symbolization == 'Graduated Symbol':
            return self.values(self.symbols,min_scale=min_scale,max_scale=max_scale)
        elif self.symbolization == 'Unique Value':
            return self.values(self.symbols,min_scale=min_scale,max_scale=max_scale)
        elif self.symbolization == 'Continuous Color':
            return self.continuous_values(self.symbols,min_scale=min_scale,max_scale=max_scale)
        elif self.symbolization == 'OSM':
            return self.values(self.symbols,min_scale=min_scale,max_scale=max_scale)
        else:
            raise Exception("not implemented yet")
            
    def point_sym(self,symbol,color=None):
        # what out for sketchy QImages!
        # http://blog.qgis.org/node/74
        color = QColor()
        width_scale = 1
        scale = 1
        rotation = 0
        allow_overlap = False
        filename = None
        path_expression = None
        #symbol.pointSize()
        attr = symbol.scaleClassificationField()
        # This nasty code will be replaced once Mapnik has proper
        # support for dynamically scaling SVG symbols....
        if attr >= 0 and MAPNIK_VERSION >= 800:
            allow_overlap = True
            if self.idx == 0:
                features = self.layer.dataProvider().uniqueValues(attr)
                vals = []
                for item in features:
                    field_value = get_variant_value(item)
                    #print '%.25f' % field_value
                    if item.type() == QVariant.Double:
                        if int(item.toDouble()[0]) == item.toDouble()[0]:
                            # check if it is actually an int
                            mapnik_field_value = int(item.toDouble()[0])
                        else:
                            # okay, its actually a float...
                            # due dirty things to try to match Mapnik's float precision
                            m_float = '%.25f' % round(item.toByteArray().toFloat()[0],13)
                            decimals = m_float.split('.')[1][:13]
                            mapnik_field_value = '%s.%s' % (m_float.split('.')[0],decimals)
                    else:
                        mapnik_field_value = field_value # assuming int
                    
                    if not field_value in vals:
                        vals.append(field_value)
                        # mapnik uses 13 digits after decimal
                        # QGIS rounds to 10 when saving image...
                        filename = 'sym_%s.png' % mapnik_field_value
                        if self.base_path:
                            filename = os.path.join(self.base_path,filename)
                        scale_value = math.sqrt(math.fabs(field_value))
                        #if not os.path.exists(filename):
                            # todo, find a way to match color to filter name
                        q_im = symbol.getPointSymbolAsImage(width_scale,False,color,scale_value,rotation,self.raster_scale_factor)
                        q_im.save(filename)
            
            fld = self.fields[attr]
            if self.base_path:
                path_expression = os.path.join(self.base_path,'sym_[%s].png' % str(fld.name()))
            else:
                path_expression = 'sym_[%s].png' % str(fld.name())
            self.idx += 1
        else:
            try:
                q_im = symbol.getPointSymbolAsImage(width_scale,False,color,scale,rotation,self.raster_scale_factor)
            except:
                # http://doc.qgis.org/stable/qgssymbol_8cpp-source.html#l00315
                q_im = symbol.getPointSymbolAsImage(width_scale,False,color)
                        
            if self.base_path:
                filename = os.path.join(self.base_path,'sym_%s.png' % self.idx)
            else:
                filename = 'sym_%s.png' % self.idx
            self.idx += 1
            q_im.save(filename)
        
        #q_im.hasAlphaChannel()
        if MAPNIK_VERSION >= 800:
            point = mapnik.PointSymbolizer(mapnik.PathExpression(path_expression or filename))
        else:
            w,h = q_im.width(),q_im.height()
            point = mapnik.PointSymbolizer(filename,'png',w,h)
        point.opacity = self.opacity
        point.allow_overlap = allow_overlap
        return point
    
    def line_sym(self,symbol,color=None,m2q_factor=.7,dashes=True):
        # make mapnik line width thicker
        w = symbol.lineWidth() + m2q_factor
        p = symbol.pen()
        stroke = mapnik.Stroke()
        stroke.width = w * self.scale_factor
        if color:
            stroke.color = color
        else:
            stroke.color = css_color(symbol.color())
        stroke.opacity = self.opacity
        # make mapnik dash spacing longer
        dash_array = [i + m2q_factor for i in p.dashPattern()]
        if dashes and dash_array:
            stroke.add_dash(*dash_array[:2])
            if len (dash_array) > 2:
                stroke.add_dash(*dash_array[2:4])
            if len (dash_array) > 4:
                stroke.add_dash(*dash_array[4:6])
        # to reduce verbosity in XML output only respect
        # user choices or QT defaults (more likely)
        # for endstyles with linear geometries
        # as Mapnik defaults are different than QT
        if self.line:
            stroke.line_join = get_join(p.joinStyle())
            stroke.line_cap = get_cap(p.capStyle())
        line = mapnik.LineSymbolizer(stroke)
        return line

    def polygon_pattern_sym(self,symbol):
        file_ = str(symbol.customTexture())
        im = QImage(symbol.customTexture())
        if MAPNIK_VERSION >= 800:
            poly_pattern = mapnik.PolygonPatternSymbolizer(mapnik.PathExpression(file_))
        else:
            poly_pattern = mapnik.PolygonPatternSymbolizer(file_,'png',im.width(),im.height())
        return poly_pattern
        
    def polygon_sym(self,symbol,color=None,gamma=None):
        if color:
            poly = mapnik.PolygonSymbolizer(color)
        else:
            poly = mapnik.PolygonSymbolizer(css_color(symbol.fillColor()))
        poly.fill_opacity = self.opacity
        if gamma:
            poly.gamma = gamma
        return poly

    def continuous_values(self,syms,min_scale=None,max_scale=None):
        r_list = []
        low = syms[0].lowerValue()
        high = syms[1].lowerValue()
        #high = syms[1].upperValue()
        s = syms[0]
        s.setLowerValue('%s' % low)
        s.setUpperValue('%s' % high)
        # should we be using fillColor() ??
        start = css_color(syms[1].color())
        end = css_color(syms[0].color())
        
        ramp = Ramp(start,end,float(low),float(high))
        filter_type = self.filter_type
        features = self.features()
        for idx, feat in enumerate(features):
            val = get_variant_value(feat)
            color_tuple = ramp.color_for_value(float(val))
            color = mapnik.Color('rgb(%s,%s,%s)' % color_tuple[:3])
            r = self.single(s,color=color,outline=False,min_scale=min_scale,max_scale=max_scale)
            filter_attr = self.filter_name(s)
            filt = unique_filter(filter_attr,unicode(val),idx,filter_type)
            if filt:
                r.filter = mapnik.Filter(str(filt))
                r_list.append(r)
        
        # currently not exposed in python...
        # need to check for renderer->drawPolygonOutline()
        # default to no outlines...
        #if self.polygon:
        #    r = mapnik.Rule()
        #    r.symbols.append(self.line_sym(s,mapnik.Color('black')))
        #    r_list.append(r)
        return r_list
            
    def values(self,syms,min_scale=None,max_scale=None):
        r_list = []
        for idx, s in enumerate(syms):
            r = self.single(s,min_scale=min_scale,max_scale=max_scale,gamma=.65)
            filt = self.get_filter(s,idx)
            if filt:
                r.filter = filt
                r_list.append(r)
        if not len(syms):
            r_list.append(self.default())
        return r_list
    
    def default(self):
        r = mapnik.Rule()
        if self.point:
            r.symbols.append(mapnik.PointSymbolizer())
        elif self.line:
            r.symbols.append(mapnik.LineSymbolizer())
        elif self.polygon:
            r.symbols.append(mapnik.PolygonSymbolizer())
        return r
                
    def single(self,sym,color=None,outline=True,min_scale=None,max_scale=None,gamma=None):
        r = mapnik.Rule()
        if min_scale:
            r.min_scale = min_scale
        if max_scale:
            r.max_scale = max_scale
        if self.point:
            if not sym.pen().style() == Qt.NoPen or not sym.brush().style() == Qt.NoBrush:
                r.symbols.append(self.point_sym(sym,color))
        elif self.line:
            if not sym.pen().style() == Qt.NoPen:
                r.symbols.append(self.line_sym(sym,color))
        if self.polygon:
            if not sym.brush().style() == Qt.NoBrush:
                # hmm qgis 1.60 reports customTexture() when it should not
                # TODO - how to detect a texture rather than solid fill?
                #if sym.customTexture():
                #    r.symbols.append(self.polygon_pattern_sym(sym))
                #else:
                r.symbols.append(self.polygon_sym(sym,color,gamma=gamma))
                #if sym.pen().style() == Qt.NoPen:
                #    # no outlines, so apply gamm fix if gamma is set
                #    # which it will be if we are using single symbolization
                #    r.symbols.append(self.polygon_sym(sym,color,gamma=gamma))
                #else:
                #    # ignore the gamma because we have outlines
                #    r.symbols.append(self.polygon_sym(sym,color,gamma=None))
            if not sym.pen().style() == Qt.NoPen and outline:
                primary = self.line_sym(sym,color)
                if len(sym.pen().dashPattern()):
                    # TODO - expose option to alternate the inverse of the line color
                    # as the background as that can look sharp
                    # for now we'll use the background color if not filling polygon
                    # and the polygon color if we are filling
                    if sym.brush().style() == Qt.NoBrush:
                        color = self.background
                    else:
                        color = css_color(sym.fillColor())
                    underneath_line = self.line_sym(sym,color=color,dashes=False)
                    r.symbols.append(underneath_line)
                r.symbols.append(primary)
        # todo - need to avoid attaching an empty rule.
        return r

class LayerAdaptor(object):
    def __init__(self,parent,layer,scale_factor,base_path,raster_scale_factor,background):
        self.parent = parent
        self.layer = layer
        self.scale_factor = scale_factor
        self.base_path = base_path
        self.raster_scale_factor = raster_scale_factor
        self.background = background
        self.vector_lyr = (layer.type() == layer.VectorLayer)
        self.raster_lyr = (layer.type() == layer.RasterLayer)
        self._datasource = None

    def message(self,msg):
        QMessageBox.information(self.parent.iface.mainWindow(),"Warning",QString(msg))
        return

    @property
    def opacity(self):
        return self.layer.getTransparency()/255.0

    @property
    def extent(self):
        # not predicatable...
        #return self.layer.dataProvider().extent()
        return self.layer.extent()

    def uri(self):
        return QgsDataSourceURI(self.layer.dataProvider().dataSourceUri())

    @property
    def provider(self):
        return str(self.layer.dataProvider().name())
        #return str(self.layer.providerType())

    def datasource(self):
        global INCOMPATIBLE_LAYER_WARNING
        if self.raster_lyr:           
            if self.is_geotiff and 'gdal' not in MAPNIK_PLUGINS:
                if self.layer.width() > 10000 or self.layer.height() > 10000:
                    # gdal is not available, but the user should install it
                    # rather than trying to read such a large file with the
                    # raster datasource without overviews support...
                    return self.gdal()
                return self.raster()
            if '.sqlite' in self.source:
                if 'rasterlite' in MAPNIK_PLUGINS:
                    # nope, we have no way to get the table name...
                    #return self.rasterlite()
                    pass
            if not self.layer.usesProvider():
                # grass rasters and some tif's do not have a provider method!
                # others?
                # TODO - needs testing
                return self.gdal()                
            elif self.provider == 'grass':
                # TODO - needs testing
                return self.gdal()
            # disable WMS support since it is
            # not working well yet...
            elif self.provider == 'wms':
                 pass
            #    return self.wms()
            else:
                return self.gdal()                
        elif self.vector_lyr:
            # grass: http://bitbucket.org/springmeyer/quantumnik/issue/14/
            if self.provider == 'postgres':
                return self.postgis()
            elif self.provider == 'grass':
                return self.grass_vector()
            elif self.provider == 'ogr':
                if self.is_shape and not os.path.isdir(self.source):
                    # re: the isdir() call.. zipped shapefiles when 
                    # extracted are often dumped into 'folder.shp'
                    # so instead of trying to reach inside, lets
                    # just let ogr read the files, which it can
                    # from within an arbitrary directory
                    return self.shape()
                return self.ogr()
            elif self.provider == 'spatialite':
                return self.sqlite()
            elif self.provider == 'osm':
                return self.osm()
        # kludgy - will get hit if any one kind of datasource is unsupported
        # goal is to support most all datasources, so hopefully we can remove this soon
        # with format specific errors where there exist incompatibilities
        if INCOMPATIBLE_LAYER_WARNING:
            self.message('You will see this warning once per session... Quantumnik does not currently support "%s" datasources. You will need to uncheck any unsupported layers before rendering with Quantumnik otherwise the resulting map will be blank. File an issue at https://github.com/springmeyer/quantumnik if you would like to request support for this format...' % self.provider)
            INCOMPATIBLE_LAYER_WARNING = False
    
    @property
    def sub_layer_name(self):
        # hack! QGIS needs to provide ogr sublayers as easy
        # to fetch attributes
        sub_layers = self.layer.dataProvider().subLayers()
        if sub_layers:
            # TODO: predictably handle more than one sublayer
            
            # can't recall for what layer type this
            # code below actually worked for!
            #for sl in sub_layers:
            #    if str(self.layer.name()) in sl:
            #        return str(self.layer.name())
            
            layer_string = None
            # support gpx data
            for sl in sub_layers:
                if str(self.layer.name()).lower() in sl:
                    layer_string = str(sl)
                    break
            
            # TODO: handle more than one sublayer
            if not layer_string:
                layer_string = str(sub_layers[0])
            # wms sublayers appear to be just the
            # layer name - this is trouble!
            if self.provider == 'wms':
                return layer_string
            # other layers via ogr look like:
            # LayerIndex : LayerName : FeatureCount : GeometryType
            # 0:ARC:30849:LineString
            pattern = r'\d+:(.+):\d+:'
            return re.findall(pattern, layer_string)[0]
        else:
            # likely will not match ogr name
            # but worth the try...
            return str(self.layer.name())

    # TODO - avoid duplicate style/layer names...
    #@property
    #def unique_name(self):
    #    # ugly, but a reliably unique name
    #    return str(self.layer.getLayerID())

    def name(self):
        # this is the 'display name' that can be be set in the layers general options
        name = str(self.layer.name())
        # shapefiles return the full path which is too verbose
        if os.path.sep in name:
            name = os.path.basename(name)
        try:
            return str(os.path.splitext(name)[0])
        except:
            return str(name)
        
    @property
    def has_labels(self):
        if self.vector_lyr:
            return self.layer.hasLabelsEnabled()
        return False

    def pk_field_name(self):
        return self.layer.dataProvider().fields()[0].name()
    
    #@check_plug
    def rasterlite(self):
        pass
    
    #@check_plug
    def osm(self):
        #/Users/spring/projects/haiti/latest.osm?type=point&tag=name&style=/Applications/Qgis.app/Contents/Resources/python/plugins/osm/styles/small_scale.style
        osm_file = str(self.source.split('?')[0])
        sqlite_osm_db = '%s.db' % osm_file
        if os.path.exists(sqlite_osm_db):
            # >>> print r.classificationAttributes()
            #[2] 
            params = {}
            params['file'] = sqlite_osm_db
            if 'polygon' in str(self.source):
                params['table'] = '(Select * from way where closed = 1) as t'
            elif 'line' in str(self.source):
                params['table'] = '(Select * from way where closed = 0) as t' 
            elif 'point' in str(self.source):
                # need to turn lat,lon into geometry...          
                params['table'] = 'way'
            params['geometry_field'] = 'wkb'
            #params['wkb_format'] = str('spatialite')
            #params['use_spatial_index'] = True
            params['key_field'] = 'i'
            params['extent'] = extent_string(self.extent)
            return mapnik.SQLite(**params)
        return mapnik.Osm(file=osm_file)

    @check_plug        
    def shape(self):
        # bug in mapnik prevents multipoint reading using shape plugin
        # so, we'll use ogr plugin instead for < Mapnik 0.7.0 and request
        # exploded geoms to workaround a bug in ogr driver
        # http://trac.mapnik.org/ticket/458
        # http://doc.qgis.org/head/classQGis.html#8da456870e1caec209d8ba7502cceff7
        if MAPNIK_VERSION:
            if self.layer.wkbType() == QGis.WKBPoint25D:
                # http://trac.mapnik.org/ticket/504
                if not MAPNIK_VERSION >= 800:
                    return self.ogr()
            if self.layer.wkbType() == QGis.WKBMultiPoint:
                if MAPNIK_VERSION >= 700:
                    return mapnik.Shapefile(file=self.source)
                else:
                    return self.ogr(multiple_geometries=True)        
            if MAPNIK_VERSION > 600:
                # Mapnik 0.6.0 and greater supports creating 
                # shapefile datasources using the '.shp' extension
                return mapnik.Shapefile(file=self.source)
        elif self.layer.wkbType() == QGis.WKBMultiPoint:
           return self.ogr(multiple_geometries=True) 
        return mapnik.Shapefile(file=self.source.replace('.shp',''))

    @check_plug
    def ogr(self,multiple_geometries=False):
        return mapnik.Ogr(file=self.source,layer=self.sub_layer_name,multiple_geometries=multiple_geometries)
    
    def wms(self):
        params = {}
        params['format'] = 'image/png'
        params['layers'] = self.sub_layer_name
        params['styles'] = ''
        # currently can't get at actual version being requested...
        params['version'] = '1.1.1'
        params['url'] = self.source + '?'
        params['srs'] = self.authid()
        params['projection'] = self.authid()
        e = self.layer.extent()
        params['ulx'] = e.xMinimum() # flipped
        params['uly'] = e.yMaximum()
        params['llx'] = e.xMaximum() # flipped
        params['lly'] = e.yMinimum()
        wms_template = '''<GDAL_WMS>
            <Service name="WMS">
              	<Version>%(version)s</Version>
              	<ServerUrl>%(url)s</ServerUrl>
              	<!--<SRS>%(srs)s</SRS>-->
                <!--<ImageFormat>%(format)s</ImageFormat>-->
                <Layers>%(layers)s</Layers>
                <Styles>%(styles)s</Styles>
            </Service>
            <DataWindow>
                  <UpperLeftX>%(ulx)s</UpperLeftX>
                  <UpperLeftY>%(uly)s</UpperLeftY>
                  <LowerRightX>%(llx)s</LowerRightX>
                  <LowerRightY>%(lly)s</LowerRightY>
                  <SizeX>2949120</SizeX>
                  <SizeY>1474560</SizeY>
            </DataWindow>
            <Projection>%(projection)s</Projection>
            <OverviewCount>12</OverviewCount>
            <BlockSizeX>256</BlockSizeX>
            <BlockSizeY>256</BlockSizeY>
            <BandsCount>3</BandsCount>
        </GDAL_WMS>
        ''' % params
        print wms_template
        (handle, service_description) = tempfile.mkstemp('.xml', 'qnik_gdal_wms-')
        os.close(handle)
        open(service_description, 'w').write(wms_template)
        return mapnik.Gdal(file=service_description)

    @check_plug    
    def postgis(self):
        params = {}
        # a bunch of stuff exposed in 1.1
        # http://trac.osgeo.org/qgis/changeset/10581
        uri = self.uri()
        # dbname='aussie' user='postgres' table="osm_au_polygon" (way) sql=
        # uri = QgsDataSourceURI(iface.mapCanvas().layer(0).dataProvider().dataSourceUri())
        # quote potentially changed in http://trac.osgeo.org/qgis/changeset/13336
        params['extent'] = extent_string(self.extent)
        params['estimate_extent'] = False
        params['user'] = str(uri.username())
        if uri.schema():
            table = '"%s"."%s"' % (str(uri.schema()),str(uri.table()))
        else:
            table = '"%s"' % str(uri.table())

        if uri.sql():
            where = str(uri.sql())
            params['table'] = '(SELECT * FROM %s WHERE %s) as %s' % (table,where,'"%s"' % str(uri.table()))
        else:
            params['table'] = table

        if hasattr(uri, 'database'):
            params['dbname'] = str(uri.database())
        else:
            params['dbname'] = str(uri.connectionInfo().split(' ')[0].split('=')[1])
        if hasattr(uri, 'database'):
            if uri.password():
                params['password'] = str(uri.password()) 
        if hasattr(uri, 'host'):
            if uri.host():
                params['host'] = str(uri.host())
        if hasattr(uri, 'port'):
            if uri.port():
                params['port'] = str(uri.port())
        params['geometry_field'] = str(uri.geometryColumn())
        if hasattr(self.layer,'crs'):
            params['srid'] = self.layer.crs().postgisSrid()
        else:
            params['srid'] = self.layer.srs().postgisSrid() # deprecated
        return mapnik.PostGIS(**params)

    @check_plug
    def sqlite(self):
        params = {}
        uri = self.uri()
        params['file'] = str(uri.database())
        params['table'] = str(uri.table())
        params['geometry_field'] = str(uri.geometryColumn())
        params['wkb_format'] = str('spatialite')
        params['use_spatial_index'] = True
        # this assumption is likely going to fall apart!
        # how can we predictably get the PK name?
        params['key_field'] = str(self.pk_field_name())
        params['extent'] = extent_string(self.extent)
        return mapnik.SQLite(**params)
    
    @check_plug
    def gdal(self):
        # todo - check for GDAL version and determine whether
        # to used shared opening option
        #return mapnik.Gdal(file=self.source,shared=True)
        return mapnik.Gdal(file=self.source)

    def grass_vector(self):
        # we are going to connect through OGR...
        # since the grass provider does not provide
        # a descent connection string to pass to ogr
        # this is going to be ugly and error prone
        # http://gdal.org/ogr/drv_grass.html
        src = os.path.normpath(self.source)
        parts = src.split(os.path.sep)
        grass_base = os.path.sep.join(parts[:len(parts)-2])
        dataset = parts[-2:-1][0]
        v_file = os.path.join(grass_base,'vector',dataset,'head')
        layer = parts[-1:][0].split('_')[0]
        return mapnik.Ogr(file=v_file,layer=layer)
        
    @check_plug
    def raster(self):
        d= {}
        d['file'] = self.source
        lox,loy,hix,hiy = extent_tuple(self.extent)
        d['lox'] = lox
        d['loy'] = loy
        d['hix'] = hix
        d['hiy'] = hiy
        return mapnik.Raster(**d)
        
    @property
    def source(self):
        src = str(self.layer.source())
        # hack to support e00 files that
        # seem to tack on the layername after
        # a pipe - others do perhaps as well?
        if '|' in src:
            return src.split('|')[0]
        return src

    @property
    def is_shape(self):
        return self.source.endswith('shp')

    @property
    def is_geotiff(self):
        # TODO need to check for strips or tiles...
        return self.source.endswith('tiff') or self.source.endswith('tif')

    @property
    def srs(self):
        srid = self.authid()
        if not srid:
            if hasattr(self.layer,'crs'):
                return str(self.layer.crs().toProj4())
            return str(self.layer.srs().toProj4()) # deprecated
        try:
            # if the proj4 library that Mapnik
            # is linked against knows about this
            # projection by epsg code then lets
            # use that to assign the srs to layers
            return mapnik.Projection('+init=%s' % srid).params()
        except:
            try:
                proj_init = '+init=epsg:%s' % self.layer.srs().epsg() #deprecated
                return mapnik.Projection(proj_init).params()
            except:
                # otherwise initialize with the proj literal
                if hasattr(self.layer,'crs'):
                    return str(self.layer.crs().toProj4())
                return str(self.layer.srs().toProj4())

    def authid(self):
        if hasattr(self.layer,'crs'):
            self.layer.srs = self.layer.crs
        
        if hasattr(self.layer.srs(),'authid'):
            return str(self.layer.srs().authid())    
        # deprecated
        return str('EPSG:%s' % self.layer.srs().epsg())

    def get_style(self,min_scale=None,max_scale=None):
        # todo - detect pen/brush = false
        # e.g...
        # if not self.has_symbology:
        # return None
        
        style = mapnik.Style()
        if self.vector_lyr:
            rules = VectorRules(self.layer,self.opacity,self.scale_factor,self.base_path,self.raster_scale_factor,self.background)
            style.rules.extend(rules.set(min_scale=min_scale,max_scale=max_scale))
        elif self.raster_lyr:
            rules = RasterRules(self.layer,self.opacity,self.scale_factor,self.base_path,self.raster_scale_factor)
            style.rules.extend(rules.set(min_scale=min_scale,max_scale=max_scale))
        else:
            raise Exception('Type not yet supported')
        return style
   
    def get_label_style(self):
        style = mapnik.Style()
        rules = VectorLabels(self.layer,self.opacity,self.scale_factor,self.base_path,self.raster_scale_factor,self.background)
        style.rules.extend(rules.set())
        return style
    
    def is_valid(self):
        ds = self.datasource()
        if ds:
            self._datasource = ds
            return True
        return False

    def get_min_max_scales(self):
        pixel_factor = (90.1/72)
        min_ = self.layer.minimumScale() * pixel_factor
        max_ = self.layer.maximumScale() * pixel_factor
        return min_,max_
    
    @property
    def scale_based(self):
        return self.layer.hasScaleBasedVisibility()

    def to_mapnik(self,name=None,scale_based=True):
        if not name:
            name = self.name()
        lyr = mapnik.Layer(name,self.srs)
        if self._datasource:
            lyr.datasource = self._datasource
        else:
            lyr.datasource = self.datasource()
        if scale_based and self.scale_based:
            lyr.minzoom,lyr.maxzoom = self.get_min_max_scales()
        #lyr.queryable = True
        #lyr.clear_label_cache = True
        #lyr.active
        #lyr.abstract
        #lyr.title
        # add extra attributes
        #lyr.style = self.style
        #if self.vector_lyr:
            #lyr.label_style = self.get_label_style
        #else:
        #    lyr.label_style = None
        return lyr

class EasyCanvas(object):
    def __init__(self,parent,canvas,resolution=90.714):
        self.parent = parent
        self.canvas = canvas
        self.resolution = resolution
        self.width = canvas.width()
        self.height = canvas.height()
        self.normal_pixel = 90.714
        self.base_path =  tempfile.gettempdir()
        # TODO - expose as user options...
        self.merge_duplicate_layers = True

    def message(self,msg):
        QMessageBox.information(self.parent.iface.mainWindow(),"Warning",QString(msg))
        return
    
    def raster_scale_factor(self):
        if hasattr(self.canvas.mapRenderer(),'rendererContext'):
            return self.canvas.mapRenderer().rendererContext().scaleFactor()
        else: ## QGIS < 1.2
            return 2.2
    
    @property
    def scale_factor(self):
        return self.resolution/self.normal_pixel
        
    @property
    def dimensions(self):
        w = self.width * self.scale_factor
        h = self.height * self.scale_factor
        return (int(w),int(h))

    @property
    def background(self):
        return css_color(self.canvas.backgroundBrush().color())
        
    @property
    def srs(self):
        ren = self.canvas.mapRenderer()
        srs_obj = None
        if not ren.hasCrsTransformEnabled():
            # if we are not projecting on the fly...
            if self.canvas.layerCount() == 1:
                # check if we only have one layer and if so
                # we make the map projection the same as this
                # layers projection because in many circumstances
                # QGIS will actually report the default WGS84 srs
                # when QGIS is actually ignoring its presence because
                # it is not reprojecting on the fly...
                if hasattr(self.canvas.layer(0),'crs'):
                    srs_obj = self.canvas.layer(0).crs()
                else:
                    srs_obj = self.canvas.layer(0).srs()
            elif self.canvas.layerCount() > 1:
                # otherwise do a clumsy check to see if all layers
                # are actually in the same projection and if so
                # then use the projection of the first layer
                first = self.canvas.layer(0)
                if hasattr(first,'crs'):
                    first.srs = first.crs
                if not False in [first.srs() == self.canvas.layer(i).srs() for i in xrange(self.canvas.layerCount())]:
                    if hasattr(first,'crs'):
                        srs_obj = self.canvas.layer(0).crs()
                    else:
                        srs_obj = self.canvas.layer(0).srs()
        # otherwise we are reprojecting on the fly and we'll set
        # the map projection to what QGIS actually reports
        if not srs_obj:
            if hasattr(self.canvas.mapRenderer(),'destinationCrs'):
                srs_obj = self.canvas.mapRenderer().destinationCrs()
            else:
                srs_obj = self.canvas.mapRenderer().destinationSrs()


        srid = ''
        if hasattr(srs_obj,'authid'):
            srid = str(srs_obj.authid())

        try:
            # if the proj4 library that Mapnik
            # is linked against knows about this
            # projection by epsg code then lets
            # use that to assign the srs to layers
            return mapnik.Projection('+init=%s' % srid).params()
        except:
            try:
                proj_init = '+init=epsg:%s' % srs_obj.epsg() #deprecated
                return mapnik.Projection(proj_init).params()
            except:
                # otherwise initialize with the proj literal
                if hasattr(srs_obj,'crs'):
                    return str(srs_obj.toProj4())
                return str(srs_obj.toProj4())

    def to_mapnik(self,m=None):
        global INCOMPATIBLE_RENDERER_WARNING

        if m:
            m.remove_all()
        else:
            m = mapnik.Map(*self.dimensions)
        m.srs = self.srs
        #m.background = mapnik.Color('transparent')
        # now that we are drawing on our own mapnik
        # qCanvas, we should respect the background
        # color of the main canvas..
        m.background = self.background        

        layer_count = self.canvas.layerCount()
        
        # if not layers, return an empty map
        if not layer_count:
            return m
        
        # switch the layer order
        layer_list = range(layer_count)
        layer_list.reverse()
        #### TODO - proper datasource uniqueness-based dup detection
        #has_dupes = False
        #all_names = [self.canvas.layer(i).name() for i in layer_list]
        #if not len(all_names) == len(set(all_names)):
        #    has_dupes = True
        warn_about_v2 = False
        l_names = []
        labeled_layer_cache = []
        idx = 1
        for i in layer_list:
            # get the qgis layer
            q_lyr = self.canvas.layer(i)
            if hasattr(q_lyr,'isUsingRendererV2') and q_lyr.isUsingRendererV2():
                # we don't support symbology-ng yet, so skip layer
                warn_about_v2 = True
                continue
            
            # wrap the qgis layer in the adapter class to we can quickly
            # make sense of it for turning into a mapnik layer
            lyr_a = LayerAdaptor(self.parent,
                                  q_lyr,
                                  self.scale_factor,
                                  self.base_path,
                                  self.raster_scale_factor(),
                                  self.background
                                  )
            # if the layer can be turned into a mapnik datasource...
            if lyr_a.is_valid():
                # get a simple, non unique layer name
                name = lyr_a.name()
                # unless this layer is a duplicate we'll plan to 
                # add it as a mapnik layer
                add_layer = True
                if name in l_names:
                    # we have a duplicate layer (by name)
                    # thus we need to assign a unique name
                    
                    #### TODO  make dup sniffing smarter and not 
                    #### name dependent but datasource specific
                    #### to allow for renaming in the qgis legend
                    #### without breaking this trickery
                    
                    name += str(idx)
                    idx += 1
                    # if duplicate layers are to be interpreted as the user wishing to 
                    # be able to create multiple styles per mapnik layer...
                    # then we want to 'merge' the layers by aggregating all possible styles
                    # against on mapnik layer, thus skipping any duplicate qgis layers
                    if self.merge_duplicate_layers:
                        add_layer = False
                l_names.append(lyr_a.name())
                # create the style name from the unique layer name
                style_name = '%s_style' % name
                # the style may be created at different points below
                # so we'll make it None for now...
                style_obj = None
                # TODO - the mapnik layer may not need to be created if it has a style with pen/brush = false
                m_lyr = lyr_a.to_mapnik(name)
                if add_layer:
                    # if we have a new layer to add
                    if self.merge_duplicate_layers:# and has_dupes:
                        # overwrite mapnik layer ignoring any possible scale visibility
                        # applied to the layer because we are going to aggregate all styles
                        # and apply the visibility to the mapnik style rules instead
                        #### TODO - implement when we have a better way of detecting dups
                        pass
                        #m_lyr = lyr_a.to_mapnik(name,scale_based=False)
                    # attach the style by name
                    m_lyr.styles.append(style_name)
                    # attach the layer to the map
                    
                else:
                    # get existing layer and append new style
                    exists = [l for l in m.layers if l.name == lyr_a.name()]
                    if len(exists) == 1:
                        existing_layer = exists[0]
                        existing_layer.styles.append(style_name)
                        if lyr_a.scale_based:
                            # apply layers scales to style's rules
                            #### TODO - implement when we have a better way of detecting dups
                            pass
                            #min_scale,max_scale = lyr_a.get_min_max_scales()
                            #style_obj = lyr_a.get_style(min_scale=min_scale,max_scale=max_scale)
                if not style_obj:
                    # don't apply layer scales to style rules
                    # just get the style as it is
                    style_obj = lyr_a.get_style()
                
                # finally, add this layers style to the map
                m.append_style(style_name,style_obj)
                
                # now focus on text labels
                if lyr_a.has_labels:
                    label_name, label_obj = '%s_labels' % name, lyr_a.get_label_style()
                    if layer_count == 1:
                        # if only one layer is in the project then there is no need
                        # apply to a separate layer and we can avoid cacheing
                        # so place right now on the current layer which should exist
                        # because it cannot be a duplicate
                        
                        # TODO - foreseeably the layer could have not main styles (brush,pen = false)
                        # and we only want to create labels
                        #if not m_lyr:
                        #    m_lyr = lyr_a.to_mapnik(name)
                        m_lyr.styles.append(label_name)
                        m.append_style(label_name,label_obj)
                    elif layer_count > 1:
                        # now, for all layers with labels, create a new, duplicate
                        # mapnik layer with a text style, and cache it to enable
                        # appending it at the end to ensure the labels are on top
                        m_label_lyr = lyr_a.to_mapnik('%s_label_overlay' % name)
                        # note: layer based scale visibility left unchanged for label layers...
                        m_label_lyr.styles.append(label_name)
                        m.append_style(label_name,label_obj)
                        labeled_layer_cache.append(m_label_lyr)
                
                # finally append any new layer
                if add_layer:
                    m.layers.append(m_lyr)

        # attach any cached label layers last (on top)
        for layer in labeled_layer_cache:
            m.layers.append(layer)
                
        if warn_about_v2 and INCOMPATIBLE_RENDERER_WARNING:
            self.message('The "New Symbology" plugin in QGIS is not yet supported by Quantumnik and layers using it will be rendered blank. See http://bitbucket.org/springmeyer/quantumnik/issue/23 to track progress.')
            INCOMPATIBLE_RENDERER_WARNING = False
        return m

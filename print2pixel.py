#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Dane Springmeyer (dbsgeo [ -a- ] gmail.com)"
__copyright__ = "Copyright 2008, Dane Springmeyer"
__version__ = "0.0.1SVN"
__license__ = "GPLv2"

import optparse
import sys
import copy
import math
import platform

VERBOSE = False
ROUND_RESULT = True

POSTSCRIPT_PPI = 72.0 # dpi
OGC_PIXEL = 0.28 # mm
METERS_PER_DEGREE = 6378137 * 2 * math.pi/360
#PLOTTER_MAX_WIDTH = 36 # inches
#POWER_POINT_MAX_DIM = (36,56)
#MS_WORD_MAX_DIM = (11,17)

# use my default screen dimensions for now...
USE_MACBOOK_RESOLUTION = True

def ppi2mm_px_size(ppi):
  return (1.0/ppi)*25.4

def mm_px_size2ppi(pixel_size):
  return 1.0/(pixel_size/25.4)

POSTSCRIPT_PIXEL = ppi2mm_px_size(POSTSCRIPT_PPI) # mm 0.35277777777777775
OGC_PPI = mm_px_size2ppi(OGC_PIXEL) # 90.714285714285708 as 1 'dot'/.011 inches

def ppi2microns(ppi):
    """Convert ppi to µm
    """
    return 25400.0/ppi

# 76dpi (postcript) translates to a resolution of 334.21 microns
# http://www.cl.cam.ac.uk/~mgk25/metric-typo/
def microns2ppi(microns):
    """Convert µm to ppi
    """
    return 25400.0/microns

def error(E,msg):
  if __name__ == '__main__':
    sys.exit('// -- Error: %s' % msg)
  else:
    raise E(msg)

def msg(msg):
 global VERBOSE
 if VERBOSE:
   print msg

# Factors for converting to inches by division
# read this as 1 inch == unit value
inch_eq = {
  'in' : 1,
  'ft': 0.0833333333,
  'yd': 0.0277777778,
  'mi': 1.57828283e-5,
  'm': 0.0254,
  'dm': 0.254,
  'cm': 2.54,
  'mm': 25.4,
  'km': 2.54e-5,
  'um': 25400.0,
  'px': POSTSCRIPT_PPI,
  }
upper_inch_eq = dict([(k.upper(), v) for k, v in inch_eq.items()])

alias = {
  # Imperial
  'inch' : 'in',
  'inches' : 'in',
  'foot' : 'ft',
  'feet' : 'ft',
  'yard' : 'yd',
  'yards' : 'yd',
  'mile' : 'mi',
  'miles' : 'mi',
  # Metric
  'microns': 'um',
  'micrometer': 'um',
  'micrometres':'um',
  'µm':'um',
  'millimeter' : 'mm',
  'millimetre' : 'mm',
  'centimeter' : 'cm',
  'centimeters' : 'cm',
  'decimeter' : 'dm',
  'decimeters' : 'dm',
  'meter' : 'm',
  'meters' : 'm',
  'metre' : 'm',
  'metres' : 'm',
  'kilometer' : 'km',
  'kilometers' : 'km',
  'kilometre' : 'km',
  'kilometres' : 'km',
  }
upper_alias = dict([(k.upper(), v) for k, v in alias.items()])

# Paper sizes by name/shorthand
# in millimetres
iso = {
  # iso A series
  'A0': (841,1189),
  'A1': (594,841),
  'A2': (420,594),
  'A3': (297,420),
  'A4': (210,297),
  'A5': (148,210),
  'A6': (105,148),
  'A7': (74,105),
  'A8': (52,74),
  'A9': (37,52),
  'A10': (26,37),
  # iso B series
  'B0': (1000,1414),
  'B1': (707,1000),
  'B2': (500,707),
  'B3': (353,500),
  'B4': (250,353),
  'B5': (176,250),
  'B6': (125,176),
  'B7': (88,125),
  'B8': (62,88),
  'B9': (44,62),
  'B10': (31,44),
  # iso C series
  'C0': (917,1297),
  'C1': (648,917),
  'C2': (458,648),
  'C3': (324,458),
  'C4': (228,324),
  'C5': (162,229),
  'C6': (114.9,162),
  'C7': (88,114.9),
  'C8': (57,81),
  'C9': (40,57),
  'C10': (28,40),
  # DIN 476 (German)
  '4A0': (1682,2378),
  '2A0': (1189,1682),
  # SIS 014711 (Swiss)
  'G5': (169,239),
  'E5': (155,220),
  }

# Japanese
jis = {
  'J0': (1030,1456),
  'J1': (728,1030),
  'J2': (515,728),
  'J3': (364,515),
  'J4': (257,364),
  'J5': (182,257),
  'J6': (128,182),
  'J7': (91,128),
  'J8': (64,91),
  'J9': (45,64),
  'J10': (32,45),
  'J11': (22,32),
  'J12': (16,22),
  }

# inches
ansi = {
  'ANSI-A': (8.5,11),
  'ANSI-B': (11,17),
  'ANSI-C': (17,22),
  'ANSI-D': (22,34),  
  'ANSI-E': (34,44),
  }

# inches
north_america = {
  'letter': (8.5,11),
  'carta': (8.5,11),
  'legal': (8.5,14),
  'oficio': (8.5,14),
  'executive': (7.25,10.5),
  'tabloid': (11,17),
  'ledge': (17,11),
  'government-letter': (8,10.5),
  'chilean-legal': (8.5,13),
  'philippine-legal': (8.5,13),
  }

sizes = (
  (north_america,'in'),
  (iso,'mm'),
  (jis,'mm'),
  (ansi,'in'),
  )

size_dict = {}
size_dict.update(north_america)
size_dict.update(iso)
size_dict.update(jis)
size_dict.update(ansi)

def get_size_by_name(papername):
    """Return the units, width, and height of a given paper size.
    
    Supports lookup of ISO, Japanese, ANSI, and North American sizes.
    """
    u = h = w = None
    up,lo = papername.upper().strip('\'"'),papername.lower().strip('\'"')
    for size in sizes:      
      if size[0].has_key(lo):
        w,h = size[0][lo]
        u = size[1]
      elif size[0].has_key(up):
        w,h = size[0][up]
        u = size[1]
    if not w:
      error(AttributeError,'Could not find paper size of: %s' % papername)
    msg("%s size found, using unit: '%s'; width: '%s'; height: '%s'" % (papername.upper(),u,w,h))
    if u != 'in':
      factor = get_to_inch_factor(u)
      w,h = w/factor,h/factor
      # set u = 'in' since we're now forcing work in inches
      u = 'in'
      msg("%s equivalent in inches is: %s, %s" % (papername.upper(),w,h))
    else:
      msg("No 'to-inch' conversion needed, native paper size units are inches...")
    return u,w,h
    
def print_scale_relative_to_postscript(ppi,system_assumed_dpi=POSTSCRIPT_PPI):
    """Return the scale factor to reduce an image of a given ppi to print at intended resolution.
    
    Needed on systems where 72 ppi is assumed when an image lacks an embedded dpi/ppi exif tag.
    """
    # Is 96 dpi on win32 true?
    # Likely to hard to guess...
    if os.name == 'nt':
      system_assumed_dpi = 96.0
    elif platform.uname()[0] == 'Darwin': 
      pass # 72 assumed on mac os
    elif platform.uname()[0] == 'Linux':
      pass # need to check on linux...
    return system_assumed_dpi/ppi * 100.0

def get_to_inch_factor(unit):
    """Return the conversion factor for calculating an inch equivalent for a given unit.
    """
    if inch_eq.has_key(unit):
        return inch_eq[unit]
    elif upper_inch_eq.has_key(unit):
        return inch_eq[upper_inch_eq[unit]]
    elif alias.has_key(unit):
        return inch_eq[alias[unit]]
    elif upper_alias.has_key(unit):
        return inch_eq[upper_alias[unit]]
    else:
        error(AttributeError,'Unknown unit type: %s' % unit)

def get_px_screen_ppi(pixels_wide=1440,pixels_high=900,screen_width=15.4):
    """Return the actual pixels per inch for a given display resolution and width.
    """
    pixel_density = math.sqrt(pixels_wide**2 + pixels_high**2)/screen_width
    msg("Screen pixel density per inch (ppi): '%s'" % pixel_density)
    return pixel_density

def get_px_for_print_size(unit,print_w,print_h,print_res,res_unit):
    """Return the pixel width and height given a target print size and resolution.
    """
    # get the conversion factor to inches
    factor = get_to_inch_factor(unit)
    if not factor == 1:
      msg("Conversion factor to inches will be '%s' will be 'in = mm/%s'" % (unit,factor))
    # We accept ppi or pixel size in microns for now
    if res_unit == 'microns' or res_unit == 'micrometres' or res_unit == 'µm' or res_unit == 'um':
      # convert microns to inches since our print sizes
      # are going to be forced into inch units
      msg("Setting resolution using micrometres (µm)... to '%s' µm" % print_res)
      print_res = microns2ppi(print_res)
      msg("Micron value equivalent to '%s' ppi" % print_res)
    elif res_unit == 'inches' or res_unit == 'in' or res_unit == 'inch':
      microns = ppi2microns(print_res)
      msg("Setting resolution using inches... to '%s' ppi" % print_res)
      msg("Per inch resolution equivalent to pixel size of '%s' microns" % microns)
    else:
      error(AttributeError,'Unknown print resolution type: %s' % res_unit)
    px_w = print_w/factor*print_res
    px_h = print_h/factor*print_res
    return px_w,px_h

def get_pixels(unit,w,h,print_res=300,res_unit='inches',margin=0,layout=None,**kwargs):
    """Return the pixel width and height given a target resolution, margin, and layout.
    
    A wrapper around get_px_for_print_size() that handles margins and aspect ratio.
    """
    if margin:
      w,h = w-margin,h-margin
      msg("Margin requested, dimensions in '%s' now: %s,%s " % (unit,w,h))
    
    # Pass of to the function that does the real work
    px_w, px_h = get_px_for_print_size(unit,w,h,print_res,res_unit)
    if layout:
      dim = [px_w, px_h]
      dim_copy = copy.copy(dim)
      if layout == 'portrait':
        dim.sort()
        if dim_copy == dim:
          msg('Layout already of portrait orientation...')
        else:
          msg('Switched to Portrait type orientation...') 
        return tuple(dim)
      elif layout == 'landscape':
        dim.sort()
        dim.reverse()
        if dim_copy == dim:
          msg('Layout already of landscape orientation...')
        else:
          msg('Switched to Landscape type orientation...')          
        return tuple(dim)
    else:
      return px_w,px_h

def print_map_by_dimensions(params,**kwargs):
    """Return the pixels given user defined dimensions and units.
    """
    try:
      w,h,unit = params.split(',')
    except ValueError: # assume inches for now...
      unit = 'in'
      w,h = params.split(',')
    dx, dy = get_pixels(unit,float(w),float(h),**kwargs)
    if ROUND_RESULT:
      dx, dy = int(dx),int(dy)
    return dx, dy

def print_map_by_name(papername,**kwargs):
    """Return the pixels given a known, named paper size.
    """
    unit,w,h = get_size_by_name(papername)
    dx, dy = get_pixels(unit,float(w),float(h),**kwargs)
    if ROUND_RESULT:
      dx, dy = int(dx),int(dy)
    return dx, dy

parser = optparse.OptionParser(usage="""python print2pixel.py <papersize> [options]

Usage:
    $ python print2pixel.py tabloid -r 300 -u inches -l
    $ python print2pixel.py 3,7,in
    $ python print2pixel.py letter -u inches -r 76
    $ python print2pixel.py letter -u microns -r 334.21

""")

parser.add_option('-r', '--resolution',
    dest='print_res', type='float',
    help='Specify the desired resolution in ppi (pixels per inch) or microns (pixel size)')
parser.add_option('-u', '--units',
    dest='res_unit',
    help='Specify the resolution units as either inches or microns')
parser.add_option('-m', '--margin',
    dest='margin', type='float',
    help='Specify the a paper margin in the units of the paper size')
parser.add_option('-l', '--landscape',
    action='store_const', const='landscape', dest='layout',
    help='Force lanscape orientation')
parser.add_option('-p', '--portrait',
    action='store_const', const='portrait', dest='layout',
    help='Force portrait orientation')
parser.add_option('-v', '--VERBOSE', default=False,
    action='store_true', dest='VERBOSE',
    help='VERBOSE debug output')
parser.add_option('-n', '--norounding',
    action='store_false', dest='ROUND_RESULT', default=True,
    help='Do not return rounded integer result for pixel dimensions')
parser.add_option('-s', '--screen',
    action='store_const', const=True, dest='screen_res',
    help='Set the --resolution to the PPI of your screen (requires -w and -d flags)')
parser.add_option('-w', '--screenwidth',
    dest='screen_width', type='float',
    help='Screen width in inches')
parser.add_option('-d', '--displaypixels',
    dest='display_res',
    help='Display pixels as w,h')
parser.add_option('--render',
    action='store_const', const=True, dest='render',
    help='Render the result using a nik2img test mapfile')

if __name__ == '__main__':
    (options, args) = parser.parse_args()
    
    if len(args) < 1:
      sys.exit('\nPlease provide a named paper size or a triplet of dimensions and their unit, ie 8.5,11,in \n')
    else:
      size = args[0]
  
    if options.print_res and not options.res_unit:
      sys.exit('\nPlease provide a unit for the resolution value\n')

    if options.res_unit and not options.print_res:
      if not options.screen_res:
        sys.exit('\nPlease provide a resolution value in addition to the respective unit\n')
    
    if options.screen_res:
      if USE_MACBOOK_RESOLUTION:
        options.print_res = get_px_screen_density()
      elif not options.res_unit or not options.screen_width or not options.display_res:
        sys.exit('\nPlease provide a screen width in inches, and the display resolution\n')        
      else:
        try: 
          p_w, p_h = map(float,options.display_res.split(','))
        except ValueError:
          sys.exit('Problem setting the display resolution\n')
        options.print_res = get_px_screen_density(pixels_wide=p_w,pixels_high=p_h,screen_width=options.screen_width)

    if options.VERBOSE:
      VERBOSE = True
      print

    if not options.ROUND_RESULT:
      ROUND_RESULT = False

    kwargs = {}
    for k,v in vars(options).items():
      if v != None:
       kwargs[k] = v

    if len(size.split(','))> 1:
      dx, dy = print_map_by_dimensions(size, **kwargs)
    else:
      dx, dy = print_map_by_name(size, **kwargs)

    print '// --  Pixel Width: %s' % dx
    print '// --  Pixel Height: %s' % dy

    if options.render:
      import nik2img
      m = nik2img.Map('tests/mapfile.xml','w-%s_h-%s.png' % (dx,dy),width=dx,height=dy)
      m.open()


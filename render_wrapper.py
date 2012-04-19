# -*- coding: utf-8 -*-

import os

try:
    import mapnik2 as mapnik
except ImportError:
    import mapnik

def render_to_file(mapnik_map,output,format):
    
    # get the full path for a users directory
    if '~' in output:
        output = os.path.expanduser(output)
        
    # mapnik won't create directories so
    # we have to make sure they exist first...
    dirname = os.path.dirname(output)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    # render out to the desired format
    if format in ('png','png256','jpeg') or (hasattr(mapnik,'mapnik_version') and mapnik.mapnik_version() >= 700):
        try:
            mapnik.render_to_file(mapnik_map,output,format)
        except Exception, e:
            return (False,e)            
    else:
        try:
            import cairo
            surface = getattr(cairo,'%sSurface' % format.upper())(output,mapnik_map.width,mapnik_map.height)
            mapnik.render(mapnik_map, surface)
            surface.finish()
        except Exception, e:
            return (False,e)
    return (True,mapnik_map)
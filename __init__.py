# -*- coding: utf-8 -*-

from quantumnik import Quantumnik, NAME

def name():
  return NAME

def description():
  return "Mapnik integration with QGIS"

def version():
  return "Version 0.4.1"

def qgisMinimumVersion():
  return "1.8" # Kore, ideally 1.1.0 (Pan)

def author():
  return "Dane Springmeyer"

def email():
  return "dane@dbsgeo.com"

def homepage():
  return "https://github.com/springmeyer/quantumnik"

def classFactory(iface):
  return Quantumnik(iface)

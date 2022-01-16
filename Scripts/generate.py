#!/usr/bin/env python3
import math
import datetime
import argparse
import zipfile
import shutil
from geopy import point
from numpy.core.multiarray import concatenate
import urllib3
import argparse
import numpy as np
import requests
import re
import os
import fnmatch
import xml.etree.ElementTree as xtree
import pandas as pd
import urllib3
import xmlschema
import pyproj
from datetime import date
from defusedxml import defuse_stdlib
from bs4 import BeautifulSoup
from colorama import Fore, Style
from time import time, ctime
from alive_progress import alive_bar
from pykml import parser
from shapely.geometry import MultiPoint
from shapely.geometry import Point as sPoint
from shapely.ops import transform
from functools import partial
from geopy.point import Point
from geopy.distance import geodesic
from xml.dom import minidom

work_dir = os.path.dirname(__file__)

class Airac:
    '''Class for general functions relating to AIRAC'''

    def __init__(self):
        # First AIRAC date following the last cycle length modification
        startDate = "2019-01-02"
        self.baseDate = date.fromisoformat(str(startDate))
        # Length of one AIRAC cycle
        self.cycleDays = 28

    def initialise(self, dateIn=0):
        # Calculate the number of AIRAC cycles between any given date and the start date
        if dateIn:
            inputDate = date.fromisoformat(str(dateIn))
        else:
            inputDate = date.today()

        # How many AIRAC cycles have occured since the start date
        diffCycles = (inputDate - self.baseDate) / datetime.timedelta(days=1)
        # Round that number down to the nearest whole integer
        numberOfCycles = math.floor(diffCycles / self.cycleDays)

        return numberOfCycles

    def currentCycle(self):
        # Return the date of the current AIRAC cycle
        numberOfCycles = self.initialise()
        numberOfDays = numberOfCycles * self.cycleDays + 1
        return self.baseDate + datetime.timedelta(days=numberOfDays)

    def nextCycle(self):
        # Return the date of the next AIRAC cycle
        numberOfCycles = self.initialise()
        numberOfDays = (numberOfCycles + 1) * self.cycleDays + 1
        return self.baseDate + datetime.timedelta(days=numberOfDays)

    def url(self, next=0):
        # Return a generated URL based on the AIRAC cycle start date
        baseUrl = "https://www.aurora.nats.co.uk/htmlAIP/Publications/"
        if next:
            baseDate = self.nextCycle() # if the 'next' variable is passed, generate a URL for the next AIRAC cycle
        else:
            baseDate = self.currentCycle()

        basePostString = "-AIRAC/html/eAIP/"
        return baseUrl + str(baseDate) + basePostString

class Webscrape:
    '''Class to scrape data from the given AIRAC eAIP URL'''

    def __init__(self, next=0):
        cycle = Airac()
        self.cycle = cycle.currentCycle()
        self.cycleUrl = cycle.url()
        self.country = "EG"

    def get_table_soup(self, uri):
        """Parse the given table into a beautifulsoup object"""
        address = self.cycleUrl + uri

        http = urllib3.PoolManager()
        error = http.request("GET", address)
        if (error.status == 404):
            return 404

        page = requests.get(address)
        return BeautifulSoup(page.content, "lxml")

    def parse_ad01_data(self):
        """Parse the data from AD-0.1"""
        print("Parsing "+ self.country +"-AD-0.1 data to obtain ICAO designators...")

        # create the table
        dfColumns = ['icao_designator','verified','location','elevation','name','magnetic_variation']
        df = pd.DataFrame(columns=dfColumns)

        # scrape the data
        getAerodromeList = self.get_table_soup(self.country + "-AD-0.1-en-GB.html")

        # process the data
        listAerodromeList = getAerodromeList.find_all("h3")
        barLength = len(listAerodromeList)
        with alive_bar(barLength) as bar: # Define the progress bar
            for row in listAerodromeList:
                # search for aerodrome icao designator and name
                getAerodrome = re.search(rf"({self.country}[A-Z]{{2}})(\n[\s\S]{{7}}\n[\s\S]{{8}})([A-Z]{{4}}.*)(\n[\s\S]{{6}}<\/a>)", str(row))
                if getAerodrome:
                    # Place each aerodrome into the DB
                    dfOut = {'icao_designator': str(getAerodrome[1]),'verified': 0,'location': 0,'elevation': 0,'name': str(getAerodrome[3]),'magnetic_variation': 0}
                    df = df.append(dfOut, ignore_index=True)
                bar()
        return df

    def parse_ad02_data(self, dfAd01):
        """Parse the data from AD-2.x"""
        print("Parsing "+ self.country +"-AD-2.x data to obtain aerodrome data...")
        df_columns_rwy = ['icao_designator','runway','location','elevation','bearing','length']
        df_rwy = pd.DataFrame(columns=df_columns_rwy)

        df_columns_srv = ['icao_designator','callsign_type','frequency']
        df_srv = pd.DataFrame(columns=df_columns_srv)

        # Select all aerodromes in the database
        barLength = len(dfAd01.index)
        with alive_bar(barLength) as bar: # Define the progress bar
            for index, row in dfAd01.iterrows():
                aeroIcao = row['icao_designator']
                # Select all runways in this aerodrome
                getRunways = self.get_table_soup(self.country + "-AD-2."+ aeroIcao +"-en-GB.html")
                if getRunways !=404:
                    print("  Parsing AD-2 data for " + aeroIcao)
                    aerodromeAd0202 = getRunways.find(id=aeroIcao + "-AD-2.2")
                    aerodromeAd0212 = getRunways.find(id=aeroIcao + "-AD-2.12")
                    aerodromeAd0218 = getRunways.find(id=aeroIcao + "-AD-2.18")

                    # Find current magnetic variation for this aerodrome
                    aerodromeMagVar = self.search("([\d]{1}\.[\d]{2}).([W|E]{1})", "TAD_HP;VAL_MAG_VAR", str(aerodromeAd0202))
                    pM = Geo.plusMinus(aerodromeMagVar[0][1])
                    floatMagVar = pM + aerodromeMagVar[0][0]

                    # Find lat/lon/elev for aerodrome
                    aerodromeLat = re.search(r'(Lat: )(<span class="SD" id="ID_[\d]{7}">)([\d]{6})([N|S]{1})', str(aerodromeAd0202))
                    aerodromeLon = re.search(r"(Long: )(<span class=\"SD\" id=\"ID_[\d]{7}\">)([\d]{7})([E|W]{1})", str(aerodromeAd0202))
                    aerodromeElev = re.search(r"(VAL_ELEV\;)([\d]{1,4})", str(aerodromeAd0202))

                    full_location = self.sct_location_builder(
                        aerodromeLat.group(3),
                        aerodromeLon.group(3),
                        aerodromeLat.group(4),
                        aerodromeLon.group(4)
                        )

                    dfAd01.at[index, 'verified'] = 1
                    dfAd01.at[index, 'magnetic_variation'] = str(floatMagVar)
                    dfAd01.at[index, 'location'] = str(full_location)
                    dfAd01.at[index, 'elevation'] = str(aerodromeElev[2])

                    # Find runway locations
                    aerodromeRunways = self.search("([\d]{2}[L|C|R]?)", "TRWY_DIRECTION;TXT_DESIG", str(aerodromeAd0212))
                    aerodromeRunwaysLat = self.search("([\d]{6}\.[\d]{2}[N|S]{1})", "TRWY_CLINE_POINT;GEO_LAT", str(aerodromeAd0212))
                    aerodromeRunwaysLong = self.search("([\d]{7}\.[\d]{2}[E|W]{1})", "TRWY_CLINE_POINT;GEO_LONG", str(aerodromeAd0212))
                    aerodromeRunwaysElev = self.search("([\d]{3}\.[\d]{1})", "TRWY_CLINE_POINT;VAL_ELEV", str(aerodromeAd0212))
                    aerodromeRunwaysBearing = self.search("([\d]{3}\.[\d]{2}.)", "TRWY_DIRECTION;VAL_TRUE_BRG", str(aerodromeAd0212))
                    aerodromeRunwaysLen = self.search("([\d]{3,4})", "TRWY;VAL_LEN", str(aerodromeAd0212))

                    for rwy, lat, lon, elev, brg, rwyLen in zip(aerodromeRunways, aerodromeRunwaysLat, aerodromeRunwaysLong, aerodromeRunwaysElev, aerodromeRunwaysBearing, aerodromeRunwaysLen):
                        # Add runway to the aerodromeDB
                        latSplit = re.search(r"([\d]{6}\.[\d]{2})([N|S]{1})", str(lat))
                        lonSplit = re.search(r"([\d]{7}\.[\d]{2})([E|W]{1})", str(lon))

                        loc = self.sct_location_builder(
                            latSplit.group(1),
                            lonSplit.group(1),
                            latSplit.group(2),
                            lonSplit.group(2)
                            )

                        df_rwy_out = {'icao_designator': str(aeroIcao),'runway': str(rwy),'location': str(loc),'elevation': str(elev),'bearing': str(brg.rstrip('°')),'length': str(rwyLen)}
                        # print(df_rwy_out)
                        df_rwy = df_rwy.append(df_rwy_out, ignore_index=True)

                    # Find air traffic services
                    aerodromeServices = self.search("(APPROACH|GROUND|DELIVERY|TOWER|DIRECTOR|INFORMATION|RADAR|RADIO|FIRE|EMERGENCY)", "TCALLSIGN_DETAIL", str(aerodromeAd0218))
                    serviceFrequency = self.search("([\d]{3}\.[\d]{3})", "TFREQUENCY", str(aerodromeAd0218))

                    last_srv = ''
                    if len(aerodromeServices) == len(serviceFrequency):
                        # Simple aerodrome setups with 1 job, 1 frequency
                        for srv, frq in zip(aerodromeServices, serviceFrequency):
                            if str(srv) is None:
                                s_type = last_srv
                            else:
                                s_type = str(srv)
                                last_srv = s_type
                            df_srv_out = {'icao_designator': str(aeroIcao),'callsign_type': s_type,'frequency': str(frq)}
                            df_srv = df_srv.append(df_srv_out, ignore_index=True)
                    else:
                        # Complex aerodrome setups with multiple frequencies for the same job
                        print(Fore.BLUE + "    Aerodrome " + aeroIcao + " has a complex comms structure" + Style.RESET_ALL)
                        for row in aerodromeAd0218.find_all("span"):
                            # get the full row and search between two "TCALLSIGN_DETAIL" objects
                            table_row = re.search(r"(APPROACH|GROUND|DELIVERY|TOWER|DIRECTOR|INFORMATION|RADAR|RADIO|FIRE|EMERGENCY)", str(row))
                            if table_row is not None:
                                callsign_type = table_row.group(1)
                            freq_row = re.search(r"([\d]{3}\.[\d]{3})", str(row))
                            if freq_row is not None:
                                frequency = str(freq_row.group(1))
                                if frequency != "121.500": # filter out guard frequencies
                                    df_srv_out = {'icao_designator': str(aeroIcao),'callsign_type': callsign_type,'frequency': frequency}
                                    df_srv = df_srv.append(df_srv_out, ignore_index=True)
                else:
                    print(Fore.RED + "Aerodrome " + aeroIcao + " does not exist" + Style.RESET_ALL)
                bar()
        return [dfAd01, df_rwy, df_srv]

    def parse_enr016_data(self, dfAd01):
        """Parse the data from ENR-1.6"""
        print("Parsing "+ self.country + "-ENR-1.6 data to obtan SSR code allocation plan")
        dfColumns = ['start','end','depart','arrive', 'string']
        df = pd.DataFrame(columns=dfColumns)

        webpage = self.get_table_soup(self.country + "-ENR-1.6-en-GB.html")
        getDiv = webpage.find("div", id = "ENR-1.6.2.6")
        getTr = getDiv.find_all('tr')
        barLength = len(getTr)
        with alive_bar(barLength) as bar: # Define the progress bar
            for row in getTr:
                getP = row.find_all('p')
                if len(getP) > 1:
                    text = re.search(r"([\d]{4})...([\d]{4})", getP[0].text) # this will just return ranges and ignore all discreet codes in the table
                    if text:
                        start = text.group(1)
                        end = text.group(2)

                        # create an array of words to search through to try and match code range to destination airport
                        locArray = getP[1].text.split()
                        for loc in locArray:
                            strip = re.search(r"([A-Za-z]{3,10})", loc)
                            if strip:
                                dep = "EG\w{2}"
                                # search the dataframe containing icao_codes
                                name = dfAd01[dfAd01['name'].str.contains(strip.group(1), case=False, na=False)]
                                if len(name.index) == 1:
                                    dfOut = {'start': start,'end': end,'depart': dep,'arrive': name.iloc[0]['icao_designator'],'string': strip.group(1)}
                                    df = df.append(dfOut, ignore_index=True)
                                elif strip.group(1) == "RAF" or strip.group(1) == "Military" or strip.group(1) == "RNAS" or strip.group(1) == "NATO":
                                    dfOut = {'start': start,'end': end,'depart': dep,'arrive': 'Military','string': strip.group(1)}
                                    df = df.append(dfOut, ignore_index=True)
                                elif strip.group(1) == "Transit":
                                    dfOut = {'start': start,'end': end,'depart': dep,'arrive': locArray[2],'string': strip.group(1)}
                                    df = df.append(dfOut, ignore_index=True)
                bar()
        return(df)

    def parse_enr02_data(self):
        dfColumns = ['name', 'callsign', 'frequency', 'boundary', 'upper_fl', 'lower_fl']
        df_fir = pd.DataFrame(columns=dfColumns)
        df_uir = pd.DataFrame(columns=dfColumns)
        df_cta = pd.DataFrame(columns=dfColumns)
        df_tma = pd.DataFrame(columns=dfColumns)

        print("Parsing "+ self.country +"-ENR-2.1 Data (FIR, UIR, TMA AND CTA)...")
        getData = self.get_table_soup(self.country + "-ENR-2.1-en-GB.html")

        # create a list of complex airspace areas with the direction of the arc for reference later on
        dfColumns = ['area', 'number', 'direction']
        complex_areas = pd.DataFrame(columns=dfColumns)
        row = 0
        complex_search_data = getData.find_all("p") # find everything enclosed in <p></p> tags
        complex_len = len(complex_search_data)
        while row < complex_len:
            title = re.search(r"id=\"ID_[\d]{8,10}\"\>([A-Z]*)\s(FIR|CTA|TMA|CTR)\s([0-9]{0,2})\<", str(complex_search_data[row]))
            if title:
                print_title = f"{str(title.group(1))} {str(title.group(2))} {str(title.group(3))}"

                direction = re.findall(r"(?<=\s)(anti-clockwise|clockwise)(?=\s)", str(complex_search_data[row+1]))
                if direction:
                    area_number = 0
                    for d in direction:
                        ca_out = {'area': print_title, 'number': str(area_number), 'direction': str(d)}
                        complex_areas = complex_areas.append(ca_out, ignore_index=True)
                        area_number += 1
                    row += 1
            row += 1
        complex_areas.to_csv(f'{work_dir}\\DataFrames\Enr02-CW-ACW-Helper.csv')

        searchData = getData.find_all("span")
        barLength = len(searchData)
        airspace = False
        row = 0
        last_arc_title = False
        arc_counter = 0
        space = []
        loop_coord = False
        first_callsign = False
        first_freq = False
        with alive_bar(barLength) as bar: # Define the progress bar
            while row < barLength:
                # find an airspace
                title = re.search(r"TAIRSPACE;TXT_NAME", str(searchData[row]))
                coords = re.search(r"(?:TAIRSPACE_VERTEX;GEO_L(?:AT|ONG);)([\d]{4})", str(searchData[row]))
                callsign = re.search(r"TUNIT;TXT_NAME", str(searchData[row]))
                freq = re.search(r"TFREQUENCY;VAL_FREQ_TRANS", str(searchData[row]))
                arc = re.search(r"TAIRSPACE_VERTEX;VAL_RADIUS_ARC", str(searchData[row]))

                if title:
                    # get the printed title
                    print_title = re.search(r"\>(.*)\<", str(searchData[row-1]))
                    if print_title:
                        # search for FIR / UIR* / CTA / TMA in the printed title *removed as same extent of FIR in UK
                        airspace = re.search(r"(FIR|CTA|TMA|CTR)", str(searchData[row-1]))
                        if airspace:
                            df_in_title = str(print_title.group(1))
                        loop_coord = True
 
                if (callsign) and (first_callsign is False):
                    # get the first (and only the first) printed callsign
                    print_callsign = re.search(r"\>(.*)\<", str(searchData[row-1]))
                    if print_callsign:
                        callsign_out = print_callsign.group(1)
                        first_callsign = True
                
                if (freq) and (first_freq is False):
                    # get the first (and only the first) printed callsign
                    print_frequency = re.search(r"\>(1[1-3]{1}[\d]{1}\.[\d]{3})\<", str(searchData[row-1]))
                    if print_frequency:
                        frequency = print_frequency.group(1)
                        first_freq = True

                if arc:
                    # what to do with "thence clockwise by the arc of a circle"
                    radius = re.search(r"\>([\d]{1,2})\<", str(searchData[row-1]))

                    # check to see if this a series, if so then increment the counter
                    if df_in_title == str(last_arc_title):
                        arc_counter += 0
                    else:
                        arc_counter == 0
                    
                    # is this going to be a clockwise or anti-clockwise arc?
                    complex_areas = pd.read_csv(f'{work_dir}\\DataFrames\\Enr02-CW-ACW-Helper.csv', index_col=0)
                    cacw = complex_areas.loc[(complex_areas["area"].str.match(df_in_title)) & (complex_areas["number"] == arc_counter)]
                    cacw = cacw['direction'].to_string(index=False)
                    print(cacw)
                    if cacw == "clockwise":
                        cacw = 1
                    elif cacw == "anti-clockwise":
                        cacw = 2

                    # work back through the rows to identify the start lat/lon
                    count_back = 2 # start countback from 2
                    start_lon = None
                    start_lat = None
                    while start_lon == None:
                        start_lon = re.search(r"\>([\d]{6,7})(E|W)\<", str(searchData[row-count_back]))
                        count_back += 1
                    while start_lat == None:
                        start_lat = re.search(r"\>([\d]{6,7})(N|S)\<", str(searchData[row-count_back]))
                        count_back += 1
                    
                    # work forward to find the centre point and end lat/lon
                    count_forward = 1
                    end_lat = None
                    end_lon = None
                    mid_lat = None
                    mid_lon = None
                    while mid_lat == None:
                        mid_lat = re.search(r"\>([\d]{6,7})(N|S)\<", str(searchData[row+count_forward]))
                        count_forward += 1
                    while mid_lon == None:
                        mid_lon = re.search(r"\>([\d]{6,7})(E|W)\<", str(searchData[row+count_forward]))
                        count_forward += 1
                    while end_lat == None:
                        end_lat = re.search(r"\>([\d]{6,7})(N|S)\<", str(searchData[row+count_forward]))
                        count_forward += 1
                    while end_lon == None:
                        end_lon = re.search(r"\>([\d]{6,7})(E|W)\<", str(searchData[row+count_forward]))
                        count_forward += 1
                    
                    # convert from dms to dd
                    start_dd = self.dms2dd(start_lat[1], start_lon[1], start_lat[2], start_lon[2])
                    mid_dd = self.dms2dd(mid_lat[1], mid_lon[1], mid_lat[2], mid_lon[2])
                    end_dd = self.dms2dd(end_lat[1], end_lon[1], end_lat[2], end_lon[2])

                    arc_out = self.generate_semicircle(float(mid_dd[0]), float(mid_dd[1]), float(start_dd[0]), float(start_dd[1]), float(end_dd[0]), float(end_dd[1]), cacw)
                    for coord in arc_out:
                        space.append(coord)
                    
                    # store the last arc title to compare against
                    last_arc_title = str(print_title.group(1))

                if coords:
                    loop_coord = False
                    # get the coordinate
                    print_coord = re.findall(r"\>([\d]{6,7})(N|S|E|W)\<", str(searchData[row-1]))
                    if print_coord: 
                        space.append(print_coord[0])
 
                if (loop_coord) and (space != []):
                    def coord_to_table(last_df_in_title, callsign_out, frequency, output):
                        df_out = {
                            'name': last_df_in_title,
                            'callsign': callsign_out,
                            'frequency': str(frequency),
                            'boundary': str(output),
                            'upper_fl': '000',
                            'lower_fl': '000'
                            }
                        return df_out
                    
                    output = self.getBoundary(space, last_df_in_title)
                    if airspace:
                        # for FIRs do this
                        if last_airspace.group(1) == "FIR":
                            df_fir_out = coord_to_table(last_df_in_title, callsign_out, frequency, output)
                            df_fir = df_fir.append(df_fir_out, ignore_index=True)
                        # for UIRs do this - same extent as FIR
                        #if last_airspace.group(1) == "UIR":
                        #    df_uir_out = {'name': last_df_in_title,'callsign': callsign_out,'frequency': str(frequency), 'boundary': str(output), 'upper_fl': '000', 'lower_fl': '000'}
                        #    df_uir = df_uir.append(df_uir_out, ignore_index=True)
                        # for CTAs do this
                        if last_airspace.group(1) == "CTA":
                            df_cta_out = coord_to_table(last_df_in_title, callsign_out, frequency, output)
                            df_cta = df_cta.append(df_cta_out, ignore_index=True)
                        if last_airspace.group(1) == "TMA":
                            df_tma_out = coord_to_table(last_df_in_title, callsign_out, frequency, output)
                            df_tma = df_tma.append(df_tma_out, ignore_index=True)
                        space = []
                        loop_coord = True
                        first_callsign = False
                        first_freq = False

                if airspace:
                    last_df_in_title = df_in_title
                    last_airspace = airspace
                bar()
                row += 1
        df_uir = df_fir # UIR is same extent as FIR
        return [df_fir, df_uir, df_cta, df_tma]

    def parse_enr03_data(self, section):
        dfColumns = ['name', 'route']
        dfEnr03 = pd.DataFrame(columns=dfColumns)
        print("Parsing "+ self.country +"-ENR-3."+ section +" data to obtain ATS routes...")
        getENR3 = self.get_table_soup(self.country + "-ENR-3."+ section +"-en-GB.html")
        listTables = getENR3.find_all("tbody")
        barLength = len(listTables)
        with alive_bar(barLength) as bar: # Define the progress bar
            for row in listTables:
                getAirwayName = self.search("([A-Z]{1,2}[\d]{1,4})", "TEN_ROUTE_RTE;TXT_DESIG", str(row))
                getAirwayRoute = self.search("([A-Z]{3,5})", "T(DESIGNATED_POINT|DME|VOR|NDB);CODE_ID", str(row))
                printRoute = ''
                if getAirwayName:
                    for point in getAirwayRoute:
                        printRoute += str(point[0]) + "/"
                    dfOut = {'name': str(getAirwayName[0]), 'route': str(printRoute).rstrip('/')}
                    dfEnr03 = dfEnr03.append(dfOut, ignore_index=True)
                bar()
        return dfEnr03

    def parse_enr04_data(self, sub):
        dfColumns = ['name', 'type', 'coords', 'freq']
        df = pd.DataFrame(columns=dfColumns)
        print("Parsing "+ self.country +"-ENR-4."+ sub +" Data (RADIO NAVIGATION AIDS - EN-ROUTE)...")
        getData = self.get_table_soup(self.country + "-ENR-4."+ sub +"-en-GB.html")
        listData = getData.find_all("tr", class_ = "Table-row-type-3")
        barLength = len(listData)
        with alive_bar(barLength) as bar: # Define the progress bar
            for row in listData:
                # Split out the point name
                id = row['id']
                name = id.split('-')

                # Find the point location
                lat = self.search("([\d]{6}[\.]{0,1}[\d]{0,2}[N|S]{1})", "T", str(row))
                lon = self.search("([\d]{7}[\.]{0,1}[\d]{0,2}[E|W]{1})", "T", str(row))
                pointLat = re.search(r"([\d]{6}(\.[\d]{2}|))([N|S]{1})", str(lat))
                pointLon = re.search(r"([\d]{7}(\.[\d]{2}|))([W|E]{1})", str(lon))

                if pointLat:
                    fullLocation = self.sct_location_builder(
                        pointLat.group(1),
                        pointLon.group(1),
                        pointLat.group(3),
                        pointLon.group(3)
                    )

                    if sub == "1":
                        # Do this for ENR-4.1
                        # Set the navaid type correctly
                        if name[1] == "VORDME":
                            name[1] = "VOR"
                        #elif name[1] == "DME": # prob don't need to add all the DME points in this area
                        #    name[1] = "VOR"

                        # find the frequency
                        freq_search = self.search("([\d]{3}\.[\d]{3})", "T", str(row))
                        freq = pointLat = re.search(r"([\d]{3}\.[\d]{3})", str(freq_search))

                        # Add navaid to the aerodromeDB
                        dfOut = {'name': str(name[2]), 'type': str(name[1]), 'coords': str(fullLocation), 'freq': freq.group(1)}
                    elif sub == "4":
                        # Add fix to the aerodromeDB
                        dfOut = {'name': str(name[1]), 'type': 'FIX', 'coords': str(fullLocation), 'freq': '000.000'}

                    df = df.append(dfOut, ignore_index=True)
                bar()
        return df

    def parse_enr051_data(self):
        dfColumns = ['name', 'boundary', 'floor', 'ceiling']
        dfEnr05 = pd.DataFrame(columns=dfColumns)
        print("Parsing "+ self.country +"-ENR-5.1 data for PROHIBITED, RESTRICTED AND DANGER AREAS...")
        getENR5 = self.get_table_soup(self.country + "-ENR-5.1-en-GB.html")
        listTables = getENR5.find_all("tr")
        barLength = len(listTables)
        with alive_bar(barLength) as bar: # Define the progress bar
            for row in listTables:
                getId = self.search("((EG)\s(D|P|R)[\d]{3}[A-Z]*)", "TAIRSPACE;CODE_ID", str(row))
                getName = self.search("([A-Z\s]*)", "TAIRSPACE;TXT_NAME", str(row))
                getLoc = self.search("([\d]{6,7})([N|E|S|W]{1})", "TAIRSPACE_VERTEX;GEO_L", str(row))
                getUpper = self.search("([\d]{3,5})", "TAIRSPACE_VOLUME;VAL_DIST_VER_UPPER", str(row))
                #getLower = self.search("([\d]{3,5})|(SFC)", "TAIRSPACE_VOLUME;VAL_DIST_VER_LOWER", str(row))

                if getId:
                    for upper in getUpper:
                        up = upper
                    dfOut = {'name': str(getId[0][0]) + ' ' + str(getName[2]), 'boundary': self.getBoundary(getLoc, str(getId[0][0])), 'floor': 0, 'ceiling': str(up)}
                    dfEnr05 = dfEnr05.append(dfOut, ignore_index=True)

                bar()
        return dfEnr05

    def test(self): # testing code - remove for live
        test = self.parse_enr051_data()
        test.to_csv('Dataframes/Enr051.csv')

    def run(self):
        full_dir = f"{work_dir}\\DataFrames\\"
        Ad01 = self.parse_ad01_data() # returns single dataframe
        Ad02 = self.parse_ad02_data(Ad01) # returns dfAd01, df_rwy, df_srv
        Enr016 = self.parse_enr016_data(Ad01) # returns single dataframe
        Enr02 = self.parse_enr02_data() # returns dfFir, dfUir, dfCta, dfTma
        Enr031 = self.parse_enr03_data('1') # returns single dataframe
        Enr033 = self.parse_enr03_data('3') # returns single dataframe
        Enr035 = self.parse_enr03_data('5') # returns single dataframe
        Enr041 = self.parse_enr04_data('1') # returns single dataframe
        Enr044 = self.parse_enr04_data('4') # returns single dataframe
        Enr051 = self.parse_enr051_data() # returns single dataframe

        Ad01.to_csv(f'{full_dir}Ad01.csv')
        Ad02[1].to_csv(f'{full_dir}Ad02-Runways.csv')
        Ad02[2].to_csv(f'{full_dir}Ad02-Services.csv')
        Enr016.to_csv(f'{full_dir}Enr016.csv')
        Enr02[0].to_csv(f'{full_dir}Enr02-FIR.csv')
        Enr02[1].to_csv(f'{full_dir}Enr02-UIR.csv')
        Enr02[2].to_csv(f'{full_dir}Enr02-CTA.csv')
        Enr02[3].to_csv(f'{full_dir}Enr02-TMA.csv')
        Enr031.to_csv(f'{full_dir}Enr031.csv')
        Enr033.to_csv(f'{full_dir}Enr033.csv')
        Enr035.to_csv(f'{full_dir}Enr035.csv')
        Enr041.to_csv(f'{full_dir}Enr041.csv')
        Enr044.to_csv(f'{full_dir}Enr044.csv')
        Enr051.to_csv(f'{full_dir}Enr051.csv')

        return [Ad01, Ad02, Enr016, Enr02, Enr031, Enr033, Enr035, Enr041, Enr044, Enr051]

    @staticmethod
    def search(find, name, string):
        searchString = find + "(?=<\/span>.*>" + name + ")"
        result = re.findall(f"{str(searchString)}", str(string))
        return result

    @staticmethod
    def split(word):
        return [char for char in word]
    
    def sct_location_builder(self, lat, lon, lat_ns, lon_ew):
        """Returns an SCT file compliant location"""
        lat_split = self.split(lat) # split the lat into individual digits
        if len(lat_split) > 6:
            lat_print = f"{lat_ns}{lat_split[0]}{lat_split[1]}.{lat_split[2]}{lat_split[3]}.{lat_split[4]}{lat_split[5]}.{lat_split[7]}{lat_split[8]}"
        else:
            lat_print = f"{lat_ns}{lat_split[0]}{lat_split[1]}.{lat_split[2]}{lat_split[3]}.{lat_split[4]}{lat_split[5]}.00"

        lon_split = self.split(lon)
        if len(lon_split) > 7:
            lon_print = f"{lon_ew}{lon_split[0]}{lon_split[1]}{lon_split[2]}.{lon_split[3]}{lon_split[4]}.{lon_split[5]}{lon_split[6]}.{lon_split[8]}{lon_split[9]}"
        else:
            lon_print = f"{lon_ew}{lon_split[0]}{lon_split[1]}{lon_split[2]}.{lon_split[3]}{lon_split[4]}.{lon_split[5]}{lon_split[6]}.00"

        fullLocation = f"{lat_print} {lon_print}" # AD-2.2 gives aerodrome location as DDMMSS / DDDMMSS

        return fullLocation

    def getBoundary(self, space, name=0):
        """creates a boundary useable in vatSys from AIRAC data"""
        lat = True
        lat_lon_obj = []
        draw_line = []
        fullBoundary = ''
        for coord in space:
            coord_format = re.search(r"[N|S][\d]{2,3}\.[\d]{1,2}\.[\d]{1,2}\.[\d]{1,2}\s[E|W][\d]{2,3}\.[\d]{1,2}\.[\d]{1,2}\.[\d]{1,2}", str(coord))
            if coord_format != None:
                fullBoundary += f"{coord}/"
            else:
                if lat:
                    lat_lon_obj.append(coord[0])
                    lat_lon_obj.append(coord[1])
                    lat = False
                else:
                    lat_lon_obj.append(coord[0])
                    lat_lon_obj.append(coord[1])
                    lat = True
                
                # if lat_lon_obj has 4 items
                if len(lat_lon_obj) == 4:
                    lat_lon = self.sct_location_builder(lat_lon_obj[0], lat_lon_obj[2], lat_lon_obj[1], lat_lon_obj[3])
                    fullBoundary += f"{lat_lon}/"
                    draw_line.append(lat_lon)
                    lat_lon_obj = []

        return fullBoundary.rstrip('/')
    
    @staticmethod
    def split_single(word):
        return [char for char in str(word)]

    def dms2dd(self, lat, lon, ns, ew):
        lat_split = self.split_single(lat)
        lon_split = self.split_single(lon)

        lat_dd = lat_split[0] + lat_split[1]
        lat_mm = lat_split[2] + lat_split[3]
        lat_ss = lat_split[4] + lat_split[5]

        # lat N or S (+/-) lon E or W (+/-)

        lat_out = int(lat_dd) + int(lat_mm) / 60 + int(lat_ss) / 3600

        lon_dd = lon_split[0] + lon_split[1] + lon_split[2]
        lon_mm = lon_split[3] + lon_split[4]
        lon_ss = lon_split[5] + lon_split[6]

        lon_out = int(lon_dd) + int(lon_mm) / 60 + int(lon_ss) / 3600

        if ns == "S":
            lat_out = lat_out - (lat_out * 2)
        if ew == "W":
            lon_out = lon_out - (lon_out * 2)

        return [lat_out, lon_out]

    def generate_semicircle(self, center_x, center_y, start_x, start_y, end_x, end_y, direction):
        """Dreate a semicircle. Direction is 1 for clockwise and 2 for anti-clockwise"""
        from geographiclib.geodesic import Geodesic

        # centre point to start
        geolib_start = Geodesic.WGS84.Inverse(center_x, center_y, start_x, start_y)
        start_brg = geolib_start['azi1']
        start_dst = geolib_start['s12']
        start_brg_compass = ((360 + start_brg) % 360)

        # centre point to end
        geolib_end = Geodesic.WGS84.Inverse(center_x, center_y, end_x, end_y)
        end_brg = geolib_end['azi1']
        end_brg_compass = ((360 + end_brg) % 360)

        arc_out = []
        if direction == 1: # if cw
            while round(start_brg) != round(end_brg_compass):
                arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
                arc_out.append(self.dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
                start_brg = ((start_brg + 1) % 360)
                print(start_brg, end_brg_compass)
        elif direction == 2: # if acw
            while round(start_brg) != round(end_brg_compass):
                arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
                arc_out.append(self.dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
                start_brg = ((start_brg - 1) % 360)
                print(start_brg, end_brg_compass)

        return arc_out

    @staticmethod
    def dd2dms(latitude, longitude, dd_type=0):

        # math.modf() splits whole number and decimal into tuple
        # eg 53.3478 becomes (0.3478, 53)
        split_degx = math.modf(longitude)
        
        # the whole number [index 1] is the degrees
        degrees_x = int(split_degx[1])

        # multiply the decimal part by 60: 0.3478 * 60 = 20.868
        # split the whole number part of the total as the minutes: 20
        # abs() absoulte value - no negative
        minutes_x = abs(int(math.modf(split_degx[0] * 60)[1]))

        # multiply the decimal part of the split above by 60 to get the seconds
        # 0.868 x 60 = 52.08, round excess decimal places to 2 places
        # abs() absoulte value - no negative
        seconds_x = abs(round(math.modf(split_degx[0] * 60)[0] * 60,2))

        # repeat for latitude
        split_degy = math.modf(latitude)
        degrees_y = int(split_degy[1])
        minutes_y = abs(int(math.modf(split_degy[0] * 60)[1]))
        seconds_y = abs(round(math.modf(split_degy[0] * 60)[0] * 60,2))

        # account for E/W & N/S
        if longitude < 0:
            EorW = "W"
        else:
            EorW = "E"

        if latitude < 0:
            NorS = "S"
        else:
            NorS = "N"

        # abs() remove negative from degrees, was only needed for if-else above
        output = (NorS + str(abs(round(degrees_y))).zfill(3) + "." + str(round(minutes_y)).zfill(2) + "." + str(seconds_y).zfill(3) + " " + EorW + str(abs(round(degrees_x))).zfill(3) + "." + str(round(minutes_x)).zfill(2) + "." + str(seconds_x).zfill(3))
        return output

class Builder:
    '''Class to build sct files from the dataframes for POSCON'''

    def __init__(self, fileImport=0):
        self.mapCentre = "+53.7-1.5"
        # if there are dataframe files present then use those, else run the webscraper
        if fileImport == 1:
            scrape = []
            scrape.append(pd.read_csv('Dataframes/Ad01.csv', index_col=0))          #0
            scrape.append(pd.read_csv('Dataframes/Ad02-Runways.csv', index_col=0))  #1
            scrape.append(pd.read_csv('Dataframes/Ad02-Services.csv', index_col=0)) #2
            scrape.append(pd.read_csv('Dataframes/Enr016.csv', index_col=0))        #3
            scrape.append(pd.read_csv('DataFrames/Enr02-FIR.csv', index_col=0))     #4
            scrape.append(pd.read_csv('DataFrames/Enr02-UIR.csv', index_col=0))     #5
            scrape.append(pd.read_csv('DataFrames/Enr02-CTA.csv', index_col=0))     #6
            scrape.append(pd.read_csv('DataFrames/Enr02-TMA.csv', index_col=0))     #7
            scrape.append(pd.read_csv('DataFrames/Enr031.csv', index_col=0))        #8
            scrape.append(pd.read_csv('DataFrames/Enr033.csv', index_col=0))        #9
            scrape.append(pd.read_csv('DataFrames/Enr035.csv', index_col=0))        #10
            scrape.append(pd.read_csv('DataFrames/Enr041.csv', index_col=0))        #11
            scrape.append(pd.read_csv('DataFrames/Enr044.csv', index_col=0))        #12
            scrape.append(pd.read_csv('DataFrames/Enr051.csv', index_col=0))        #13
            self.scrape = scrape
        else:
            initWebscrape = Webscrape()
            self.scrape = initWebscrape.run()

    def run(self):
        """Build the SCT file"""
        sct_file = "Build/EGxx_FIR.sct"

        def sct_writer(filename):
            """Write to SCT file"""        
            with open(sct_file, 'a') as write_sct_file:
                with open(filename, 'r') as hdr:
                    lines = hdr.readlines()
                    for line in lines:
                        write_sct_file.write(line)
                write_sct_file.write('\n\n')

        def build_artcc(idx, section, range_lo, range_hi):
            with open(sct_file, 'a') as write_sct_file:
                write_sct_file.write(f'[{section}]\nRANGE {range_lo} {range_hi}\n')
                df = self.scrape[idx]
                for index, row in df.iterrows():
                    boundary = row['boundary']
                    draw_line = boundary.split('/')
                    n = 0
                    while n < len(draw_line):
                        if (n + 1) < len(draw_line):
                            write_sct_file.write(f"{row['name']}\t{draw_line[n]}\t{draw_line[n+1]}\n")
                        n += 1
                write_sct_file.write('\n')

        # Check if file exists and delete
        if os.path.exists(sct_file):
            os.remove(sct_file)

        # Headers
        sct_writer('DataFrames/HEADER.txt')
        sct_writer('DataFrames/INFO.txt')

        # VOR section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[VOR]\nRANGE 10 3000\n')
            df = self.scrape[11]
            for index, row in df.iterrows():
                write_sct_file.write(f"{row['name']} {row['freq']} {row['coords']}\n")
            write_sct_file.write('\n')
        
        # NDB section

        # AIRPORT section !!!AERODROME AIRSPACE CLASS NEEDS ENTERING PROPERLY - E AS A HOLDING CLASS!!!
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[AIRPORT]\nRANGE 10 500\n')
            df = self.scrape[0]
            df_filter = df.loc[df['verified'] == 1]
            for index, row in df_filter.iterrows():
                # select tower frequency
                df_services = self.scrape[2]
                df_services_filter = df_services.loc[(df_services['icao_designator'] == row['icao_designator']) & (df_services['callsign_type'] == "TOWER")]
                df_services_count = len(df_services_filter)
                if df_services_count >= 1:
                    for s_index, s_row in df_services_filter.iterrows():
                        write_sct_file.write(f"{row['icao_designator']}\t{s_row['frequency']}\t{row['location']}\tE\t;{row['name']}\n")
                else:
                    write_sct_file.write(f"{row['icao_designator']}\t000.000\t{row['location']}\tE\t;{row['name']}\n")
            write_sct_file.write('\n')

        # RUNWAY section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[RUNWAY]\nRANGE 0 500\n')
            df = self.scrape[1]
            flip_flop = True
            for index, row in df.iterrows():
                if flip_flop:
                    s_rwy = row['runway']
                    s_bearing = row['bearing']
                    s_loc = row['location']
                    flip_flop = False
                else:
                    write_sct_file.write(f"{s_rwy}\t{row['runway']}\t{s_bearing}\t{row['bearing']}\t{s_loc}\t{row['location']}\t{row['icao_designator']}\n")
                    flip_flop = True
            write_sct_file.write('\n')

        # FIXES section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[FIXES]\nRANGE 0 200\n')
            df = self.scrape[12]
            for index, row in df.iterrows():
                write_sct_file.write(f"{row['name']}\t{row['coords']}\n")
            write_sct_file.write('\n')

        # ARTCC section FIR
        build_artcc(4, "ARTCC", "100", "5000")

        # ARTCC HIGH section TMA
        build_artcc(7, "ARTCC HIGH", "100", "3000")

        # ARTCC LOW section CTA
        build_artcc(6, "ARTCC LOW", "0", "2000")

        # SID section

        # STAR section

        # LOW AIRWAY section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[LOW AIRWAY]\nRANGE 10 200\n')
            write_sct_file.write(';ENR-3.3\n')
            df = self.scrape[9]
            for index, row in df.iterrows():
                route = row['route']
                split_route = route.split('/')
                full_route = ''
                for point in split_route:
                    full_route += f"{point}\t"
                write_sct_file.write(f"{row['name']}\t{full_route}\tGreen\n")
            write_sct_file.write('\n')

        # HIGH AIRWAY section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[HIGH AIRWAY]\nRANGE 10 3000\n')
            write_sct_file.write(';ENR-3.1\n')
            df = self.scrape[8]
            for index, row in df.iterrows():
                route = row['route']
                split_route = route.split('/')
                full_route = ''
                for point in split_route:
                    full_route += f"{point}\t"
                write_sct_file.write(f"{row['name']}\t{full_route}\n")
            
            write_sct_file.write(';ENR-3.5\n')
            df = self.scrape[10]
            for index, row in df.iterrows():
                route = row['route']
                split_route = route.split('/')
                full_route = ''
                for point in split_route:
                    full_route += f"{point}\t"
                write_sct_file.write(f"{row['name']}\t{full_route}\n")
            write_sct_file.write('\n')

        # GEO section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[GEO]\nRANGE 0 6000\n')
        # UK Geographic Boundary
        sct_writer('DataFrames/UK_NOAA_GEO.txt')
        # ENR-5.1 DANGER / RESTRICTED areas
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(f';ENR-5.1\nRANGE 0 1500\n')
            df = self.scrape[13]
            for index, row in df.iterrows():
                boundary = row['boundary']
                draw_line = boundary.split('/')
                n = 0
                while n < len(draw_line):
                    if (n + 1) < len(draw_line):
                        write_sct_file.write(f"{row['name']}\t{draw_line[n]}\t{draw_line[n+1]}\tRed\n")
                    n += 1
            write_sct_file.write('\n')
        # UK Airfields
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('\nRANGE 0 20\n')
        sct_writer('Airfields/UK_AIRFIELDS.txt')

        # REGIONS section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[REGIONS]\nRANGE 0 20\n')
        # UK Airfields
        sct_writer('Airfields/UK_AIRFIELD_REGIONS.txt')

        # FREETEXT (labels) section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[FREETEXT]\n')
        
        # VOR labels
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(';VOR Names\nRANGE:10:1000\n')
            df_enr044 = self.scrape[11]
            for index, row in df_enr044.iterrows():
                coords = row['coords']
                write_sct_file.write(f"{coords.replace(' ', ':')}:VOR:{row['name']}\n")
            write_sct_file.write('\n')
        
        # AIRFIELD labels
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(';Airfield Labels\nRANGE:0:5\n')
        sct_writer('Airfields/UK_AIRFIELD_LABELS.txt')

        # POSITIONS section <name of position>:<radio callsign>:<frequency>:<identifier>:<middle letter>:<prefix>:<suffix>:<not used>:<not used>:<A code start of range>:<A code end of range>[:<VIS center1 latitude>:<VIS center1 longitude>[: ... ]]
        """
        The name of the position can be anything used to help in identifying the line inside the ESE file.
        Radio callsign shall be the official radiotelephony callsign that shall be used for that station.
        Frequency shall be in full with “.” as decimal separator.
        The identifier is used in many places in the software and may be as short as one character and as long as required.
        Prefix and suffix are the first and last parts of the callsign used to identify the position.
        A code ranges are used to preset the assignment A code ranges from which the system will assign the codes for a specific position.
        Optionally there can be some visibility centers defined for the position.
            One center can be defined by two parameters: latitude and longitude.
            There can be maximum 4 visibility centers defined (that is altogether 8 optional elements in the line)
        """
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[POSITIONS]\n')
            list_positions = ["APPROACH", "GROUND", "DELIVERY", "TOWER", "DIRECTOR", "RADIO", "RADAR"] # don't include INFORMATION as this is a non-controlled automatic position
            df = self.scrape[0]
            df_filter = df.loc[df['verified'] == 1]
            for index, row in df_filter.iterrows():
                for pos in list_positions:
                    df_services = self.scrape[2]
                    df_services_filter = df_services.loc[(df_services['icao_designator'] == row['icao_designator']) & (df_services['callsign_type'] == pos)]
                    num = 1
                    for s_index, s_row in df_services_filter.iterrows():
                        s_pos = s_row['callsign_type']
                        split_icao = Webscrape.split(row['icao_designator'])
                        if s_pos == "APPROACH":
                            short_pos = "INT"
                        elif s_pos == "GROUND":
                            short_pos = "GMC"
                        elif s_pos == "DELIVERY":
                            short_pos = "GMP"
                        elif s_pos == "TOWER":
                            short_pos = "TWR"
                        elif s_pos == "DIRECTOR":
                            short_pos = "FIN"
                        elif s_pos == "RADIO":
                            short_pos = "RDO"
                        elif s_pos == "RADAR":
                            short_pos = "RAD"
                        callsign = f"{split_icao[2]}{split_icao[3]}{short_pos}{num}"
                        write_sct_file.write(f"{row['icao_designator']} {row['name']} {pos}:{callsign}:{s_row['frequency']}:{callsign}:{num}:{row['icao_designator']}:{short_pos}:0401:7617\n")
                        num += 1
            write_sct_file.write('\n')



class Geo:
    '''Class to store various geo tools'''

    @staticmethod
    def geodesic_point_buffer(lat, lon, km):
        proj_wgs84 = pyproj.Proj('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        # Azimuthal equidistant projection
        aeqd_proj = '+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0'
        project = partial(
            pyproj.transform,
            pyproj.Proj(aeqd_proj.format(lat=lat, lon=lon)),
            proj_wgs84)
        buf = sPoint(0, 0).buffer(km * 1000)  # distance in metres
        return transform(project, buf).exterior.coords[:]

    @staticmethod
    def northSouth(arg): # Turns a compass point into the correct + or - for lat and long
        if arg in ('+'):
            return "N"
        return "S"

    @staticmethod
    def eastWest(arg): # Turns a compass point into the correct + or - for lat and long
        if arg in ('+'):
            return "E"
        return "W"

    @staticmethod
    def plusMinus(arg): # Turns a compass point into the correct + or - for lat and long
        if arg in ('N','E'):
            return "+"
        return "-"

    @staticmethod
    def backBearing(brg):
        if (float(brg) - 180) < 0:
            bB = float(brg) + 180.00
        else:
            bB = float(brg) - 180.00
        return round(bB, 2)

    @staticmethod
    def kmlMappingConvert(fileIn, icao): # BUG: needs reworking
        def mapLabels():
            # code to generate the map labels.
            points = MultiPoint(latLonString) # function to calculate polygon centroid
            labelPoint = points.centroid
            labelPrint = re.sub(r'[A-Z()]', '', str(labelPoint))
            labelSplit = labelPrint.split()

            xmlGroundMapInfLabelPoint = xtree.SubElement(xmlGroundMapInfLabel, 'Point')
            xmlGroundMapInfLabelPoint.set('Name', splitName[1])
            xmlGroundMapInfLabelPoint.text = "+" + str(labelSplit[0]) + re.sub(r'-0\.', '-000.', labelSplit[1])

        self.icao = icao

        xmlGround = Xml.root('Ground')
        xmlGroundMap = xtree.SubElement(xmlGround, 'Maps')

        with open(fileIn) as fobj:
            folder = parser.parse(fobj).getroot().Document

        xmlGroundMapRwy = Xml.constructMapHeader(xmlGroundMap, 'Ground_RWY', self.icao + '_SMR_RWY', '1', '+510853.0-0001125.0')
        xmlGroundMapTwy = Xml.constructMapHeader(xmlGroundMap, 'Ground_TWY', self.icao + '_SMR_TWY', '2', '+510853.0-0001125.0')
        xmlGroundMapBld = Xml.constructMapHeader(xmlGroundMap, 'Ground_BLD', self.icao + '_SMR_BLD', '1', '+510853.0-0001125.0')
        xmlGroundMapApr = Xml.constructMapHeader(xmlGroundMap, 'Ground_APR', self.icao + '_SMR_APR', '3', '+510853.0-0001125.0')
        xmlGroundMapBak = Xml.constructMapHeader(xmlGroundMap, 'Ground_BAK', self.icao + '_SMR_BAK', '4', '+510853.0-0001125.0')
        xmlGroundMapInf = Xml.constructMapHeader(xmlGroundMap, 'Ground_INF', self.icao + '_SMR_INF', '0', '+510853.0-0001125.0')
        xmlGroundMapHld = Xml.constructMapHeader(xmlGroundMap, 'Ground_INF', self.icao + '_SMR_HLD', '0', '+510853.0-0001125.0')

        xmlGroundMapInfLabel = xtree.SubElement(xmlGroundMapInf, 'Label')
        xmlGroundMapInfLabel.set('HasLeader', 'False')
        xmlGroundMapInfLabel.set('Alignment', 'Center')
        xmlGroundMapInfLabel.set('VerticalAlignment', 'Middle')

        for pm in folder.Placemark:
            name = pm.name
            splitName = str(name).split()
            if splitName[0] == "Hold":
                coords = pm.LineString.coordinates
            else:
                coords = pm.Polygon.outerBoundaryIs.LinearRing.coordinates

            search = re.finditer(r'([+|-]{1})([\d]{1}\.[\d]{10,20}),([\d]{2}\.[\d]{10,20})', str(coords))
            output = ''
            latLonString = []
            print(name)
            for line in search:
                fullLon = line.group().split(',')
                output += "+" + str(line.group(3)) + str(line.group(1)) + "00" + str(line.group(2)) + "/"
                latLonString.append((float(line.group(3)),float(fullLon[0])))

            if splitName[0] == "Rwy":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapRwy, 'Infill')
                mapLabels()
            elif splitName[0] == "Twy":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapTwy, 'Infill')
                mapLabels()
            elif splitName[0] == "Bld":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapBld, 'Infill')
            elif splitName[0] == "Apr":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapApr, 'Infill')
            elif splitName[0] == "Bak":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapBak, 'Infill')
            elif splitName[0] == "Hold":
                xmlGroundInfill = xtree.SubElement(xmlGroundMapHld, 'Line')
                mapLabels()

            xmlGroundInfill.set('Name', name)
            xmlGroundInfill.text = output.rstrip('/')

        Builder.buildPrettyXml(xmlGround, 'Build/Maps/'+ self.icao + '_SMR.xml')

class Navigraph:
    def sidStar(file, icaoIn, rwyIn):
        dfColumns=['ICAO','Runway','Name','Route']
        df = pd.DataFrame(columns=dfColumns)
        #print(df.to_string())
        with open(file, 'r') as text:
            content = text.read() # read everything
            aerodromeData = re.split(r'\[', content) # split by [
            for data in aerodromeData:
                aerodromeIcao = re.search(r'([A-Z]{4})(\]\n)', data) # get the ICAO aerodrome designator
                if aerodromeIcao:
                    icao = aerodromeIcao.group(1)
                    if icao == icaoIn:
                        lineSearch = re.findall(r'(T[\s]+)([A-Z\d]{5,})([\s]+[A-Z\d]{5,}[\s]+)([\d]{2}[L|R|C]?)(\,.*)?\n', data)

                        if lineSearch:
                            for line in lineSearch:
                                srdRunway = line[3]

                                # for each SID, get the route
                                routeSearch = re.findall(rf'^({line[1]})\s+([\dA-Z]{{3,5}})', data, re.M)

                                if routeSearch:
                                    concatRoute = ''
                                    for route in routeSearch:
                                        concatRoute += route[1] + "/"
                                        routeName = route[0]

                                    if line[4]:
                                        starRunways = line[4].split(',')
                                        for rwy in starRunways:
                                            dfOut = {'ICAO': icao, 'Runway': rwy, 'Name': routeName, 'Route': concatRoute.rstrip('/')}
                                            df = df.append(dfOut, ignore_index=True)

                                    dfOut = {'ICAO': icao, 'Runway': srdRunway, 'Name': routeName, 'Route': concatRoute.rstrip('/')}
                                    df = df.append(dfOut, ignore_index=True)

            return df[(df.Runway == rwyIn)]

class ValidateXml:
    """docstring for ValidateXml."""

    def __init__(self, schema):
        with open(schema) as sFile:
            self.schema = xmlschema.XMLSchema(sFile)

    def validateDir(self, searchDir, matchFile):
        with alive_bar() as bar:
            for subdir, dirs, files in os.walk(searchDir):
                for filename in files:
                    filepath = subdir + os.sep + filename
                    if fnmatch.fnmatch(filename, matchFile + '.xml'):
                        bar()
                        if self.schema.is_valid(filepath) is False:
                            print(filepath)
                            self.schema.validate(filepath)

        print(Fore.GREEN + "    OK" + Style.RESET_ALL + " - All tests passed for " + searchDir + matchFile)

    @staticmethod
    def run():
        # Validation of XML files with XSD schema
        twrMap = ValidateXml("Validation/twrmap.xsd")
        twrMap.validateDir("Build/Maps", "*TWR*")

        airspace = ValidateXml("Validation/airspace.xsd")
        airspace.validateDir("Build", "Airspace")

        radar = ValidateXml("Validation/radars.xsd")
        radar.validateDir("Build", "Radars")

        sectors = ValidateXml("Validation/sectors.xsd")
        sectors.validateDir("Build", "Sectors")

        allMaps = ValidateXml("Validation/allmaps.xsd")
        allMaps.validateDir("Build/Maps", "ALL_*")

class EuroScope:
    """tools to convert EuroScope bits to vatSys"""

    def __init__(self, icao):
        self.icao = icao
        # get the location of this aerodrome
        df = pd.read_csv('Dataframes/Ad01.csv', index_col=0)
        dfLookup = df.loc[df['icao_designator'] == icao]
        self.location = dfLookup.iat[0,2]

    def kmlMappingConvert(self, fileIn, fileNumber):
        def mapLabels():
            # code to generate the map labels.
            points = MultiPoint(latLonString) # function to calculate polygon centroid
            labelPoint = points.centroid
            labelPrint = re.sub(r'[A-Z()]', '', str(labelPoint))
            labelSplit = labelPrint.split()

            if labelSplit:
                xmlGroundMapInfLabelPoint = xtree.SubElement(xmlGroundMapInfLabel, 'Point')
                xmlGroundMapInfLabelPoint.set('Name', child)
                if float(labelSplit[0]) > 0:
                    dotSplit = str(labelSplit[0]).split(".")
                    latPrint = "+" + str(dotSplit[0]).zfill(2) + "." + str(dotSplit[1])
                else:
                    dotSplit = str(labelSplit[0]).split(".")
                    dotStart = str(dotSplit[0]).lstrip("-")
                    latPrint = "-" + str(dotStart).zfill(2) + "." + str(dotSplit[1])

                if float(labelSplit[1]) > 0:
                    dotSplit = str(labelSplit[1]).split(".")
                    lonPrint = "+" + str(dotSplit[0]).zfill(3) + "." + str(dotSplit[1])
                else:
                    dotSplit = str(labelSplit[1]).split(".")
                    dotStart = str(dotSplit[0]).lstrip("-")
                    lonPrint = "-" + str(dotStart).zfill(3) + "." + str(dotSplit[1])

                xmlGroundMapInfLabelPoint.text = str(latPrint) + str(lonPrint)

        xmlGround = Builder.root('Ground')
        xmlGroundMap = xtree.SubElement(xmlGround, 'Maps')

        with open(fileIn) as fobj:
            folder = parser.parse(fobj).getroot().Document

        xmlGroundMapRwy = Builder.constructMapHeader(xmlGroundMap, 'Ground_RWY', self.icao + '_SMR_RWY', '1', self.location)
        xmlGroundMapTwy = Builder.constructMapHeader(xmlGroundMap, 'Ground_TWY', self.icao + '_SMR_TWY', '2', self.location)
        xmlGroundMapBld = Builder.constructMapHeader(xmlGroundMap, 'Ground_BLD', self.icao + '_SMR_BLD', '1', self.location)
        xmlGroundMapApr = Builder.constructMapHeader(xmlGroundMap, 'Ground_APR', self.icao + '_SMR_APR', '3', self.location)
        xmlGroundMapBak = Builder.constructMapHeader(xmlGroundMap, 'Ground_BAK', self.icao + '_SMR_BAK', '4', self.location)
        xmlGroundMapInf = Builder.constructMapHeader(xmlGroundMap, 'Ground_INF', self.icao + '_SMR_INF', '0', self.location)
        xmlGroundMapHld = Builder.constructMapHeader(xmlGroundMap, 'Ground_INF', self.icao + '_SMR_HLD', '0', self.location)

        xmlGroundMapInfLabel = xtree.SubElement(xmlGroundMapInf, 'Label')
        xmlGroundMapInfLabel.set('HasLeader', 'False')
        xmlGroundMapInfLabel.set('Alignment', 'Center')
        xmlGroundMapInfLabel.set('VerticalAlignment', 'Middle')

        try:
            rootFolder = folder.Folder.Folder
        except:
            rootFolder = folder.Folder

        for pm in rootFolder:
            name = pm.name
            print(" " + name)
            titles = ["apron","aprons","asphalt","backround","backrounds","buildings","concrete","grass","ground","holding","holds","island","land","markings","new","parking","runway","runways","stand","stands","surface","taxi","taxilines","taxiway","taxiways","other"]
            splitName = str(name).split()
            if splitName[0].lower() in titles:
                try:
                    pmP = pm.Folder.Placemark
                except:
                    try:
                        pmP = pm.Placemark
                    except:
                        pass

                for place in pmP:
                    try:
                        coords = place.LineString.coordinates
                    except:
                        coords = place.Polygon.outerBoundaryIs.LinearRing.coordinates

                    child = place.name
                    print("  " + str(child))
                    search = re.finditer(r'([+|-]?)([\d]{1,3})\.([\d]{10,20}),([+|-]?)([\d]{1,2})\.([\d]{10,20})', str(coords))
                    output = ''
                    latLonString = []

                    for line in search:
                        if line.group(1) == "-":
                            lonSign = "-"
                        else:
                            lonSign = "+"

                        if line.group(4) == "-":
                            latSign = "-"
                        else:
                            latSign = "+"

                        output += latSign + str(line.group(5)).zfill(2) + "." + str(line.group(6)) + lonSign + str(line.group(2)).zfill(3) + "." + str(line.group(3)) + "/"
                        lineSplit = line.group().split(",")
                        latLonString.append((float(lineSplit[1]),float(lineSplit[0])))

                    if str(name).lower() == "runways" or str(name).lower() == "runway" or splitName[-1].lower() == "runways":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapRwy, 'Infill')
                        mapLabels()
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')
                    elif splitName[0].lower() == "taxiways" or splitName[0].lower() == "taxi" or splitName[0].lower() == "taxilines" or splitName[0].lower() == "taxiway" or splitName[-1].lower() == "taxiways":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapTwy, 'Infill')
                        mapLabels()
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')
                    elif splitName[0].lower() == "buildings":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapBld, 'Infill')
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')
                    elif splitName[0].lower() == "aprons" or splitName[-1] == "aprons":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapApr, 'Infill')
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')
                    elif splitName[0].lower() == "background" or splitName[0].lower() == "backgrounds":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapBak, 'Infill')
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')
                    elif splitName[0].lower() == "surface" or splitName[0].lower() == "markings" or splitName[-1].lower() == "markings" or splitName[-1].lower() == "lines" or splitName[0].lower() == "hold" or splitName[0].lower() == "holding" or splitName[0].lower() == "holds" or splitName[0].lower() == "stand" or splitName[0].lower() == "stands":
                        xmlGroundInfill = xtree.SubElement(xmlGroundMapHld, 'Line')
                        mapLabels()
                        xmlGroundInfill.set('Name', child)
                        xmlGroundInfill.text = output.rstrip('/')

        if str(fileNumber) == "1":
            Builder.buildPrettyXml(xmlGround, 'Build/Maps/'+ self.icao + '/' + self.icao + '_SMR.xml')
        else:
            Builder.buildPrettyXml(xmlGround, 'KML/SMR/' + self.icao + '_' + str(fileNumber) + '_SMR.xml')

    @staticmethod
    def parse(fileIn):
        dfColumns = ['sectorline','coords']
        df = pd.DataFrame(columns=dfColumns)
        file = open(fileIn, "r")
        #fileWrite = open('Testing/out.txt', "w")
        c = ''
        for f in file:
            coord = re.search(r"(N|S)([\d]{3})\.([\d]{2})\.([\d]{2})(\.[\d]{3})[\s|:](E|W)([\d]{3})\.([\d]{2})\.([\d]{2})(\.[\d]{3})", f)
            line = re.search(r"(SECTORLINE):(.*)", f)
            if coord:
                latSign = Geo.plusMinus(coord.group(1))
                lonSign = Geo.plusMinus(coord.group(6))

                output = latSign + coord.group(2).lstrip("0") + coord.group(3) + coord.group(4)  + coord.group(5) + lonSign + coord.group(7) + coord.group(8) + coord.group(9)  + coord.group(10)
                c += output + '/'
            elif line:
                lineOut = line.group(2)
            elif f == "\n":
                dfOut = {'sectorline': lineOut, 'coords': c.rstrip('/')}
                df = df.append(dfOut, ignore_index=True)
                c = ''

        print(df)
        df.to_csv('Dataframes/ES-SectorLines.csv')

    @staticmethod
    def iterFolders(src, dst):
        for subdir, dirs, files in os.walk(rf'{src}'):
            c = 0
            for filename in files:
                filepath = subdir + os.sep + filename
                if filepath.endswith(".kmz"):
                    splitPath = subdir.split('/')
                    splitName = filename.split('.')
                    if re.match(r'(EG)[A-Z]{2}', splitPath[-1]) is not None:
                        c += 1
                        copyDst = dst + splitPath[-1] + "_" + str(c) + '.zip'
                        shutil.copyfile(filepath, copyDst)
                        with zipfile.ZipFile(copyDst, 'r') as zip:
                            print(splitPath[-1])
                            zip.extractall(dst)
                            shutil.copyfile(dst + 'doc.kml', dst + splitPath[-1] + "_" + str(c) + '.kml')
                            try:
                                convert = EuroScope(splitPath[-1])
                                kmlFileIn = dst + splitPath[-1] + "_" + str(c) + '.kml'
                                convert.kmlMappingConvert(kmlFileIn, c)
                            except:
                                print("ERROR: " + splitPath[-1])

# Defuse XML
defuse_stdlib()

# Build command line argument parser
cmdParse = argparse.ArgumentParser(description="Application to collect data from an AIRAC source and build that into xml files for use with vatSys.")
cmdParse.add_argument('-s', '--scrape', help='web scrape and build xml files', action='store_true')
cmdParse.add_argument('-b', '--build', help='build xml file from database', action='store_true')
cmdParse.add_argument('-g', '--geo', help='tool to assist with converting airport mapping from ES', action='store_true')
cmdParse.add_argument('-d', '--debug', help='runs the code defined in the debug section [DEV ONLY]', action='store_true')
cmdParse.add_argument('-v', '--verbose', action='store_true')
args = cmdParse.parse_args()

if args.geo:
    EuroScope.iterFolders(f'{work_dir}\\_data\\SMR Files\\', f'{work_dir}\\KML\\ZIP\\')
elif args.debug:
    EuroScope.parse(f'{work_dir}\\Sectors\\Combined.txt')
elif args.scrape:
    shutil.rmtree(f'{work_dir}\\Build')
    os.mkdir(f'{work_dir}\\Build')
    new = Webscrape()
    new.run()
elif args.build:
    shutil.rmtree(f'{work_dir}\\Build')
    os.mkdir(f'{work_dir}\\Build')
    new = Builder(1)
    new.run()
else:
    new = Webscrape()
    new.parse_enr02_data()
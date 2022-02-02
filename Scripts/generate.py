#!/usr/bin/env python3
from asyncore import loop
import math
import datetime
import argparse
from pkgutil import get_data
import shutil
from webbrowser import get
from numpy import fft
import urllib3
import argparse
import requests
import re
import os
import pandas as pd
import urllib3
from alive_progress import alive_bar
from bs4 import BeautifulSoup
from colorama import Fore, Style
from datetime import date
from geographiclib.geodesic import Geodesic

work_dir = os.getcwd()

# pandas init
dfColumns = ['name', 'callsign', 'frequency', 'boundary', 'upper_fl', 'lower_fl', 'class']
df_fir = pd.DataFrame(columns=dfColumns)
df_uir = pd.DataFrame(columns=dfColumns)
df_cta = pd.DataFrame(columns=dfColumns)
df_tma = pd.DataFrame(columns=dfColumns)
df_ctr = pd.DataFrame(columns=dfColumns)
df_atz = pd.DataFrame(columns=dfColumns)
dfEnr05 = pd.DataFrame(columns=dfColumns)

class Airac:
    """Class for general functions relating to AIRAC"""

    def __init__(self):
        """First AIRAC date following the last cycle length modification"""
        startDate = "2019-01-02"
        self.baseDate = date.fromisoformat(str(startDate))
        # Length of one AIRAC cycle
        self.cycleDays = 28

    def initialise(self, dateIn=0):
        """Calculate the number of AIRAC cycles between any given date and the start date"""
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
        """Return the date of the current AIRAC cycle"""
        numberOfCycles = self.initialise()
        numberOfDays = numberOfCycles * self.cycleDays + 1
        return self.baseDate + datetime.timedelta(days=numberOfDays)

    def nextCycle(self):
        """Return the date of the next AIRAC cycle"""
        numberOfCycles = self.initialise()
        numberOfDays = (numberOfCycles + 1) * self.cycleDays + 1
        return self.baseDate + datetime.timedelta(days=numberOfDays)

    def url(self, next=0):
        """Return a generated URL based on the AIRAC cycle start date"""
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
    
    def cw_acw_helper(self, data_in, output_title, load=0):
        """creates a list of complex airspace areas with the direction of the arc for reference later on"""
        dfColumns = ['area', 'number', 'direction']
        complex_areas = pd.DataFrame(columns=dfColumns)
        row = 0
        complex_search_data = data_in.find_all("p") # find everything enclosed in <p></p> tags
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
        if load == 1:
            return complex_areas
        else:
            complex_areas.to_csv(f'{work_dir}\\DataFrames\{output_title}-CW-ACW-Helper.csv')
    
    def circle_helper(self, data_in, output_title, load=0):
        """creates a list of complex airspace areas with the direction of the arc for reference later on"""
        dfColumns = ['area', 'number', 'direction']
        complex_areas = pd.DataFrame(columns=dfColumns)
        row = 0
        complex_search_data = data_in.find_all("p") # find everything enclosed in <p></p> tags
        complex_len = len(complex_search_data)
        while row < complex_len:
            title = re.search(r"id=\"ID_[\d]{8,10}\"\>([A-Z]*)\s(ATZ)\<", str(complex_search_data[row]))
            if title:
                print_title = f"{str(title.group(1))} {str(title.group(2))}"
                circle = re.findall(r"(?<=\s)(circle)(?=\,|\s)", str(complex_search_data[row+1]))
                if circle:
                    ca_out = {'area': print_title, 'number': "0", 'direction': "circle"}
                    complex_areas = complex_areas.append(ca_out, ignore_index=True)
                    row += 1
            row += 1
        if load == 1:
            return complex_areas
        else:
            complex_areas.to_csv(f'{work_dir}\\DataFrames\{output_title}-Circle-Helper.csv')

    def airspace_parser(self, getData, ad217=0, df_fir=df_fir, df_uir=df_uir, df_cta=df_cta, df_tma=df_tma, df_ctr=df_ctr, df_atz=df_atz, df_danger=dfEnr05):
        """parse the airspace data from the given page"""
        # scrape all the data and chuck it in an array
        data_out = []
        searchData = getData.find_all("tr")
        for line in searchData:
            for l in line.stripped_strings:
                data_out.append(l)

        # define some bits
        stopstopstop = 0
        df_atz_out = False
        airspace = False
        danger = False
        row = 0
        last_arc_title = False
        arc_counter = 0
        space = []
        loop_coord = False
        first_callsign = False
        first_freq = False
        frequency = "000.000"
        upper_limit_out = "000"
        lower_limit_out = "000"
        airspace_class_out = "E"
        count = 0

        # actually do something with the data
        while (count < len(data_out) and (stopstopstop == 0)):
            data_to_wrangle = data_out[count]
            title = re.search(r"TAIRSPACE;TXT_NAME", str(data_to_wrangle))
            danger_area = re.search(r"TAIRSPACE;CODE_ID", str(data_to_wrangle))
            coords = re.search(r"(?:TAIRSPACE_VERTEX;GEO_L(?:AT|ONG);)([\d]{4})", str(data_to_wrangle))
            callsign = re.search(r"TUNIT;TXT_NAME", str(data_to_wrangle))
            freq = re.search(r"TFREQUENCY;VAL_FREQ_TRANS", str(data_to_wrangle))
            arc = re.search(r"TAIRSPACE_VERTEX;VAL_RADIUS_ARC", str(data_to_wrangle))
            lat_arc = re.search(r"TAIRSPACE_VERTEX;GEO_LAT_ARC", str(data_to_wrangle))
            lon_arc = re.search(r"TAIRSPACE_VERTEX;GEO_LONG_ARC", str(data_to_wrangle))
            airspace_class = re.search(r"TAIRSPACE_LAYER_CLASS;CODE_CLASS", str(data_to_wrangle))
            upper_limit = re.search(r"TAIRSPACE_VOLUME;VAL_DIST_VER_UPPER", str(data_to_wrangle))
            lower_limit = re.search(r"TAIRSPACE_VOLUME;VAL_DIST_VER_LOWER", str(data_to_wrangle))

            if title:
                # get the printed title
                print_title = str(data_out[count-1])
                airspace = re.search(r"(FIR|UIR|CTA|TMA|CTR|ATZ|RMZ)", str(data_out[row-1]))
                if airspace:
                    df_in_title = print_title
                loop_coord = True

            if danger_area and (stopstopstop == 0):
                # get the danger area code
                dac_d_p_r = re.search(r"(EG\s[D|P|R]{1}[\d]{3}[A-Z]*)", str(data_out[row-1]))
                print(dac_d_p_r)
                dac_ru = re.search(r"(EG\sRU[\d]{3}[A-Z]*)", str(data_out[row-1]))
                print(dac_ru)
                if dac_ru:
                    stopstopstop = 1
                if dac_d_p_r:
                    airspace = dac_d_p_r
                    danger = True
                    danger_title = str(data_out[count+1])
                    loop_coord = True

            if (callsign) and (first_callsign is False):
                # get the first (and only the first) printed callsign
                callsign_out = str(data_out[count-1])
                first_callsign = True

            if airspace_class:
                # get airspace class
                airspace_class_out = str(data_out[count-1])
            
            if upper_limit:
                # get airspace upper limit
                upper_limit_out = str(data_out[count-1])

            if lower_limit:
                # get airspace lower limit
                lower_limit_out = str(data_out[count-1])
            
            if (freq) and (first_freq is False):
                # get the first (and only the first) printed callsign
                frequency = str(data_out[count-1])
                first_freq = True

            if arc: # what to do if an arc is found
                # check to see if this a series, if so then increment the counter
                if print_title == str(last_arc_title):
                    arc_counter += 0
                else:
                    arc_counter == 0

                # circle, clockwise or anti-clockwise arc?
                circle = re.search(r"^[A|a]\sradius\,\scentred\sat", data_out[count-2])
                circle2 = re.search(r"^[A|a]\scircle\,", data_out[count-2])
                anti_clockwise = re.search("anti-clockwise", data_out[count-2])
                clockwise = re.search(r"\sclockwise\s", data_out[count-2])
                cacw = 0
                if anti_clockwise:
                    cacw = 2
                elif circle or circle2:
                    cacw = 3
                elif clockwise:
                    cacw = 1

                if cacw > 0:         
                    radius = data_out[count-1]
                    # deal with radius in meters
                    if float(radius) > 100:
                        radius = float(radius) / 1000
                    if cacw < 3:
                        start_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count-4])
                        start_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count-6])
                        centre_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+4])
                        centre_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+6])
                        end_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+9])
                        end_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+11])
                    elif cacw == 3:
                        centre_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+4])
                        centre_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+6])

                    if (cacw < 3) and (centre_lat == None):
                        centre_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+2])
                        centre_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+4])
                        end_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+7])
                        end_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+9])
                    
                    if (cacw < 3) and (end_lat == None):
                        end_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+11])
                        end_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+13])

                    # convert from dms to dd
                    if cacw == 3:
                        mid_dd = self.dms2dd(centre_lat.group(1), centre_lon.group(1), centre_lat.group(2), centre_lon.group(2))
                        start_dd = mid_dd
                        end_dd = mid_dd
                    else:
                        start_dd = self.dms2dd(start_lat.group(1), start_lon.group(1), start_lat.group(2), start_lon.group(2))
                        mid_dd = self.dms2dd(centre_lat.group(1), centre_lon.group(1), centre_lat.group(2), centre_lon.group(2))
                        end_dd = self.dms2dd(end_lat.group(1), end_lon.group(1), end_lat.group(2), end_lon.group(2))
                    if danger_area:
                        print(danger_title)
                    else:
                        print(print_title)
                    arc_out = self.generate_semicircle(float(mid_dd[0]), float(mid_dd[1]), float(start_dd[0]), float(start_dd[1]), float(end_dd[0]), float(end_dd[1]), cacw, float(radius))
                    for coord in arc_out:
                        space.append(coord)
                    
                    # store the last arc title to compare against
                    last_arc_title = str(print_title)

            if coords:
                loop_coord = False
                # get the coordinate
                print_coord = re.findall(r"([\d]{6,7})(N|S|E|W)", str(data_out[count-1]))
                if print_coord: 
                    space.append(print_coord[0])

            if (ad217 == 1) and (loop_coord):
                # for looping through AD2.17 aerodrome
                first_callsign = True
                callsign_out = print_title
            elif (ad217 == 2) and (loop_coord):
                # for danger areas
                first_callsign = True
                callsign_out = danger_title

            if (loop_coord) and (space != []) and (first_callsign):
                def coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit, lower_limit, airspace_class):
                    df_out = {
                        'name': last_df_in_title,
                        'callsign': callsign_out,
                        'frequency': str(frequency),
                        'boundary': str(output),
                        'upper_fl': str(upper_limit),
                        'lower_fl': str(lower_limit),
                        'class': str(airspace_class)
                        }
                    return df_out

                output = self.getBoundary(space)
                if airspace:
                    # for FIRs do this
                    if last_airspace.group(1) == "FIR":
                        df_fir_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                        df_fir = df_fir.append(df_fir_out, ignore_index=True)
                    # for UIRs do this - same extent as FIR
                    #if last_airspace.group(1) == "UIR":
                    #    df_uir_out = {'name': last_df_in_title,'callsign': callsign_out,'frequency': str(frequency), 'boundary': str(output), 'upper_fl': '000', 'lower_fl': '000'}
                    #    df_uir = df_uir.append(df_uir_out, ignore_index=True)
                    # for CTAs do this
                    if last_airspace.group(1) == "CTA":
                        df_cta_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                        df_cta = df_cta.append(df_cta_out, ignore_index=True)
                    if last_airspace.group(1) == "TMA":
                        df_tma_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                        df_tma = df_tma.append(df_tma_out, ignore_index=True)
                    if last_airspace.group(1) == "CTR":
                        df_ctr_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                        df_ctr = df_ctr.append(df_ctr_out, ignore_index=True)
                    if (last_airspace.group(1) == "ATZ") or (last_airspace.group(1) == "RMZ") or (last_airspace.group(1) == "CTR"):
                        df_atz_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                        df_atz = df_atz.append(df_atz_out, ignore_index=True)
                    if danger:
                        df_danger_out = coord_to_table(last_df_in_title, False, False, output, upper_limit_out, lower_limit_out, False)
                        df_danger = df_danger.append(df_danger_out, ignore_index=True)
                    space = []
                    loop_coord = True
                    first_callsign = False
                    first_freq = False

            if airspace:
                if danger:
                    last_df_in_title = danger_title
                else:
                    last_df_in_title = print_title
                last_airspace = airspace
            row += 1
            count += 1
        df_uir = df_fir
        if (ad217 == 1):
            return [df_fir, df_uir, df_cta, df_tma, df_ctr, df_atz_out, df_danger]
        else:
            return [df_fir, df_uir, df_cta, df_tma, df_ctr, df_atz, df_danger]

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
                    pM = self.plusMinus(aerodromeMagVar[0][1])
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
    
    def parse_ad0217_data(self, dfAd01): # re-write of this section has been completed
        """This will parse airspace data from AD 2.17 for each aerodrome"""
        print("Parsing "+ self.country +"-AD-2.17 Data (AIR TRAFFIC SERVICES AIRSPACE)...")

        dfColumns = ['name', 'callsign', 'frequency', 'boundary', 'upper_fl', 'lower_fl', 'class']
        df_atz = pd.DataFrame(columns=dfColumns)

        # Select all aerodromes in the database
        for index, rowu in dfAd01.iterrows():
            aeroIcao = rowu['icao_designator']
            # Select all runways in this aerodrome
            getAerodromes = self.get_table_soup(self.country + "-AD-2."+ aeroIcao +"-en-GB.html")
            if getAerodromes !=404:
                print("  Parsing AD-2.17 data for " + aeroIcao)
                #getData = self.get_table_soup(self.country + "-ENR-2.1-en-GB.html")
                getData = getAerodromes.find(id=aeroIcao + "-AD-2.17")
                output = self.airspace_parser(getData, 1)
                if output[5] != False:
                    df_atz = df_atz.append(output[5], ignore_index=True)
                
        return df_atz

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

    def parse_enr021_data(self): # re-write of this section has been completed
        """This will parse ENR 2 data from the given AIP"""

        print("Parsing "+ self.country +"-ENR-2.1 Data (FIR, UIR, TMA AND CTA)...")
        getData = self.get_table_soup(self.country + "-ENR-2.1-en-GB.html")
        output = self.airspace_parser(getData)
        
        return [output[0], output[1], output[2], output[3]]

    def parse_enr022_data(self): # re-write of this section has been completed
        """This will parse ENR 2.2 data from the given AIP"""
        
        print("Parsing "+ self.country +"-ENR-2.2 Data (OTHER REGULATED AIRSPACE)...")
        getData = self.get_table_soup(self.country + "-ENR-2.2-en-GB.html")
        output = self.airspace_parser(getData)

        return output[5]

    def acc_uac_control_sectors(self):
        xlsx_file = f"{work_dir}\\ACC_UAC_Sectors.csv"
        part_number = False

        dfColumns = ['name', 'boundary']
        df = pd.DataFrame(columns=dfColumns)

        def wrangler(data, sector, df):
            """sorts out all of the random coords into something useful"""
            latlon = ""
            if data != "":
                pair = re.findall(r"([0-9]{6})([N|S])[\,\s\.\n]?([0-9]{7})([E|W])", data)
                for p in pair:
                    lat = p[0]
                    lon = p[2]
                    ns = p[1]
                    ew = p[3]
                    q = self.sct_location_builder(lat, lon, ns, ew)
                    latlon = f"{latlon}/{q}"
                latlon = latlon.lstrip("/")
                dfOut = {'name': str(sector), 'boundary': str(latlon)}
                print(dfOut)
                return dfOut

        coord_full = ""
        area = False
        sector = False
        with open(xlsx_file) as read_file:
            for line in read_file:
                split_line = line.split(',')
                area_name = re.match(r"[A-Z]{3,}\sAC", line) # area name
                sector_name = re.match(r"[A-Z]{3,}", split_line[0]) # sector name
                sector_number = re.match(r"[0-9]{1,2}\,\,", line) # sector name
                if len(split_line) > 3:
                    part_number = re.match(r"[0-9]{1}", split_line[2]) # get sector part number
                    upper_fl = re.match(r"[FL\s]{2,4}[\d\s]{1,5}", split_line[3]) # get upper flight level
                    if not upper_fl:
                        upper_fl = re.match(r"[FL\s]{2,4}[\d\s]{2,5}", split_line[0]) # get upper flight level
                # find area name
                if area_name:
                    dfOut = wrangler(coord_full, area, df)
                    df = df.append(dfOut, ignore_index=True)
                    coord_full = ""
                    area = split_line[0]
                elif sector_name or sector_number:
                    # sector name or number
                    if part_number:
                        dfOut = wrangler(coord_full, sector, df)
                        df = df.append(dfOut, ignore_index=True)
                        coord_full = ""
                        sector = f"{area} {split_line[0]} {part_number[0]}"
                    else:
                        sector = f"{area} {split_line[0]}"
                    
                    if upper_fl:
                        print_txt = split_line[3].replace(" ", "")
                        #print(f"\t\t{print_txt}")
                elif upper_fl:
                    print_txt = upper_fl[0].replace(" ", "")
                    #print(f"\t\t{print_txt}")
                
                for splt in split_line:
                    clear_spaces = splt.replace(" ", "").replace("O", "0").replace("l", "1").replace("I", "1")
                    with open("out.txt", "a") as file:
                        file.write(clear_spaces)
                    nav = re.findall(r"[0-9OlIi]{5,8}[\-]?[N|S|E|W]", clear_spaces)
                    for coord in nav:
                        ns_check = re.match(r"[0-9]{6}[N|S]", coord)
                        we_check = re.match(r"[0-9]{7}[W|E]", coord)
                        if (not ns_check) and (not we_check):
                            ns_check_s2 = re.search(r"([0-9]{5})([N|S])", coord)
                            ew_check_s2 = re.search(r"([0-9]{6})([W|E])", coord)
                            ew_check_s3 = re.search(r"([0-9]{5})([W|E])", coord)
                            if ns_check_s2:
                                coord = f"{ns_check_s2[0]}0{ns_check_s2[1]}"
                            elif ew_check_s2:
                                coord = f"{ew_check_s2[0]}0{ew_check_s2[1]}"
                            elif ew_check_s3:
                                coord = f"{ew_check_s3[0]}00{ew_check_s3[1]}"
                            else:
                                coord = input(f"Error spotted with {coord}, please enter correct value: ")
                        coord_full = f"{coord_full} {coord}"

        return df

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
        """This will parse ENR 5.1 data from the given AIP"""

        print("Parsing "+ self.country +"-ENR-5.1 data for PROHIBITED, RESTRICTED AND DANGER AREAS...")
        get_data = self.get_table_soup(self.country + "-ENR-5.1-en-GB.html")
        output = self.airspace_parser(get_data, 2)

        return output[6]

    def test(self): # testing code - remove for live
        test = self.parse_enr051_data()
        test.to_csv('Dataframes/Enr051.csv')

    @staticmethod
    def plusMinus(arg):
        """Turns a compass point into the correct + or - for lat and long"""
        if arg in ('N','E'):
            return "+"
        return "-"

    def run(self):
        full_dir = f"{work_dir}\\DataFrames\\"
        Ad01 = self.parse_ad01_data() # returns single dataframe
        Ad02 = self.parse_ad02_data(Ad01) # returns dfAd01, df_rwy, df_srv
        Ad0217 = self.parse_ad0217_data(Ad01) # returns single dataframe
        Enr016 = self.parse_enr016_data(Ad01) # returns single dataframe
        Enr021 = self.parse_enr021_data() # returns dfFir, dfUir, dfCta, dfTma
        Enr022 = self.parse_enr022_data() # returns single dataframe
        Enr031 = self.parse_enr03_data('1') # returns single dataframe
        Enr033 = self.parse_enr03_data('3') # returns single dataframe
        Enr035 = self.parse_enr03_data('5') # returns single dataframe
        Enr041 = self.parse_enr04_data('1') # returns single dataframe
        Enr044 = self.parse_enr04_data('4') # returns single dataframe
        Enr051 = self.parse_enr051_data() # returns single dataframe
        AccUac = self.acc_uac_control_sectors() # returns single dataframe

        Ad01.to_csv(f'{full_dir}Ad01.csv')
        Ad02[1].to_csv(f'{full_dir}Ad02-Runways.csv')
        Ad02[2].to_csv(f'{full_dir}Ad02-Services.csv')
        Ad0217.to_csv(f'{full_dir}Ad0217-ATS.csv')
        Enr016.to_csv(f'{full_dir}Enr016.csv')
        Enr021[0].to_csv(f'{full_dir}Enr021-FIR.csv')
        Enr021[1].to_csv(f'{full_dir}Enr021-UIR.csv')
        Enr021[2].to_csv(f'{full_dir}Enr021-CTA.csv')
        Enr021[3].to_csv(f'{full_dir}Enr021-TMA.csv')
        Enr022.to_csv(f'{full_dir}Enr022-ATZ.csv')
        Enr031.to_csv(f'{full_dir}Enr031.csv')
        Enr033.to_csv(f'{full_dir}Enr033.csv')
        Enr035.to_csv(f'{full_dir}Enr035.csv')
        Enr041.to_csv(f'{full_dir}Enr041.csv')
        Enr044.to_csv(f'{full_dir}Enr044.csv')
        Enr051.to_csv(f'{full_dir}Enr051.csv')
        AccUac.to_csv(f'{full_dir}AccUac.csv')

        return [Ad01, Ad02, Enr016, Enr021, Enr022, Enr031, Enr033, Enr035, Enr041, Enr044, Enr051]

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

    def generate_semicircle(self, center_x, center_y, start_x, start_y, end_x, end_y, direction, dst=2.5):
        """Dreate a semicircle. Direction is 1 for clockwise and 2 for anti-clockwise"""

        if (direction == 1) or (direction == 2):
            # centre point to start
            geolib_start = Geodesic.WGS84.Inverse(center_x, center_y, start_x, start_y)
            start_brg = geolib_start['azi1']
            start_dst = geolib_start['s12']
            start_brg_compass = ((360 + start_brg) % 360)

            # centre point to end
            geolib_end = Geodesic.WGS84.Inverse(center_x, center_y, end_x, end_y)
            end_brg = geolib_end['azi1']
            end_brg_compass = ((360 + end_brg) % 360)
        elif direction == 3: # if direction set to 3, draw a circle
            start_brg = 0
            start_dst = dst * 1852 # convert nautical miles to meters
            end_brg_compass = 359
            direction = 1 # we can set the direction to 1 as the bit of code below can still be used

        arc_out = []
        if direction == 1: # if cw
            while round(start_brg) != round(end_brg_compass):
                arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
                arc_out.append(self.dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
                start_brg = ((start_brg + 1) % 360)
        elif direction == 2: # if acw
            while round(start_brg) != round(end_brg_compass):
                arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
                arc_out.append(self.dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
                start_brg = ((start_brg - 1) % 360)

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
            scrape.append(pd.read_csv('DataFrames/Enr021-FIR.csv', index_col=0))    #4
            scrape.append(pd.read_csv('DataFrames/Enr021-UIR.csv', index_col=0))    #5
            scrape.append(pd.read_csv('DataFrames/Enr021-CTA.csv', index_col=0))    #6
            scrape.append(pd.read_csv('DataFrames/Enr021-TMA.csv', index_col=0))    #7
            scrape.append(pd.read_csv('DataFrames/Enr022-ATZ.csv', index_col=0))    #8
            scrape.append(pd.read_csv('DataFrames/Enr031.csv', index_col=0))        #9
            scrape.append(pd.read_csv('DataFrames/Enr033.csv', index_col=0))        #10
            scrape.append(pd.read_csv('DataFrames/Enr035.csv', index_col=0))        #11
            scrape.append(pd.read_csv('DataFrames/Enr041.csv', index_col=0))        #12
            scrape.append(pd.read_csv('DataFrames/Enr044.csv', index_col=0))        #13
            scrape.append(pd.read_csv('DataFrames/Enr051.csv', index_col=0))        #14
            scrape.append(pd.read_csv('Dataframes/Ad0217-ATS.csv', index_col=0)) #15
            scrape.append(pd.read_csv('DataFrames/AccUac.csv', index_col=0))        #16
            self.scrape = scrape
        else:
            initWebscrape = Webscrape()
            self.scrape = initWebscrape.run()

    def run(self):
        """Build the SCT file"""
        sct_file = "Build/EGxx_FIR.sct"

        def dms2dd(coord_group):
            """Convert dms to dd - N57.12.14.80 W002.12.05.88"""

            # split coord group into lat lon
            group_split = str(coord_group).split(" ")
            lat = re.match(r"([N|S])([\d]{2})\.([\d]{2})\.([\d]{2})\.([\d]{2})", group_split[0])
            lon = re.match(r"([E|W])([\d]{3})\.([\d]{2})\.([\d]{2})\.([\d]{2})", group_split[1])

            lat_dd = lat.group(2)
            lat_mm = lat.group(3)
            lat_ss = lat.group(4) + "." + lat.group(5)

            # lat N or S (+/-) lon E or W (+/-)

            lat_out = int(lat_dd) + int(lat_mm) / 60 + float(lat_ss) / 3600

            lon_dd = lon.group(2)
            lon_mm = lon.group(3)
            lon_ss = lon.group(4) + "." + lon.group(5)

            lon_out = int(lon_dd) + int(lon_mm) / 60 + float(lon_ss) / 3600

            if lat.group(1) == "S":
                lat_out = lat_out - (lat_out * 2)
            if lon.group(1) == "W":
                lon_out = lon_out - (lon_out * 2)

            return [lat_out, lon_out]

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

        def extended_centerline(start_coord, runway_heading, line_length=10):
            """Generate the extended center line from the runway threshold. Line length in NM"""

            # convert start coords to dd
            coords = dms2dd(start_coord)

            # calculate the back bearing
            back_bearing = ((runway_heading + 180) % 360)

            # convert NM to meters (1852m = 1NM)
            distance_meters = line_length * 1852

            start_of_centerline = Geodesic.WGS84.Direct(coords[0], coords[1], back_bearing, distance_meters)
            sct_start_of_line_lat_lon = dd2dms(start_of_centerline["lat2"], start_of_centerline["lon2"])

            ticks = []
            marker = 0
            while marker <= line_length:
                dst_from_start = (line_length - marker) * 1852
                right_angle = ((runway_heading + 90) % 360)
                left_angle = ((right_angle + 180) % 360)
                center_of_tick = Geodesic.WGS84.Direct(coords[0], coords[1], back_bearing, dst_from_start)
                left_tick = Geodesic.WGS84.Direct(center_of_tick["lat2"], center_of_tick["lon2"], right_angle, 200)
                right_tick = Geodesic.WGS84.Direct(center_of_tick["lat2"], center_of_tick["lon2"], left_angle, 200)

                sct_left_tick = dd2dms(left_tick["lat2"], left_tick["lon2"])
                sct_right_tick = dd2dms(right_tick["lat2"], right_tick["lon2"])
                tick = f"{sct_left_tick} {sct_right_tick}"
                ticks.append(tick)
                marker += 1

            return [sct_start_of_line_lat_lon, ticks]

        def rematch(ft, line):
                """re.match strings"""
                if ft == "GEO": # GEO (not REGIONS)
                    return re.match(r"\[GEO\]", line)
                elif ft == "FREETEXT":
                    return re.match(r"\[FREETEXT\]", line)
                elif ft == "REGIONS":
                    return re.match(r"\[REGIONS\]", line)
                else:
                    raise ValueError(f"{ft} has not been recognised")

        def custom_list(file, file_type):
            """modify UK_AIRFIELDS.txt to use custom built sector files where available"""

            custom_airfields = ["EGSS", "EGSC"]
            ignore_line = True
            label_match = False
            
            # strip out any references to the the scraped data
            with open(file) as original_file:
                for line in original_file:
                    if (file_type == "GEO") or (file_type == "FREETEXT"):
                        if not any(custom_airfields in line for custom_airfields in custom_airfields):
                            with open(sct_file, 'a') as write_sct_file:
                                write_sct_file.write(line)
                    elif file_type == "REGIONS":
                        if not label_match: # if we're looking for a matching line, print the line
                            for airfield in custom_airfields:
                                if re.match(f"A-{airfield}", line):
                                    label_match = True
                            if not label_match: # if the line doesn't match the search string then print the line
                                with open(sct_file, 'a') as write_sct_file:
                                    write_sct_file.write(line)
                        elif label_match:
                            counter = 0
                            if re.match(r"A\-", line):
                                for airfield in custom_airfields:
                                    if not re.match(airfield, line):
                                        counter += 1
                                if counter == len(custom_airfields):
                                    label_match = False
         
            # insert the new data
            for airfield in custom_airfields:
                print_line = True
                label_match = False
                custom_file = f"CustomAirfields\\{airfield}.sct"
                with open(custom_file) as c_file:
                    for line in c_file:
                        if (not label_match) and (print_line):
                            if rematch(file_type, line): # once we get to the defined tag
                                label_match = True
                        elif label_match and print_line:
                            with open(sct_file, 'a') as write_sct_file:
                                if re.match(r"\[.*\]", line): # stop whenever we get to the next tag
                                    write_sct_file.write("\n")
                                    print_line = False
                                else:
                                    write_sct_file.write(line)

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
        print("Adding headers...")
        sct_writer('DataFrames/HEADER.txt')
        sct_writer('DataFrames/INFO.txt')

        # VOR section
        print("Adding VOR beacons...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[VOR]\nRANGE 10 3000\n')
            df = self.scrape[12]
            for index, row in df.iterrows():
                write_sct_file.write(f"{row['name']} {row['freq']} {row['coords']}\n")
            write_sct_file.write('\n')
        
        # NDB section

        # AIRPORT section !!!AERODROME AIRSPACE CLASS NEEDS ENTERING PROPERLY - E AS A HOLDING CLASS!!!
        print("Adding airports...")
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
        print("Adding runways...")
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
        print("Adding fixes...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[FIXES]\nRANGE 0 200\n')
            df = self.scrape[13]
            for index, row in df.iterrows():
                write_sct_file.write(f"{row['name']}\t{row['coords']}\n")
            write_sct_file.write('\n')

        # ARTCC section FIR
        print("Adding ARTCC...")
        build_artcc(4, "ARTCC", "100", "5000")

        # ARTCC HIGH section TMA
        print("Adding ARTCC HIGH...")
        build_artcc(7, "ARTCC HIGH", "100", "3000")
        #build_artcc(16, "ARTCC HIGH", "100", "3000")

        # ARTCC LOW section CTA
        print("Adding ARTCC LOW...")
        build_artcc(6, "ARTCC LOW", "0", "2000")
        build_artcc(8, "ARTCC LOW", "0", "2000")
        build_artcc(15, "ARTCC LOW", "0", "2000")

        # SID section

        # STAR section

        # LOW AIRWAY section
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[LOW AIRWAY]\nRANGE 10 200\n')
            write_sct_file.write(';ENR-3.3\n')
            df = self.scrape[10]
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
            df = self.scrape[9]
            for index, row in df.iterrows():
                route = row['route']
                split_route = route.split('/')
                full_route = ''
                for point in split_route:
                    full_route += f"{point}\t"
                write_sct_file.write(f"{row['name']}\t{full_route}\n")
            
            write_sct_file.write(';ENR-3.5\n')
            df = self.scrape[11]
            for index, row in df.iterrows():
                route = row['route']
                split_route = route.split('/')
                full_route = ''
                for point in split_route:
                    full_route += f"{point}\t"
                write_sct_file.write(f"{row['name']}\t{full_route}\n")
            write_sct_file.write('\n')

        # GEO section
        print("Adding GEO...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[GEO]\nRANGE 0 6000\n')
        # UK Geographic Boundary
        sct_writer('DataFrames/UK_NOAA_GEO.txt')
        # Runway Center Lines
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(f'; Runway Extended Center Lines\nRANGE 10 100\n')
            file_in = 'Dataframes/Ad02-Runways.csv'
            df_centerline = pd.read_csv(file_in, index_col=0)

            for index, row in df_centerline.iterrows():
                write_sct_file.write(f"; Extended Center Line for {row['icao_designator']} Rwy {row['runway']}\n")
                location = row['location']
                bearing = row['bearing']
                start = extended_centerline(location, bearing)
                write_sct_file.write(f"{row['icao_designator']}\t{start[0]}\t{location}\tWhite\n")
                for tick in start[1]:
                    write_sct_file.write(f"{row['icao_designator']}\t{tick}\tWhite\n")
                write_sct_file.write('\n')
        # ENR-5.1 DANGER / RESTRICTED areas
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(f';ENR-5.1\nRANGE 0 1500\n')
            df = self.scrape[14]
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
        custom_list('Airfields/UK_AIRFIELDS.txt', 'GEO')

        # REGIONS section
        print("Adding regions...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[REGIONS]\nRANGE 0 20\n')
        # UK Airfields
        custom_list('Airfields/UK_AIRFIELD_REGIONS.txt', 'REGIONS')

        # FREETEXT (labels) section
        print("Adding freetext...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('[FREETEXT]\n')
        
        # VOR labels
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(';VOR Names\nRANGE:10:1000\n')
            df_enr044 = self.scrape[12]
            for index, row in df_enr044.iterrows():
                coords = row['coords']
                write_sct_file.write(f"{coords.replace(' ', ':')}:VOR:{row['name']}\n")
            write_sct_file.write('\n')
        
        # AIRFIELD labels
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write(';Airfield Labels\nRANGE:0:5\n')
        custom_list('Airfields/UK_AIRFIELD_LABELS.txt', 'FREETEXT')

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
        print("Adding positions...")
        with open(sct_file, 'a') as write_sct_file:
            write_sct_file.write('\n\n[POSITIONS]\n')
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

# Build command line argument parser
cmdParse = argparse.ArgumentParser(description="Application to collect data from an AIRAC source and build that into sct files for use on POSCON")
cmdParse.add_argument('-s', '--scrape', help='web scrape and build xml files', action='store_true')
cmdParse.add_argument('-b', '--build', help='build xml file from database', action='store_true')
cmdParse.add_argument('-g', '--geo', help='NoOp', action='store_true')
cmdParse.add_argument('-d', '--debug', help='NoOp', action='store_true')
cmdParse.add_argument('-v', '--verbose', action='store_true')
args = cmdParse.parse_args()

if args.geo:
    pass
elif args.debug:
    pass
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
    new = Airac()
    print(new.url())

    new = Webscrape()
    acc = new.acc_uac_control_sectors()
    print(acc)

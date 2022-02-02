#!/usr/bin/env python3
import math
import datetime
import argparse
from pkgutil import get_data
import shutil
import urllib3
import argparse
import requests
import re
import os
import pandas as pd
import urllib3
from datetime import date
from bs4 import BeautifulSoup
from colorama import Fore, Style
from alive_progress import alive_bar

work_dir = os.getcwd()

def generate_semicircle(center_x, center_y, start_x, start_y, end_x, end_y, direction, dst=2.5):
    """Dreate a semicircle. Direction is 1 for clockwise and 2 for anti-clockwise"""
    from geographiclib.geodesic import Geodesic

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
        print("clockwise")
        while round(start_brg) != round(end_brg_compass):
            arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
            arc_out.append(dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
            start_brg = ((start_brg + 1) % 360)
    elif direction == 2: # if acw
        print("anticlockwise")
        while round(start_brg) != round(end_brg_compass):
            arc_coords = Geodesic.WGS84.Direct(center_x, center_y, start_brg, start_dst)
            arc_out.append(dd2dms(arc_coords['lat2'], arc_coords['lon2'], "1"))
            start_brg = ((start_brg - 1) % 360)

    return arc_out

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

def dms2dd(lat, lon, ns, ew):
    lat_split = split_single(lat)
    lon_split = split_single(lon)

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

def split_single(word):
    return [char for char in str(word)]

def split(word):
        return [char for char in word]

def sct_location_builder(lat, lon, lat_ns, lon_ew):
    """Returns an SCT file compliant location"""
    lat_split = split(lat) # split the lat into individual digits
    if len(lat_split) > 6:
        lat_print = f"{lat_ns}{lat_split[0]}{lat_split[1]}.{lat_split[2]}{lat_split[3]}.{lat_split[4]}{lat_split[5]}.{lat_split[7]}{lat_split[8]}"
    else:
        lat_print = f"{lat_ns}{lat_split[0]}{lat_split[1]}.{lat_split[2]}{lat_split[3]}.{lat_split[4]}{lat_split[5]}.00"

    lon_split = split(lon)
    if len(lon_split) > 7:
        lon_print = f"{lon_ew}{lon_split[0]}{lon_split[1]}{lon_split[2]}.{lon_split[3]}{lon_split[4]}.{lon_split[5]}{lon_split[6]}.{lon_split[8]}{lon_split[9]}"
    else:
        lon_print = f"{lon_ew}{lon_split[0]}{lon_split[1]}{lon_split[2]}.{lon_split[3]}{lon_split[4]}.{lon_split[5]}{lon_split[6]}.00"

    fullLocation = f"{lat_print} {lon_print}" # AD-2.2 gives aerodrome location as DDMMSS / DDDMMSS

    return fullLocation

def getBoundary(space, name=0):
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
                lat_lon = sct_location_builder(lat_lon_obj[0], lat_lon_obj[2], lat_lon_obj[1], lat_lon_obj[3])
                fullBoundary += f"{lat_lon}/"
                draw_line.append(lat_lon)
                lat_lon_obj = []

    return fullBoundary.rstrip('/')

def get_table_soup():
    """Parse the given table into a beautifulsoup object"""
    address = "https://www.aurora.nats.co.uk/htmlAIP/Publications/2021-12-30-AIRAC/html/eAIP/EG-ENR-2.1-en-GB.html"

    http = urllib3.PoolManager()
    error = http.request("GET", address)
    print(error.status)
    if (error.status == 404):
        return 404
    elif (error.status == 503):
        print("Backup Site")
        address = "https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/Current-AIRAC/html/eAIP/EG-ENR-2.1-en-GB.html"

    page = requests.get(address)
    return BeautifulSoup(page.content, "lxml")

# scrape all the data and chuck it in an array
data_out = []
getData = get_table_soup()
searchData = getData.find_all("tr")
for line in searchData:
    for l in line.stripped_strings:
        data_out.append(l)

# pandas init
dfColumns = ['name', 'callsign', 'frequency', 'boundary', 'upper_fl', 'lower_fl', 'class']
df_fir = pd.DataFrame(columns=dfColumns)
df_uir = pd.DataFrame(columns=dfColumns)
df_cta = pd.DataFrame(columns=dfColumns)
df_tma = pd.DataFrame(columns=dfColumns)
df_ctr = pd.DataFrame(columns=dfColumns)
df_atz = pd.DataFrame(columns=dfColumns)

# define some bits
airspace = False
row = 0
last_arc_title = False
arc_counter = 0
space = []
loop_coord = False
first_callsign = False
first_freq = False
upper_limit_out = "000"
lower_limit_out = "000"
airspace_class_out = "E"
count = 0

# actually do something with the data
while count < len(data_out):
    data_to_wrangle = data_out[count]
    title = re.search(r"TAIRSPACE;TXT_NAME", str(data_to_wrangle))
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
        print(print_title)
        airspace = re.search(r"(FIR|UIR|CTA|TMA|CTR|ATZ)", str(data_out[row-1]))
        if airspace:
            df_in_title = print_title
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
        circle = re.search(r"^[A|a]\scircle\,", data_out[count-2])
        anti_clockwise = re.search("anti-clockwise", data_out[count-2])
        if anti_clockwise:
            cacw = 2
        elif circle:
            cacw = 3
        else:
            cacw = 1
              
        radius = data_out[count-1]
        start_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count-4])
        start_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count-6])
        centre_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+4])
        centre_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+6])
        end_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+9])
        end_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+11])

        if centre_lat == None:
            centre_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+2])
            centre_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+4])
            end_lat = re.search(r"([\d]{6,7})(N|S)", data_out[count+7])
            end_lon = re.search(r"([\d]{6,7})(E|W)", data_out[count+9])

        print(cacw, radius, start_lat, start_lon, centre_lat, centre_lon, end_lat, end_lon)

        # convert from dms to dd
        start_dd = dms2dd(start_lat.group(1), start_lon.group(1), start_lat.group(2), start_lon.group(2))
        mid_dd = dms2dd(centre_lat.group(1), centre_lon.group(1), centre_lat.group(2), centre_lon.group(2))
        end_dd = dms2dd(end_lat.group(1), end_lon.group(1), end_lat.group(2), end_lon.group(2))

        arc_out = generate_semicircle(float(mid_dd[0]), float(mid_dd[1]), float(start_dd[0]), float(start_dd[1]), float(end_dd[0]), float(end_dd[1]), cacw)
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

    if (loop_coord) and (space != []):
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

        output = getBoundary(space, last_df_in_title)
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
                df_ctr = df_tma.append(df_ctr_out, ignore_index=True)
            if last_airspace.group(1) == "ATZ":
                df_atz_out = coord_to_table(last_df_in_title, callsign_out, frequency, output, upper_limit_out, lower_limit_out, airspace_class_out)
                df_atz = df_tma.append(df_atz_out, ignore_index=True)
            space = []
            loop_coord = True
            first_callsign = False
            first_freq = False

    if airspace:
        last_df_in_title = print_title
        last_airspace = airspace
    row += 1
    count += 1
df_uir = df_fir

print(df_fir, df_uir, df_cta, df_tma)
full_dir = f"{work_dir}\\DataFrames\\"
df_fir.to_csv(f'{full_dir}Enr021-FIR.csv')
df_uir.to_csv(f'{full_dir}Enr021-UIR.csv')
df_cta.to_csv(f'{full_dir}Enr021-CTA.csv')
df_tma.to_csv(f'{full_dir}Enr021-TMA.csv')

    
exit()

start_lat = []
start_lon = []
start_lat.append("520517")
start_lat.append("N")
start_lon.append("0002124")
start_lon.append("E")

mid_lat = []
mid_lon = []
mid_lat.append("515306")
mid_lat.append("N")
mid_lon.append("0001406")
mid_lon.append("E")

end_lat = []
end_lon = []
end_lat.append("515828")
end_lat.append("N")
end_lon.append("0003314")
end_lon.append("E")

cacw = 1
start_dd = dms2dd(start_lat[0], start_lon[0], start_lat[1], start_lon[1])
if (cacw == 1) or (cacw == 2):
    mid_dd = dms2dd(mid_lat[0], mid_lon[0], mid_lat[1], mid_lon[1])
    end_dd = dms2dd(end_lat[0], end_lon[0], end_lat[1], end_lon[1])
elif cacw == 3:
    mid_dd = start_dd
    end_dd = start_dd

space = generate_semicircle(float(mid_dd[0]), float(mid_dd[1]), float(start_dd[0]), float(start_dd[1]), float(end_dd[0]), float(end_dd[1]), cacw)

output = getBoundary(space)

sector_name = "LONDON STANSTED CTA 1"
draw_line = output.split('/')
n = 0
while n < len(draw_line):
    if (n + 1) < len(draw_line):
        print(f"{sector_name}\t{draw_line[n]}\t{draw_line[n+1]}")
    n += 1
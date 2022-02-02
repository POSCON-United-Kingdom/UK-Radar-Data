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

file_in = 'Dataframes/Ad02-Runways.csv'
df = pd.read_csv(file_in, index_col=0)
file_out = "test.sct"

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

def build_artcc(df, section, range_lo, range_hi):
    colours = ["Black", "Maroon", "Green", "Olive", "Purple", "Teal", "Grey", "Silver", "Red", "Lime", "Blue", "Fuchsia", "Aqua", "White"]
    colour_total = len(colours)
    colour_inc = 0
    with open(file_out, 'a') as write_sct_file:
        write_sct_file.write(f'; Runway Extended Center Lines\nRANGE 10 100\n')

        for index, row in df.iterrows():
            write_sct_file.write(f"; Extended Center Line for {row['icao_designator']} Rwy {row['runway']}\n")
            location = row['location']
            bearing = row['bearing']
            start = extended_centerline(location, bearing)
            write_sct_file.write(f"{row['icao_designator']}\t{start[0]}\t{location}\tWhite\n")
            for tick in start[1]:
                write_sct_file.write(f"{row['icao_designator']}\t{tick}\tWhite\n")
            write_sct_file.write('\n')

build_artcc(df, "ARTCC LOW", "0", "2000")

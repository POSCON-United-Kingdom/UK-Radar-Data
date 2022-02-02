import awkward as ak
import math
import os
import shutil

from time import sleep

work_dir = os.getcwd()

def dd2dms(latitude, longitude):

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
    output = (NorS + str(abs(degrees_y)).zfill(3) + "." + str(minutes_y).zfill(2) + "." + str(seconds_y).zfill(3) + " " + EorW + str(abs(degrees_x)).zfill(3) + "." + str(minutes_x).zfill(2) + "." + str(seconds_x).zfill(3))
    return output

# remove archive file(s)
shutil.rmtree(f'{work_dir}\\Airfields')
os.mkdir(f'{work_dir}\\Airfields')

# set some vars
label = False

# load the json files
json_files = os.listdir(f"{work_dir}\\AirfieldGeoJson\\")
for j in json_files:
    print(f"\n\n{j}")
    airfield_geojson = ak.from_json(f"{work_dir}\\AirfieldGeoJson\\{j}")
    icao = j.split('.')
    #icao = f"{icao[0]}{icao[1]}{icao[2]}{icao[3]}"
    b = 0

    # geojson (osm) object types
    objects = [
        "holding_position",
        "runway",
        "taxiway",
        "helipad",
        "gate",
        "parking_position",
        #"navigationaid",
        "hangar",
        "control_tower",
        "terminal",
        "apron",
        "aerodrome"
    ]

    # iterate over all the feature types
    for obj in reversed(objects):
        for item, props in zip(ak.to_list(airfield_geojson.features.geometry), ak.to_list(airfield_geojson.features.properties)):
            if props["aeroway"] == obj:
                coord_list = []
                shape = item["type"]

                # set the value of coords
                if (shape == "Polygon") or (shape == "MultiPolygon"):
                    coords = item["coordinates"][0]
                else:
                    coords = item["coordinates"]

                # iterate over all the coordinates
                if shape == "Point":
                    start_dms = dd2dms(coords[1], coords[0])
                    coord_list.append(start_dms)
                else:
                    for coord in coords:
                        if len(coord) < 2: # if this is a multi polygon
                            for c in coord[0]:
                                #print(len(coord), c)
                                start_dms = dd2dms(c[1], c[0])
                                coord_list.append(start_dms)
                        elif len(coord) > 2: # if this is a weird multi polygon
                            c_count = 0
                            while c_count < len(coord):
                                #print(len(coord), coord)
                                coord_zero = str(coord[0])
                                coord_zero = coord_zero.strip('[]')
                                coord_zero = coord_zero.split(',')
                                start_dms = dd2dms(float(coord_zero[1]), float(coord_zero[0]))
                                coord_list.append(start_dms)
                                c_count += 2
                        else:
                            #print(len(coord), coord)
                            start_dms = dd2dms(coord[1], coord[0])
                            coord_list.append(start_dms)    
                
                if shape == "Polygon":
                    # if it's a polygon, colour it in!
                    if (obj == "aerodrome"):
                        colour = "Green"
                    elif (obj == "apron"):
                        colour = "Grey"
                    elif (obj == "control_tower"):
                        colour = "Maroon"
                    else:
                        colour = "Black"

                    n = 0
                    list_len = len(coord_list)
                    while n < (list_len - 1):
                        try:
                            with open("Airfields/UK_AIRFIELD_REGIONS.txt", "a") as file:
                                if n == 0: # name this region
                                    file.write(f"A-{icao[0]}-{b}-{obj}\n{colour}")
                                    b += 1
                                file.write(f" {coord_list[n]}\n")
                            n += 1
                        except PermissionError:
                            print("Wait...")
                            sleep(2)
                elif shape == "LineString":
                    # if it's a line, colour it in!
                    if obj == "runway":
                        colour = "0"
                        # if it's a runway (or taxiway) do a bit of code to pop the name in    
                        try:               
                            if props["name"]:
                                label = props["name"]
                            elif props["ref"]:
                                label = props["ref"]
                        except KeyError:
                            label = None                       
                    elif obj == "taxiway":
                        colour = "Blue"
                        try:
                            if props["name"]:
                                label = props["name"]
                            elif props["ref"]:
                                label = props["ref"]
                        except KeyError:
                            label = None
                    elif obj == "parking_position":
                        colour = "Red" # !!!!!!!
                        if props["name"]:
                            label = props["name"]
                        elif props["ref"]:
                            label = props["ref"]  
                    else:
                        colour = "Purple"

                    n = 0
                    list_len = len(coord_list)
                    half_n = round(list_len / 2)
                    if half_n < 1:
                        half_n = 1
                    
                    while n < (list_len - 1):
                        with open("Airfields/UK_AIRFIELDS.txt", "a") as file:
                            if label:
                                label_p = label
                            else:
                                label_p = False
                            file.write(f"{icao[0]}\t{props['aeroway']}\t{label}\t{coord_list[n]}\t{coord_list[n+1]}\t{colour}\n")

                        # print the runway / taxiway name somewhere along the middle of it (in theory)
                        if (n == half_n) and label:
                            with open("Airfields/UK_AIRFIELD_LABELS.txt", "a") as file:
                                file.write(f"{coord_list[0].replace(' ', ':')}:{icao[0]} {props['aeroway']}:{label}\n")

                        n += 1
                elif shape == "Point":
                    n = 0
                    for c in coord_list:
                        # is it a name or ref?
                        try:
                            if props['name']:
                                label = props['name']
                            elif props['ref']:
                                label = props['ref']
                            elif props['parking_position']:
                                label = "HELI"
                            else:
                                label = None
                            with open("Airfields/UK_AIRFIELD_LABELS.txt", "a") as file:
                                if label:
                                    file.write(f"{c.replace(' ', ':')}:{icao[0]} {props['aeroway']}:{label}\n")
                        except KeyError as err:
                            print(err, props)
                        n += 1
# POSCON United Kingdom Division
## UK Radar Data
This repository contains FIR data for use on the POSCON network covering London, Scottish and Swanwick Sectors. The completed SCT file for the United Kingdom FIR is EGxx_FIR.sct.

### References
 - [Configuring a Sector File](https://forums.poscon.net/docs/support/manuals/eram/general/#section-595)
 - [SCT2 File Format](https://vrc.rosscarlson.dev/docs/doc.php?page=appendix_f)
 - [Sector File Formatting](https://vrc.rosscarlson.dev/docs/doc.php?page=appendix_g)

### Folder Structure
 - AirfieldGeoJson
	 - Contains a GeoJSON file for every aerodrome in the [UK eAIP](https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/). In their base format, these files are a pure scrape from [OpenStreetMap](https://www.openstreetmap.org/) using the [Overpass Turbo](https://overpass-turbo.eu/) API.
	 - The builder script uses the files located in this folder as a basis for building Surface Movement Radar (SMR) maps in an SCT file.
	 - These files are only for ground layout and don't include any labels. They can be edited in a text editor or by using an online graphical editor such as [geojson.io](https://geojson.io/).
 - AirfieldOverPass
	 - Contains an XML file for aerodromes to pull the latest [OpenStreetMap](https://www.openstreetmap.org/) data from the [Overpass Turbo](https://overpass-turbo.eu/) API.
	 - These files can only be used with the [Overpass Turbo](https://overpass-turbo.eu/) API.
 - Dataframes
	 - Contains raw data which has been scraped from the [UK eAIP](https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP/) by a script.
	 - These files will be automatically updated by a script for each AIRAC cycle.
 - Scripts
	 - Contains Python scripts to build local and FIR wide SCT files.

|File Name       |Description                         |
|----------------|------------------------------------|
|bulk_image_download.py|Downloads a whole load of images from the eAIP|
|generate.py|The main file which scrapes from the eAIP and builds the SCT files|
|osm_data_parse.py|Converts GeoJSON files to a format useable by generate.py to build SCT files|

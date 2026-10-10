import zipfile
from pathlib import Path
import shapefile

SAMPLES_DIR = Path(__file__).resolve().parent

# 1. Generate sample_survey.kml
kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Bengaluru Tech Park Survey</name>
    <description>Ground survey features for testing geospatial file measurement</description>
    
    <Placemark>
      <name>Parcel Alpha (Polygon)</name>
      <description>Commercial Development Lot</description>
      <ExtendedData>
        <Data name="zone"><value>Commercial-IT</value></Data>
        <Data name="status"><value>Approved</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.5950,12.9700,0
              77.5950,12.9750,0
              77.5900,12.9750,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <Placemark>
      <name>Access Road (LineString)</name>
      <description>Primary arterial roadway connecting north and south gate</description>
      <ExtendedData>
        <Data name="lanes"><value>4</value></Data>
        <Data name="speed_limit"><value>40 km/h</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5900,12.9700,0
          77.5925,12.9725,0
          77.5950,12.9750,0
        </coordinates>
      </LineString>
    </Placemark>

    <Placemark>
      <name>Survey Benchmark BM-01 (Point)</name>
      <description>Permanent survey benchmark on granite pillar</description>
      <ExtendedData>
        <Data name="elevation_msl"><value>920.45</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5925,12.9725,920.45</coordinates>
      </Point>
    </Placemark>

    <Placemark>
      <name>Parcel Beta (Polygon)</name>
      <description>Recreational Green Park</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5960,12.9700,0
              77.5990,12.9700,0
              77.5990,12.9730,0
              77.5960,12.9730,0
              77.5960,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

kml_path = SAMPLES_DIR / "sample_survey.kml"
with open(kml_path, "w", encoding="utf-8") as f:
    f.write(kml_content.strip())
print(f"Generated {kml_path}")


# 2. Generate sample_shapefile.zip
temp_shp_dir = SAMPLES_DIR / "temp_shp"
temp_shp_dir.mkdir(exist_ok=True)

base_name = temp_shp_dir / "plots"

# Create shapefile with Polygon features
with shapefile.Writer(str(base_name), shapeType=shapefile.POLYGON) as w:
    w.field("PLOT_ID", "C", size=20)
    w.field("ZONING", "C", size=20)
    w.field("VALUATION", "N", decimal=2)

    # Plot 1
    w.poly([
        [[77.5900, 12.9700], [77.5950, 12.9700], [77.5950, 12.9750], [77.5900, 12.9750], [77.5900, 12.9700]]
    ])
    w.record("PLOT-101", "Commercial", 5000000.00)

    # Plot 2
    w.poly([
        [[77.5960, 12.9710], [77.5980, 12.9710], [77.5980, 12.9740], [77.5960, 12.9740], [77.5960, 12.9710]]
    ])
    w.record("PLOT-102", "Residential", 3500000.00)

# Write WGS 84 .prj file
wgs84_wkt = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
with open(temp_shp_dir / "plots.prj", "w", encoding="utf-8") as f:
    f.write(wgs84_wkt)

# Package into .zip
zip_path = SAMPLES_DIR / "sample_shapefile.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for ext in [".shp", ".shx", ".dbf", ".prj"]:
        f_path = temp_shp_dir / f"plots{ext}"
        if f_path.exists():
            zipf.write(f_path, arcname=f"plots{ext}")

# Clean up temp files
import shutil
shutil.rmtree(temp_shp_dir, ignore_errors=True)
print(f"Generated {zip_path}")

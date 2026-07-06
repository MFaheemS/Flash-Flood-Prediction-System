"""
Static geographic reference data for Pakistan, used in place of paid/
account-gated datasets (GHSL/WorldPop urbanization, official drainage
infrastructure registries) that aren't available via a free public API.

DISTRICT_TOWNS: real coordinates + approximate population for the district
(or its main town) for every district appearing in the historical
cloudburst events dataset. Used as:
  - the canonical location for each monitored district in the dashboard
    (rather than the noisy mean of scattered historical event coordinates)
  - population anchors for the urbanization-index gravity-model proxy
"""

DISTRICT_TOWNS = {
    "Karachi": {"lat": 24.8607, "lon": 67.0011, "population": 16000000, "province": "Sindh"},
    "Lahore": {"lat": 31.5497, "lon": 74.3436, "population": 13000000, "province": "Punjab"},
    "Faisalabad": {"lat": 31.4180, "lon": 73.0790, "population": 3800000, "province": "Punjab"},
    "Multan": {"lat": 30.1575, "lon": 71.5249, "population": 2100000, "province": "Punjab"},
    "Hyderabad": {"lat": 25.3960, "lon": 68.3578, "population": 1900000, "province": "Sindh"},
    "Gujranwala": {"lat": 32.1877, "lon": 74.1945, "population": 2200000, "province": "Punjab"},
    "Peshawar": {"lat": 34.0151, "lon": 71.5249, "population": 2100000, "province": "Khyber Pakhtunkhwa"},
    "Islamabad": {"lat": 33.6844, "lon": 73.0479, "population": 1200000, "province": "Islamabad"},
    "Quetta": {"lat": 30.1798, "lon": 66.9750, "population": 1140000, "province": "Balochistan"},
    "Sialkot": {"lat": 32.4945, "lon": 74.5229, "population": 750000, "province": "Punjab"},
    "Sukkur": {"lat": 27.7052, "lon": 68.8574, "population": 650000, "province": "Sindh"},
    "Sargodha": {"lat": 32.0836, "lon": 72.6711, "population": 700000, "province": "Punjab"},
    "Larkana": {"lat": 27.5590, "lon": 68.2120, "population": 500000, "province": "Sindh"},
    "Mardan": {"lat": 34.1989, "lon": 72.0404, "population": 400000, "province": "Khyber Pakhtunkhwa"},
    "Kasur": {"lat": 31.1180, "lon": 74.4460, "population": 370000, "province": "Punjab"},
    "Abbottabad": {"lat": 34.1463, "lon": 73.2117, "population": 210000, "province": "Khyber Pakhtunkhwa"},
    "Skardu": {"lat": 35.2971, "lon": 75.6333, "population": 30000, "province": "Gilgit-Baltistan"},
    "Gilgit": {"lat": 35.9221, "lon": 74.3087, "population": 60000, "province": "Gilgit-Baltistan"},
    "Swat": {"lat": 34.7717, "lon": 72.3599, "population": 375000, "province": "Khyber Pakhtunkhwa"},
    "Kohat": {"lat": 33.5900, "lon": 71.4400, "population": 250000, "province": "Khyber Pakhtunkhwa"},
    "Turbat": {"lat": 26.0034, "lon": 63.0480, "population": 150000, "province": "Balochistan"},
    "Gwadar": {"lat": 25.1216, "lon": 62.3254, "population": 90000, "province": "Balochistan"},
    "Panjgur": {"lat": 26.9709, "lon": 64.0973, "population": 45000, "province": "Balochistan"},
    "Chaman": {"lat": 30.9187, "lon": 66.4515, "population": 60000, "province": "Balochistan"},
    "Zhob": {"lat": 31.3411, "lon": 69.4481, "population": 40000, "province": "Balochistan"},
    "DG Khan": {"lat": 30.0561, "lon": 70.6345, "population": 380000, "province": "Punjab"},
    "Mianwali": {"lat": 32.5850, "lon": 71.5440, "population": 130000, "province": "Punjab"},
    "Khairpur": {"lat": 27.5295, "lon": 68.7592, "population": 175000, "province": "Sindh"},
    "Thatta": {"lat": 24.7461, "lon": 67.9243, "population": 100000, "province": "Sindh"},
    "Badin": {"lat": 24.6558, "lon": 68.8378, "population": 130000, "province": "Sindh"},
    "Mansehra": {"lat": 34.3336, "lon": 73.1968, "population": 130000, "province": "Khyber Pakhtunkhwa"},
    "Hunza": {"lat": 36.3167, "lon": 74.6500, "population": 15000, "province": "Gilgit-Baltistan"},
    "Ghizer": {"lat": 36.1667, "lon": 73.7833, "population": 10000, "province": "Gilgit-Baltistan"},
    "Ghanche": {"lat": 35.1667, "lon": 76.3333, "population": 12000, "province": "Gilgit-Baltistan"},
    "Buner": {"lat": 34.6833, "lon": 72.4667, "population": 20000, "province": "Khyber Pakhtunkhwa"},
    # Extra financial/administrative hubs not in the events file but worth
    # monitoring; harmless to include in the watchlist.
    "Rawalpindi": {"lat": 33.5651, "lon": 73.0169, "population": 2300000, "province": "Punjab"},
    "Bahawalpur": {"lat": 29.4000, "lon": 71.6833, "population": 900000, "province": "Punjab"},
}

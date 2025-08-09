# Installation: pip install simfin
# import simfin package
import os

import simfin as sf

# Set your API-key for downloading data.
sf.set_api_key(os.getenv("SIMFIN_API_KEY"))

# Set the local directory where data-files are stored.
# The directory will be created if it does not already exist.
sf.set_data_dir(".")

# Download the data from the SimFin server and load into a Pandas DataFrame.
try:
    sf.load_balance(variant="quarterly")
    sf.load_balance(variant="annual")
    sf.load_cashflow(variant="quarterly")
    sf.load_cashflow(variant="annual")
    sf.load_income(variant="quarterly")
    sf.load_income(variant="annual")

    print("SimFin data loaded successfully.")
except Exception as e:
    print(f"An error occurred while loading SimFin data: {e}")

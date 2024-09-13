import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from azure.storage.blob import BlobServiceClient
import json


# Azure Blob Storage connection string and blob names
CONNECTION_STRING = ""
CONTAINER_NAME = "camileinsightsblob"
SCENARIO_BLOB_NAME = "scenarios_knowledgeBase.json"
LOG_BLOB_NAME = "scenario_updates.log" 


app = Flask(__name__)
app.secret_key = ''  

# Set up a separate logger for scenario updates
logger = logging.getLogger('scenario_logger')
logger.setLevel(logging.INFO)
log_handler = logging.FileHandler('scenario_updates.log')
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)

# Function to upload the log file to Azure Blob Storage
def upload_log_to_blob(container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    
    # Read the local log file
    with open('scenario_updates.log', 'rb') as log_file:
        blob_client.upload_blob(log_file, overwrite=True)

# Function to read JSON data from Azure Blob Storage
def read_json_from_blob(container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Download blob data as a string
    blob_data = blob_client.download_blob().readall()
    return json.loads(blob_data)

# Function to update JSON data in Azure Blob Storage
def update_json_in_blob(data, container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Convert data to JSON and upload to blob
    updated_data = json.dumps(data, indent=4)
    blob_client.upload_blob(updated_data, overwrite=True)

# Function to log changes made to the scenario
def log_scenario_update(scenario_id, original_data, updated_data):
    changes = []
    for key in updated_data:
        if updated_data[key] != original_data[key]:
            changes.append(f"Field '{key}' was updated from '{original_data[key]}' to '{updated_data[key]}'")
    
    if changes:
        logger.info(f"Scenario ID {scenario_id} updated. Changes: " + " | ".join(changes))
    else:
        logger.info(f"Scenario ID {scenario_id} was opened but no changes were made.")
    
    # After logging, upload the log file to Azure Blob Storage
    upload_log_to_blob(CONTAINER_NAME, LOG_BLOB_NAME)

# Route for the home page where users input a Scenario ID
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        scenario_id = request.form.get('scenario_id')
        return redirect(url_for('edit_scenario', scenario_id=scenario_id))
    return render_template('home.html')

# Route to display and edit scenario based on input
@app.route('/edit_scenario/<scenario_id>', methods=['GET', 'POST'])
def edit_scenario(scenario_id):
    data = read_json_from_blob(CONTAINER_NAME, SCENARIO_BLOB_NAME)
    scenario_data = next((item for item in data if item["ScenarioID"] == int(scenario_id)), None)

    if not scenario_data:
        flash(f'Scenario ID {scenario_id} does not exist.', 'danger')
        return redirect(url_for('home'))

    original_data = scenario_data['Sections'].copy()  # Keep a copy of the original data for comparison

    if request.method == 'POST':
        # Retrieve form data and update the scenario
        updated_sections = request.form.to_dict()

        # Convert the updated sections back to lists where necessary
        for key in updated_sections:
            if key in scenario_data['Sections'] and isinstance(scenario_data['Sections'][key], list):
                # Split the string back into a list by new lines
                updated_sections[key] = [line.strip() for line in updated_sections[key].split('\n') if line.strip()]
            else:
                updated_sections[key] = updated_sections[key]

        scenario_data['Sections'] = updated_sections

        # Log changes made to the scenario
        log_scenario_update(scenario_id, original_data, updated_sections)

        # Update the JSON file in the blob
        update_json_in_blob(data, CONTAINER_NAME, SCENARIO_BLOB_NAME)

        # Flash success message and redirect to home page
        flash(f'Successfully updated Scenario ID {scenario_id}.', 'success')
        return redirect(url_for('home'))

    # Prepare sections for display
    sections = {}
    if scenario_data and 'Sections' in scenario_data:
        for key, value in scenario_data['Sections'].items():
            if isinstance(value, list):
                # Join list items with new lines
                cleaned_items = [item.replace('Problem Description:\n', '').strip() for item in value]
                sections[key] = '\n'.join(cleaned_items)
            else:
                sections[key] = value.replace('Problem Description:\n', '').strip()

    return render_template('edit_scenario.html', scenario=scenario_data, sections=sections)

if __name__ == '__main__':
    app.run(debug=True)
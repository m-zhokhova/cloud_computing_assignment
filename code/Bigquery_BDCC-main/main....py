import os
from flask import Flask, render_template, jsonify, request
from google.cloud import bigquery

# Define a writable folder in /tmp for Cloud Run
UPLOAD_FOLDER = "/tmp/static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

bigquery_client = bigquery.Client()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    query = """
        SELECT a.subject_id, a.hadm_id, a.admittime, p.gender, p.dob
        FROM `bigquery-bdcc-main-452910.bdc2_451810.admissions` AS a
        JOIN `bigquery-bdcc-main-452910.patients` AS p
        ON a.subject_id = p.subject_id
        ORDER BY a.admittime DESC
        LIMIT 10
    """
    query_job = bigquery_client.query(query)
    results = query_job.result()

    patients = [{"subject_id": row.subject_id, "hadm_id": row.hadm_id, "admittime": row.admittime, "gender": row.gender, "dob": row.dob} for row in results]

    return render_template("index.html", patients=patients)

# ✅ DO NOT include app.run() in Google Cloud
if __name__ == "__main__":
    app.run(debug=False)
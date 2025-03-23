import os
import uuid
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from google.cloud import bigquery, storage

app = Flask(__name__)

# Set a strong secret key
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")  # Use environment variable for production!

bigquery_client = bigquery.Client()
storage_client = storage.Client()


# Simulated User Database (Replace with real database)
users = {
    "admin": {"password": generate_password_hash("admin123"), "role": "admin"},
    "caregiver": {"password": generate_password_hash("caregiver123"), "role": "caregiver"},
    "patient": {"password": generate_password_hash("patient123"), "role": "patient"},
}

# **Login Page**
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")  # Use .get() to avoid KeyErrors
        password = request.form.get("password")

        if not username or not password:
            return render_template("login.html", error="Username and password are required!")

        # Check if user exists
        if username in users and check_password_hash(users[username]["password"], password):
            #session.clear()  # Clear session before setting new user session
            session["username"] = username
            session["user_role"] = users[username]["role"]

            print(f"✅ Login successful! User: {username}, Role: {session['user_role']}")  # Debugging

            return redirect(url_for("home"))  # Redirect to home after login
        else:
            return render_template("login.html", error="Invalid username or password!")

    return render_template("login.html")

# **Logout Route**
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# **Home Route (Patient Search)**

@app.route("/")
def home():
   # session.clear()
        # Redirect to login if not authenticated
    if "username" not in session:
        print("🔴 User not logged in! Redirecting to login page.")
        return redirect(url_for("login"))

    # print(f"🟢 Logged in as: {session['username']} ({session['user_role']})")  # Debugging

    
    
    search_query = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))  # Default to page 1
    limit = int(request.args.get("limit", 10))  # Default limit 10
    offset = (page - 1) * limit  # Calculate offset

    print(f"Received Search Query: {search_query}")  # Debugging

    # BigQuery SQL using parameterized query
    query = """
        SELECT a.subject_id, a.hadm_id, a.admittime, p.gender, p.dob,P.IDENTITY_DOC
        FROM `bigquery-bdcc-main-453816.bdc2_451810.admissions` AS a
        JOIN `bigquery-bdcc-main-453816.bdc2_451810.patients` AS p
        ON a.subject_id = p.subject_id
        WHERE (@search = '' OR CAST(a.subject_id AS STRING) LIKE @search 
                            OR CAST(a.hadm_id AS STRING) LIKE @search)
        ORDER BY a.admittime DESC
        LIMIT @limit OFFSET @offset
    """

    print(f"Executing Query:\n{query}")  # Print the query for debugging

    query_params = [
        bigquery.ScalarQueryParameter("search", "STRING", f"%{search_query}%"),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        query_job = bigquery_client.query(query, job_config=job_config)
        results = query_job.result()
    except Exception as e:
        print(f"BigQuery Error: {e}")
        return "Error fetching data."

    patients = [
        {
            "subject_id": row.subject_id,
            "hadm_id": row.hadm_id,
            "admittime": row.admittime,
            "gender": row.gender,
            "dob": row.dob,
            "identity_doc": row.IDENTITY_DOC
        }
        for row in results
    ]

    return render_template(
    "index.html",
    patients=patients,
    search_query=search_query,
    page=page,
    limit=limit,
    username=session.get("username")  # Pass username to template
    )

@app.route("/json")
def get_json():
    search_query = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    offset = (page - 1) * limit

    query = f"""
        SELECT a.subject_id, a.hadm_id, a.admittime, p.gender, p.dob,P.IDENTITY_DOC
        FROM `bigquery-bdcc-main-453816.bdc2_451810.admissions` AS a
        JOIN `bigquery-bdcc-main-453816.bdc2_451810.patients` AS p
        ON a.subject_id = p.subject_id
        WHERE CAST(a.subject_id AS STRING) LIKE '%{search_query}%'
          
        ORDER BY a.admittime DESC
        LIMIT {limit} OFFSET {offset}
    """

    print(f"Executing Query:\n{query}")  # Print the query for debugging

    query_job = bigquery_client.query(query)
    results = query_job.result()

    data = [
        {
            "subject_id": row.subject_id,
            "hadm_id": row.hadm_id,
            "admittime": row.admittime,
            "gender": row.gender,
            "dob": row.dob,
            "identity_doc": row.IDENTITY_DOC
        }
        for row in results
    ]

    return jsonify(data)


# 🔹 Fetch Patient Details for Editing
@app.route("/patient/edit/<int:subject_id>")
def edit_patient(subject_id):
    query = f"""
        SELECT subject_id, gender, dob,IDENTITY_DOC
        FROM `bigquery-bdcc-main-453816.bdc2_451810.patients`
        WHERE subject_id = {subject_id}
    """
    query_job = bigquery_client.query(query)
    results = query_job.result()

    # Convert results to list
    patient_data = [
        {
            "subject_id": row.subject_id,
            "gender": row.gender,
            "dob": row.dob,
            "identity_doc": row.IDENTITY_DOC
        }
        for row in results
    ]

    if not patient_data:
        return jsonify({"error": "Patient not found"}), 404

    return jsonify(patient_data[0])  # Return only the first patient




# Set upload folder path
# app.config["UPLOAD_FOLDER"] = "static/uploads/"
# Google Cloud Storage Config
BUCKET_NAME = "bigquery-bdcc-main-453816.appspot.com"  # Replace with your actual bucket name
storage_client = storage.Client()

# Allowed image extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/update_patient/<int:subject_id>", methods=["POST"])
def update_patient(subject_id):
    print(f"🔹 Received update request for Subject ID: {subject_id}")

    data = request.form.to_dict()
    print("🔹 Form Data:", data)

    if "gender" not in data or "dob" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    # Handle image upload to Google Cloud Storage
    image_filename = None
    if "image" in request.files:
        image = request.files["image"]
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)

            # Upload to Google Cloud Storage
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(f"uploads/{filename}")
            blob.upload_from_file(image)
            blob.make_public()  # Make the file publicly accessible

            image_filename = blob.public_url  # Get public URL of uploaded file
            print("🔹 Image uploaded to GCS:", image_filename)

    # Construct the SQL update query
    query = """
        UPDATE `bigquery-bdcc-main-453816.bdc2_451810.patients`
        SET gender = @gender, dob = TIMESTAMP(@dob)
    """

    params = [
        bigquery.ScalarQueryParameter("gender", "STRING", data["gender"]),
        bigquery.ScalarQueryParameter("dob", "TIMESTAMP", data["dob"]),
    ]

    if image_filename:
        query += ", IDENTITY_DOC = @image"
        params.append(bigquery.ScalarQueryParameter("image", "STRING", image_filename))

    query += " WHERE subject_id = @subject_id"
    params.append(bigquery.ScalarQueryParameter("subject_id", "INT64", subject_id))

    print("\n📝 FINAL SQL QUERY:\n", query)
    print("\n📝 PARAMETERS:\n", [p.value for p in params])

    try:
        query_job = bigquery_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
        query_job.result()
        print("✅ Patient updated successfully!")
        return jsonify({
            "message": "Patient updated successfully",
            "query": query,
            "parameters": [p.value for p in params],
            "image_url": image_filename if image_filename else "No image uploaded"
        })
    except Exception as e:
        print(f"❌ BigQuery Update Error: {e}")
        return jsonify({
            "error": str(e),
            "query": query,
            "parameters": [p.value for p in params]
        }), 500
    

@app.route("/patient/details/<int:subject_id>")
def show_patient_details(subject_id):
    query = f"""
        SELECT a.subject_id, a.hadm_id, a.admittime, a.DEATHTIME,
               a.ADMISSION_TYPE, a.ADMISSION_LOCATION, a.DISCHARGE_LOCATION, 
               a.INSURANCE, a.LANGUAGE, a.RELIGION, a.MARITAL_STATUS, 
               a.ETHNICITY, a.EDREGTIME, a.EDOUTTIME, a.DIAGNOSIS, 
               a.HOSPITAL_EXPIRE_FLAG, a.HAS_CHARTEVENTS_DATA,
               p.gender, p.dob
        FROM `bigquery-bdcc-main-453816.bdc2_451810.admissions` AS a
        JOIN `bigquery-bdcc-main-453816.bdc2_451810.patients` AS p
        ON a.subject_id = p.subject_id
        WHERE a.subject_id = {subject_id}
    """
    
    query_job = bigquery_client.query(query)
    results = query_job.result()

    patients = [
        {
            "subject_id": row.subject_id,
            "hadm_id": row.hadm_id,
            "admittime": row.admittime,
            "DEATHTIME": row.DEATHTIME,
            "ADMISSION_TYPE": row.ADMISSION_TYPE,
            "ADMISSION_LOCATION": row.ADMISSION_LOCATION,
            "DISCHARGE_LOCATION": row.DISCHARGE_LOCATION,
            "INSURANCE": row.INSURANCE,
            "LANGUAGE": row.LANGUAGE,
            "RELIGION": row.RELIGION,
            "MARITAL_STATUS": row.MARITAL_STATUS,
            "ETHNICITY": row.ETHNICITY,
            "EDREGTIME": row.EDREGTIME,
            "EDOUTTIME": row.EDOUTTIME,
            "DIAGNOSIS": row.DIAGNOSIS,
            "HOSPITAL_EXPIRE_FLAG": row.HOSPITAL_EXPIRE_FLAG,
            "HAS_CHARTEVENTS_DATA": row.HAS_CHARTEVENTS_DATA,
            "gender": row.gender,
            "dob": row.dob
        }
        for row in results
    ]

    if not patients:
        return jsonify({"error": "Patient not found"}), 404

    return render_template("patient.html", patients=patients)



client = bigquery.Client()

# Fetch questions from BigQuery with filters
def fetch_questions(subject_id, hadm_id, diagnosis):
    query = f"""
        SELECT id,subject_id, hadm_id, diagnosis, question, answer, created_at
        FROM `bigquery-bdcc-main-453816.bdc2_451810.questions`
        WHERE subject_id = @subject_id AND hadm_id = @hadm_id AND diagnosis = @diagnosis
        ORDER BY created_at DESC
        LIMIT 1000
    """
    query_params = [
        bigquery.ScalarQueryParameter("subject_id", "INT64", int(subject_id)),
        bigquery.ScalarQueryParameter("hadm_id", "INT64", int(hadm_id)),
        bigquery.ScalarQueryParameter("diagnosis", "STRING", diagnosis),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    query_job = client.query(query, job_config=job_config)  

    return [dict(row) for row in query_job]

# Route to display the question page
@app.route('/patient/details/question')
def question_page():
    subject_id = request.args.get('subject_id')
    hadm_id = request.args.get('hadm_id')
    diagnosis = request.args.get('diagnosis')

    if not all([subject_id, hadm_id, diagnosis]):
        return "Missing required parameters", 400

    questions = fetch_questions(subject_id, hadm_id, diagnosis)  # Retrieve filtered questions

    return render_template(
        'question.html', 
        subject_id=subject_id, 
        hadm_id=hadm_id, 
        diagnosis=diagnosis, 
        questions=questions,
        username=session.get("username") 
    )

# Route to handle question submission
@app.route("/submit_question", methods=["POST"])
def submit_question():
    data = request.json
    subject_id = data.get("subject_id")
    hadm_id = data.get("hadm_id")
    diagnosis = data.get("diagnosis")
    question = data.get("question")

    if not all([subject_id, hadm_id, diagnosis, question]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    table_id = "bigquery-bdcc-main-453816.bdc2_451810.questions"
    row = {
        "id": str(uuid.uuid4()),  # Generate a unique ID
        "subject_id": int(subject_id),
        "hadm_id": int(hadm_id),
        "diagnosis": diagnosis,
        "question": question,
        "answer": None,  # No answer yet
        "created_at": datetime.datetime.utcnow().isoformat()  # Convert datetime to ISO format
    }

    errors = client.insert_rows_json(table_id, [row])  # Insert into BigQuery

    if errors:
        return jsonify({"success": False, "message": "Database error", "errors": errors}), 500

    return jsonify({"success": True, "message": "Question stored successfully!"})

@app.route("/submit_reply", methods=["POST"])
def submit_reply():
    data = request.json
    question_id = data.get("question_id")  # The existing question ID
    answer = data.get("answer")  # New answer text

    if not question_id or not answer:
        return jsonify({"success": False, "message": "Missing data!"}), 400

    # Debugging: Print the SQL query before execution
    query = """
        UPDATE `bigquery-bdcc-main-453816.bdc2_451810.questions`
        SET answer = @answer, created_at = CURRENT_TIMESTAMP()
        WHERE id = @question_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("answer", "STRING", answer),
            bigquery.ScalarQueryParameter("question_id", "STRING", question_id),
        ]
    )

    try:
        query_job = client.query(query, job_config=job_config)
        query_job.result()  # Wait for completion
        return jsonify({"success": True, "message": "Answer updated successfully!"})
    except Exception as e:
        print("Error executing query:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500
    
if __name__ == "__main__":
    app.run(debug=True)

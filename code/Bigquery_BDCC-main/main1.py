import flask
from flask import Flask, request, jsonify
from google.cloud import bigquery
import socket

app = Flask(__name__)
bigquery_client = bigquery.Client()

# 📌 Fetch latest 10 admissions
@app.route("/admissions")
def get_admissions():
    query = """
        SELECT subject_id, hadm_id, admittime
        FROM `bigquery-bdcc-main-453816.bdc2_451810.admissions`
        ORDER BY admittime DESC
        LIMIT 10
    """
    results = bigquery_client.query(query).result()
    
    data = [{"subject_id": row.subject_id, "hadm_id": row.hadm_id, "admittime": row.admittime} for row in results]
    return jsonify(data)

# 📌 Fetch latest 10 patients
@app.route("/patients")
def get_patients():
    query = """
        SELECT subject_id, dob, gender
        FROM `bigquery-bdcc-main-453816.bdc2_451810.patients`
        ORDER BY dob DESC
        LIMIT 10
    """
    results = bigquery_client.query(query).result()

    data = [{"subject_id": row.subject_id, "dob": row.dob, "gender": row.gender} for row in results]
    return jsonify(data)

# 📌 Add a new patient
@app.route("/patients/add", methods=["POST"])
def add_patient():
    data = request.get_json()
    query = f"""
        SELECT subject_id, user_id, question_text, answer_text
        FROM `bigquery-bdcc-main-453816.bdc2_451810.questions`
        WHERE subject_id = '{data["subject_id"]}'
    """
    results = bigquery_client.query(query).result()

    data = [{"user_id": row.user_id, "question_text": row.question_text, "answer_text": row.answer_text} for row in results]
    return jsonify(data)

# 📌 Add a new question
@app.route("/questions/add", methods=["POST"])
def add_question():
    data = request.get_json()
    query = f"""
        INSERT INTO `bigquery-bdcc-main-453816.bdc2_451810.questions`
        (subject_id, user_id, question_text)
        VALUES ('{data["subject_id"]}', '{data["user_id"]}', '{data["question_text"]}')
    """
    bigquery_client.query(query)
    return jsonify({"message": "Question added successfully!"})

# 📌 Add an answer
@app.route("/questions/answer", methods=["POST"])
def add_answer():
    data = request.get_json()
    query = f"""
        UPDATE `bigquery-bdcc-main-453816.bdc2_451810.questions`
        SET answer_text = '{data["answer_text"]}'
        WHERE subject_id = '{data["subject_id"]}' AND user_id = '{data["user_id"]}'
    """
    bigquery_client.query(query)
    return jsonify({"message": "Answer added successfully!"})

# 📌 Find a Free Port
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to any free port
        return s.getsockname()[1]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
# rule-manager/backend/app/sop_service.py
import google.generativeai as genai
import os

def extract_rules_from_sop(sop_file_path):
    """
    Uses the Gemini 2.5 Pro model to analyze an SOP file and extract rules.

    Args:
        sop_file_path: The path to the uploaded SOP PDF file.

    Returns:
        A list of dictionaries, where each dictionary represents a suggested rule.
    """

    # 1. Upload the file to the Gemini File API
    print(f"Uploading file: {sop_file_path}")
    sop_file = genai.upload_file(path=sop_file_path, display_name="SOP Document")
    print(f"Completed upload: {sop_file.name}")

    # 2. Create the prompt for the model
    prompt = """
    You are a Quality Assurance expert for a manufacturing company that uses SAP Plant Maintenance.
    Analyze the attached SOP document, which describes the correct way to write a maintenance notification.
    Your task is to extract all actionable, mandatory rules from this document.
    
    For each rule you find, generate a JSON object with the following exact keys:
    - "rule_name": A short, descriptive name for the rule in uppercase (e.g., "INCLUDE_ROOT_CAUSE").
    - "source_text": The exact sentence or phrase from the SOP that the rule is based on.
    - "target_field": The part of the notification to inspect. Must be one of: "Short Text", "Long Text", "Notification Type", "Functional Location", "Equipment".
    - "condition": The logical condition to apply. Must be one of: "contains", "does not contain", "matches regex", "is empty", "is not empty", "starts with", "has length greater than".
    - "value": The value to check against (e.g., a keyword, a regex pattern).
    - "feedback_message": A user-friendly message explaining what is wrong if the rule fails.

    Return a JSON array containing these rule objects. Do not include any other text or explanation in your response.
    """

    # 3. Call the generative model
    model = genai.GenerativeModel(model_name='models/gemini-2.5-pro')
    response = model.generate_content([prompt, sop_file])
    
    # 4. Clean up the file from the File API after processing
    genai.delete_file(sop_file.name)
    print(f"Deleted file: {sop_file.name}")

    # The response may include markdown characters (```json ... ```), so we need to clean it.
    cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
    
    return cleaned_json

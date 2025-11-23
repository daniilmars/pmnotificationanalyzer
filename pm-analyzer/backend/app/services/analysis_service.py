import os
import json
import re
import time
import requests
import google.generativeai as genai
from app.models import AnalysisResponse, ProblemDetail
from app.config_manager import get_config

RULE_MANAGER_URL = "http://localhost:5002"

def _fetch_rules_from_manager(notification_type: str) -> list:
    try:
        response = requests.get(f"{RULE_MANAGER_URL}/api/v1/rulesets?notification_type={notification_type}&status=Active")
        response.raise_for_status()
        active_rulesets = response.json()
        if not active_rulesets:
            return []
        latest_ruleset = max(active_rulesets, key=lambda rs: rs.get('version', 0))
        active_ruleset_id = latest_ruleset['id']
        detail_response = requests.get(f"{RULE_MANAGER_URL}/api/v1/rulesets/{active_ruleset_id}")
        detail_response.raise_for_status()
        return detail_response.json().get('rules', [])
    except requests.exceptions.RequestException as e:
        print(f"Could not fetch rules from Rule Manager: {e}")
        return []

def _execute_rules(rules: list, notification_data: dict) -> tuple[int, list]:
    score_adjustment = 0
    problems = []
    field_map = {
        "Short Text": "Description",
        "Long Text": "LongText",
    }
    for rule in rules:
        target_field_key = field_map.get(rule['target_field'])
        if not target_field_key:
            continue
        target_value = str(notification_data.get(target_field_key, ''))
        rule_failed = False
        condition = rule['condition']
        value = rule['value']
        if condition == 'is not empty' and not target_value.strip():
            rule_failed = True
        elif condition == 'contains' and value.lower() not in target_value.lower():
            rule_failed = True
        elif condition == 'starts with' and not target_value.startswith(value):
            rule_failed = True
        elif condition == 'has length greater than' and len(target_value) <= int(value):
            rule_failed = True
        
        if rule_failed:
            score_adjustment += rule['score_impact']
            problems.append(ProblemDetail(field="GENERAL", severity="Major", description=rule['feedback_message']))
    return score_adjustment, problems

def analyze_text(notification_data: dict, language: str = "en") -> AnalysisResponse:
    config = get_config()
    llm_settings = config.get('analysis_llm_settings', {})
    notification_type = notification_data.get('NotificationType', '')
    external_rules = _fetch_rules_from_manager(notification_type)
    rule_score_adjustment, rule_problems = _execute_rules(external_rules, notification_data)
    rules_str = "\n".join([f"- {rule['name']}: {rule.get('description', '')}" for rule in external_rules])

    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")
    details = [f"- Priority: {notification_data.get('PriorityText', 'N/A')}", f"- Description: {notification_data.get('Description', 'N/A')}"]
    structured_data_str = "\n".join(details)
    long_text = notification_data.get('LongText', '')

    prompt = f'''
    You are a meticulous GMP auditor analyzing a maintenance notification.
    Your Task: Analyze the provided data against the 5 pillars of quality (Compliance, Traceability, Root Cause, Product Impact, CAPA) and the mandatory rules. 
    
    Mandatory Rules:
    {rules_str if rules_str else "No specific rules loaded."} 
    
    Analysis Data:
    - Structured Data: {structured_data_str}
    - Long Text: "{long_text}"
    
    Response Format:
    Your response MUST be a single, valid JSON object. Do not include markdown or any other text.
    The JSON object must have keys "score" (integer 0-100), "summary" (string), and "problems" (an array of objects, where each object has keys "field", "severity", and "description").
    CRITICAL: The 'severity' value MUST be one of the following English strings: 'Critical', 'Major', 'Minor', regardless of the output language.
    Ensure all other text in your response is in {output_language}.
    '''.strip()

    max_retries = 2
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(llm_settings.get('model', 'gemini-pro'))
            generation_config = genai.types.GenerationConfig(
                temperature=llm_settings.get('temperature', 0.2),
                response_mime_type="application/json"
            )
            response = model.generate_content(prompt, generation_config=generation_config)
            
            ai_response = AnalysisResponse.model_validate_json(response.text)
            
            ai_response.problems.extend(rule_problems)
            ai_response.score += rule_score_adjustment
            ai_response.score = max(0, min(100, ai_response.score))
            
            return ai_response
        except Exception as e:
            print(f"Attempt {attempt + 1} failed during analysis: {e}")
            if attempt >= max_retries - 1:
                raise e
            time.sleep(1)

def chat_with_assistant(notification_data: dict, question: str, analysis_context: AnalysisResponse, language: str = "en") -> dict:
    config = get_config()
    llm_settings = config.get('chat_llm_settings', {})
    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")
    context_str = "..." # Omitting for brevity as it's not the focus of the fix
    long_text = notification_data.get('LongText', '')
    analysis_problems_str = "\n".join([f"- {p.description}" for p in analysis_context.problems])
    
    prompt = f'''... Answer the user\'s question: "{question}"\n'''.strip()

    try:
        model = genai.GenerativeModel(llm_settings.get('model', 'gemini-pro'))
        response = model.generate_content(prompt)
        return {"answer": response.text.strip()}
    except Exception as e:
        print(f"An error occurred during chat: {e}")
        raise e
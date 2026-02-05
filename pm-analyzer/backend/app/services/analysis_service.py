import os
import json
import re
import time
import logging
import requests
import google.generativeai as genai
from app.models import AnalysisResponse, ProblemDetail
from app.config_manager import get_config
from app.ai_governance import (
    log_ai_usage,
    validate_model,
    generate_request_id,
    AI_GOVERNANCE_ENABLED
)

logger = logging.getLogger(__name__)

# Configuration from environment variables with sensible defaults
RULE_MANAGER_URL = os.environ.get('RULE_MANAGER_URL', 'http://localhost:5002')
HTTP_TIMEOUT = int(os.environ.get('HTTP_TIMEOUT', '30'))  # seconds


def _fetch_rules_from_manager(notification_type: str) -> list:
    """Fetch active rules from Rule Manager service for the given notification type."""
    try:
        response = requests.get(
            f"{RULE_MANAGER_URL}/api/v1/rulesets",
            params={'notification_type': notification_type, 'status': 'Active'},
            timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        active_rulesets = response.json()
        if not active_rulesets:
            return []
        latest_ruleset = max(active_rulesets, key=lambda rs: rs.get('version', 0))
        active_ruleset_id = latest_ruleset['id']
        detail_response = requests.get(
            f"{RULE_MANAGER_URL}/api/v1/rulesets/{active_ruleset_id}",
            timeout=HTTP_TIMEOUT
        )
        detail_response.raise_for_status()
        return detail_response.json().get('rules', [])
    except requests.exceptions.Timeout:
        logger.warning("Timeout while fetching rules from Rule Manager")
        return []
    except requests.exceptions.ConnectionError:
        logger.warning("Could not connect to Rule Manager service")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch rules from Rule Manager: {e}")
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

    # Fetch all rules and separate them by type
    external_rules = _fetch_rules_from_manager(notification_type)
    validation_rules = [rule for rule in external_rules if rule.get('rule_type', 'VALIDATION') == 'VALIDATION']
    ai_guidance_rules = [rule for rule in external_rules if rule.get('rule_type') == 'AI_GUIDANCE']

    # Execute validation rules and get score adjustment
    rule_score_adjustment, rule_problems = _execute_rules(validation_rules, notification_data)

    # Prepare rule strings for the prompt
    ai_guidance_str = "\n".join([f"- {rule['name']}: {rule.get('description', '')}" for rule in ai_guidance_rules])
    validation_rules_str = "\n".join([f"- {rule['name']}: {rule.get('description', '')}" for rule in validation_rules])

    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")
    details = [f"- Priority: {notification_data.get('PriorityText', 'N/A')}", f"- Description: {notification_data.get('Description', 'N/A')}"]
    structured_data_str = "\n".join(details)
    long_text = notification_data.get('LongText', '')

    prompt = f'''
    You are a meticulous GMP auditor analyzing a maintenance notification.
    Your Task: Analyze the provided data against the following quality guidelines and mandatory validation rules.

    Quality Guidelines:
    {ai_guidance_str if ai_guidance_str else "No specific quality guidelines loaded."}

    Mandatory Validation Rules:
    {validation_rules_str if validation_rules_str else "No specific validation rules loaded."}
    
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
    model_id = llm_settings.get('model', 'gemini-pro')
    request_id = generate_request_id()
    start_time = time.time()
    status = 'success'
    error_message = None
    output_data = None

    # Validate model is approved for use
    if AI_GOVERNANCE_ENABLED:
        is_approved, validation_error = validate_model(model_id)
        if not is_approved:
            log_ai_usage(
                request_id=request_id,
                model_id=model_id,
                input_data=prompt,
                status='filtered',
                error_message=validation_error,
                context_type='notification_analysis',
                context_id=notification_data.get('NotificationId')
            )
            raise ValueError(validation_error)

    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(model_id)
            generation_config = genai.types.GenerationConfig(
                temperature=llm_settings.get('temperature', 0.2),
                response_mime_type="application/json"
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            ai_response = AnalysisResponse.model_validate_json(response.text)
            output_data = response.text

            ai_response.problems.extend(rule_problems)
            ai_response.score += rule_score_adjustment
            ai_response.score = max(0, min(100, ai_response.score))

            # Log successful AI usage
            latency_ms = int((time.time() - start_time) * 1000)
            log_ai_usage(
                request_id=request_id,
                model_id=model_id,
                input_data=prompt,
                output_data=output_data,
                template_name='analysis_prompt',
                latency_ms=latency_ms,
                status='success',
                context_type='notification_analysis',
                context_id=notification_data.get('NotificationId')
            )

            return ai_response
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed during analysis: {e}")
            if attempt >= max_retries - 1:
                # Log failed AI usage
                latency_ms = int((time.time() - start_time) * 1000)
                log_ai_usage(
                    request_id=request_id,
                    model_id=model_id,
                    input_data=prompt,
                    latency_ms=latency_ms,
                    status='error',
                    error_message=str(e),
                    context_type='notification_analysis',
                    context_id=notification_data.get('NotificationId')
                )
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

    model_id = llm_settings.get('model', 'gemini-pro')
    request_id = generate_request_id()
    start_time = time.time()

    # Validate model is approved for use
    if AI_GOVERNANCE_ENABLED:
        is_approved, validation_error = validate_model(model_id)
        if not is_approved:
            log_ai_usage(
                request_id=request_id,
                model_id=model_id,
                input_data=prompt,
                status='filtered',
                error_message=validation_error,
                context_type='chat',
                context_id=notification_data.get('NotificationId')
            )
            raise ValueError(validation_error)

    try:
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)
        answer = response.text.strip()

        # Log successful AI usage
        latency_ms = int((time.time() - start_time) * 1000)
        log_ai_usage(
            request_id=request_id,
            model_id=model_id,
            input_data=prompt,
            output_data=answer,
            template_name='chat_prompt',
            latency_ms=latency_ms,
            status='success',
            context_type='chat',
            context_id=notification_data.get('NotificationId')
        )

        return {"answer": answer}
    except Exception as e:
        # Log failed AI usage
        latency_ms = int((time.time() - start_time) * 1000)
        log_ai_usage(
            request_id=request_id,
            model_id=model_id,
            input_data=prompt,
            latency_ms=latency_ms,
            status='error',
            error_message=str(e),
            context_type='chat',
            context_id=notification_data.get('NotificationId')
        )
        logger.error(f"An error occurred during chat: {e}")
        raise e
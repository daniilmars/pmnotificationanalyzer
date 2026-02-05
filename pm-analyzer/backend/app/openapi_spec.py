"""
OpenAPI/Swagger Specification for SAP PM Notification Analyzer API

This module provides the OpenAPI 3.0 specification for all API endpoints.
The specification can be served as JSON or used with Swagger UI.
"""

from flask import Blueprint, jsonify, render_template_string

openapi_bp = Blueprint('openapi', __name__)

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "SAP PM Notification Analyzer API",
        "description": """
## Overview

The SAP PM Notification Analyzer API provides comprehensive access to plant maintenance
notification data, quality analytics, reliability engineering metrics, and FDA 21 CFR Part 11
compliant audit trails.

## Key Features

- **Notification Management**: CRUD operations for SAP PM notifications
- **Quality Analytics**: Data quality scoring with ALCOA+ compliance
- **Reliability Engineering**: MTBF, MTTR, FMEA, and predictive maintenance
- **Audit Trail**: FDA 21 CFR Part 11 compliant change tracking
- **AI Analysis**: AI-powered notification analysis and chat
- **Report Generation**: PDF and CSV report exports

## Authentication

Currently, the API does not require authentication. In production deployments,
implement appropriate authentication mechanisms.

## Rate Limiting

No rate limiting is currently enforced. Implement rate limiting for production use.
        """,
        "version": "2.0.0",
        "contact": {
            "name": "PM Analyzer Support",
            "email": "support@pmanalyzer.example.com"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "http://localhost:5001",
            "description": "Development server"
        },
        {
            "url": "https://api.pmanalyzer.example.com",
            "description": "Production server"
        }
    ],
    "tags": [
        {
            "name": "Notifications",
            "description": "SAP PM Notification operations"
        },
        {
            "name": "Analysis",
            "description": "AI-powered notification analysis"
        },
        {
            "name": "Quality",
            "description": "Data quality analytics and ALCOA+ compliance"
        },
        {
            "name": "Reliability",
            "description": "Reliability engineering metrics (MTBF, MTTR, FMEA)"
        },
        {
            "name": "Audit",
            "description": "FDA 21 CFR Part 11 audit trail"
        },
        {
            "name": "Reports",
            "description": "PDF and CSV report generation"
        },
        {
            "name": "Configuration",
            "description": "Application configuration"
        },
        {
            "name": "System",
            "description": "System health and status"
        }
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["System"],
                "summary": "Health check",
                "description": "Check if the API server is running",
                "operationId": "healthCheck",
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/notifications": {
            "get": {
                "tags": ["Notifications"],
                "summary": "Get all notifications",
                "description": "Retrieve a list of PM notifications with optional pagination",
                "operationId": "getNotifications",
                "parameters": [
                    {
                        "name": "language",
                        "in": "query",
                        "description": "Language code for localized content",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    },
                    {
                        "name": "page",
                        "in": "query",
                        "description": "Page number (1-indexed)",
                        "schema": {"type": "integer", "minimum": 1, "default": 1}
                    },
                    {
                        "name": "page_size",
                        "in": "query",
                        "description": "Items per page",
                        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}
                    },
                    {
                        "name": "paginate",
                        "in": "query",
                        "description": "Return paginated response with metadata",
                        "schema": {"type": "boolean", "default": False}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of notifications",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/NotificationListResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/notifications/{id}": {
            "get": {
                "tags": ["Notifications"],
                "summary": "Get notification details",
                "description": "Retrieve detailed information for a specific notification",
                "operationId": "getNotificationDetail",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": "Notification ID",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "language",
                        "in": "query",
                        "description": "Language code",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Notification details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/NotificationDetail"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/analyze": {
            "post": {
                "tags": ["Analysis"],
                "summary": "Analyze notification quality",
                "description": "Perform AI-powered analysis on a notification",
                "operationId": "analyzeNotification",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AnalysisRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Analysis result",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AnalysisResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/chat": {
            "post": {
                "tags": ["Analysis"],
                "summary": "Chat with AI assistant",
                "description": "Ask questions about a notification analysis",
                "operationId": "chatWithAssistant",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ChatRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Chat response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/quality/notification/{id}": {
            "get": {
                "tags": ["Quality"],
                "summary": "Get notification quality score",
                "description": "Calculate comprehensive quality metrics for a notification",
                "operationId": "getNotificationQuality",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": "Notification ID",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "language",
                        "in": "query",
                        "description": "Language code",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Quality score",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/QualityScore"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/quality/batch": {
            "get": {
                "tags": ["Quality"],
                "summary": "Get batch quality metrics",
                "description": "Calculate aggregate quality metrics for all notifications",
                "operationId": "getBatchQuality",
                "parameters": [
                    {
                        "name": "language",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "Max notifications to analyze",
                        "schema": {"type": "integer", "default": 100, "maximum": 1000}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Batch quality metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BatchQualityResponse"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/quality/dashboard": {
            "get": {
                "tags": ["Quality"],
                "summary": "Get quality dashboard data",
                "description": "Comprehensive quality dashboard with all metrics",
                "operationId": "getQualityDashboard",
                "parameters": [
                    {
                        "name": "language",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 200, "maximum": 500}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Dashboard data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/QualityDashboard"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/reliability/equipment/{equipment_id}/mtbf": {
            "get": {
                "tags": ["Reliability"],
                "summary": "Get MTBF for equipment",
                "description": "Calculate Mean Time Between Failures",
                "operationId": "getEquipmentMTBF",
                "parameters": [
                    {
                        "name": "equipment_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "period_days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 365}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MTBF metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MTBFResponse"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/reliability/equipment/{equipment_id}/mttr": {
            "get": {
                "tags": ["Reliability"],
                "summary": "Get MTTR for equipment",
                "description": "Calculate Mean Time To Repair",
                "operationId": "getEquipmentMTTR",
                "parameters": [
                    {
                        "name": "equipment_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "period_days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 365}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MTTR metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MTTRResponse"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/reliability/fmea": {
            "get": {
                "tags": ["Reliability"],
                "summary": "Get FMEA analysis",
                "description": "Failure Mode and Effects Analysis for all equipment",
                "operationId": "getFMEAAnalysis",
                "parameters": [
                    {
                        "name": "period_days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 365}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 20}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "FMEA items",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/FMEAResponse"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/reliability/dashboard": {
            "get": {
                "tags": ["Reliability"],
                "summary": "Get reliability dashboard",
                "description": "Comprehensive reliability engineering dashboard",
                "operationId": "getReliabilityDashboard",
                "parameters": [
                    {
                        "name": "period_days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 365}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Dashboard data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ReliabilityDashboard"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/audit/changes": {
            "get": {
                "tags": ["Audit"],
                "summary": "Get change history",
                "description": "FDA 21 CFR Part 11 compliant audit trail",
                "operationId": "getChangeHistory",
                "parameters": [
                    {
                        "name": "object_class",
                        "in": "query",
                        "description": "Filter by object class (QMEL, AUFK, etc.)",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "object_id",
                        "in": "query",
                        "description": "Filter by object ID",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "username",
                        "in": "query",
                        "description": "Filter by user",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "from_date",
                        "in": "query",
                        "description": "Start date (YYYYMMDD)",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    },
                    {
                        "name": "to_date",
                        "in": "query",
                        "description": "End date (YYYYMMDD)",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 100}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Change history",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChangeHistoryResponse"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/audit/report": {
            "get": {
                "tags": ["Audit"],
                "summary": "Get audit report",
                "description": "Comprehensive audit report with summary statistics",
                "operationId": "getAuditReport",
                "parameters": [
                    {
                        "name": "from_date",
                        "in": "query",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    },
                    {
                        "name": "to_date",
                        "in": "query",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Audit report",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AuditReport"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        },
        "/api/reports/notification/{notification_id}/pdf": {
            "get": {
                "tags": ["Reports"],
                "summary": "Generate notification PDF report",
                "description": "Generate detailed PDF report for a notification",
                "operationId": "getNotificationPDFReport",
                "parameters": [
                    {
                        "name": "notification_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "language",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["en", "de"], "default": "en"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "PDF file",
                        "content": {
                            "application/pdf": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "503": {"$ref": "#/components/responses/ServiceUnavailable"}
                }
            }
        },
        "/api/reports/audit/pdf": {
            "get": {
                "tags": ["Reports"],
                "summary": "Generate audit PDF report",
                "description": "Generate FDA 21 CFR Part 11 compliant audit PDF report",
                "operationId": "getAuditPDFReport",
                "parameters": [
                    {
                        "name": "from_date",
                        "in": "query",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    },
                    {
                        "name": "to_date",
                        "in": "query",
                        "schema": {"type": "string", "pattern": "^\\d{8}$"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "PDF file",
                        "content": {
                            "application/pdf": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        }
                    },
                    "503": {"$ref": "#/components/responses/ServiceUnavailable"}
                }
            }
        },
        "/api/reports/available": {
            "get": {
                "tags": ["Reports"],
                "summary": "List available reports",
                "description": "Get list of available report types and their status",
                "operationId": "getAvailableReports",
                "responses": {
                    "200": {
                        "description": "Available reports",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AvailableReports"}
                            }
                        }
                    }
                }
            }
        },
        "/api/configuration": {
            "get": {
                "tags": ["Configuration"],
                "summary": "Get configuration",
                "description": "Get current application configuration",
                "operationId": "getConfiguration",
                "responses": {
                    "200": {
                        "description": "Configuration",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Configuration"}
                            }
                        }
                    },
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            },
            "post": {
                "tags": ["Configuration"],
                "summary": "Update configuration",
                "description": "Update application configuration",
                "operationId": "setConfiguration",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Configuration"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Configuration updated",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                }
            }
        }
    },
    "components": {
        "schemas": {
            "NotificationListResponse": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/NotificationSummary"}
                    }
                }
            },
            "NotificationSummary": {
                "type": "object",
                "properties": {
                    "NotificationId": {"type": "string", "example": "10000001"},
                    "NotificationType": {"type": "string", "example": "M1"},
                    "Description": {"type": "string"},
                    "Priority": {"type": "string", "example": "2"},
                    "PriorityText": {"type": "string", "example": "High"},
                    "SystemStatusText": {"type": "string"},
                    "FunctionalLocation": {"type": "string"},
                    "EquipmentNumber": {"type": "string"},
                    "CreationDate": {"type": "string", "format": "date"},
                    "CreatedByUser": {"type": "string"}
                }
            },
            "NotificationDetail": {
                "type": "object",
                "properties": {
                    "NotificationId": {"type": "string"},
                    "NotificationType": {"type": "string"},
                    "Description": {"type": "string"},
                    "LongText": {"type": "string"},
                    "Priority": {"type": "string"},
                    "CreationDate": {"type": "string", "format": "date"},
                    "Equipment": {"$ref": "#/components/schemas/EquipmentInfo"},
                    "FunctionalLocation": {"$ref": "#/components/schemas/FunctionalLocationInfo"},
                    "DamageCodes": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/DamageCode"}
                    },
                    "CauseCodes": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CauseCode"}
                    },
                    "WorkOrders": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/WorkOrder"}
                    }
                }
            },
            "EquipmentInfo": {
                "type": "object",
                "properties": {
                    "EquipmentNumber": {"type": "string"},
                    "Description": {"type": "string"},
                    "Category": {"type": "string"}
                }
            },
            "FunctionalLocationInfo": {
                "type": "object",
                "properties": {
                    "FunctionalLocation": {"type": "string"},
                    "Description": {"type": "string"}
                }
            },
            "DamageCode": {
                "type": "object",
                "properties": {
                    "ItemNumber": {"type": "string"},
                    "ObjectPartGroup": {"type": "string"},
                    "ObjectPart": {"type": "string"},
                    "DamageCodeGroup": {"type": "string"},
                    "DamageCode": {"type": "string"},
                    "Description": {"type": "string"}
                }
            },
            "CauseCode": {
                "type": "object",
                "properties": {
                    "ItemNumber": {"type": "string"},
                    "CauseNumber": {"type": "string"},
                    "CauseCodeGroup": {"type": "string"},
                    "CauseCode": {"type": "string"},
                    "Description": {"type": "string"}
                }
            },
            "WorkOrder": {
                "type": "object",
                "properties": {
                    "OrderNumber": {"type": "string"},
                    "OrderType": {"type": "string"},
                    "Description": {"type": "string"},
                    "StartDate": {"type": "string", "format": "date"},
                    "EndDate": {"type": "string", "format": "date"},
                    "Operations": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Operation"}
                    }
                }
            },
            "Operation": {
                "type": "object",
                "properties": {
                    "OperationNumber": {"type": "string"},
                    "Description": {"type": "string"},
                    "WorkCenter": {"type": "string"},
                    "Duration": {"type": "number"}
                }
            },
            "AnalysisRequest": {
                "type": "object",
                "properties": {
                    "notificationId": {"type": "string"},
                    "notification": {"type": "object"},
                    "language": {"type": "string", "enum": ["en", "de"], "default": "en"}
                }
            },
            "AnalysisResponse": {
                "type": "object",
                "properties": {
                    "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "summary": {"type": "string"},
                    "problems": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Problem"}
                    }
                }
            },
            "Problem": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "description": {"type": "string"},
                    "suggestion": {"type": "string"}
                }
            },
            "ChatRequest": {
                "type": "object",
                "required": ["notification", "question", "analysis"],
                "properties": {
                    "notification": {"type": "object"},
                    "question": {"type": "string"},
                    "analysis": {"type": "object"},
                    "language": {"type": "string", "enum": ["en", "de"], "default": "en"}
                }
            },
            "ChatResponse": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"}
                }
            },
            "QualityScore": {
                "type": "object",
                "properties": {
                    "notification_id": {"type": "string"},
                    "overall_score": {"type": "number"},
                    "completeness_score": {"type": "number"},
                    "accuracy_score": {"type": "number"},
                    "timeliness_score": {"type": "number"},
                    "consistency_score": {"type": "number"},
                    "validity_score": {"type": "number"},
                    "alcoa_compliance": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"}
                    },
                    "issues": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/QualityIssue"}
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "QualityIssue": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {"type": "string"},
                    "impact_score": {"type": "number"}
                }
            },
            "BatchQualityResponse": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "average_score": {"type": "number"},
                    "min_score": {"type": "number"},
                    "max_score": {"type": "number"},
                    "score_distribution": {"type": "object"},
                    "common_issues": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CommonIssue"}
                    },
                    "alcoa_summary": {"type": "object"}
                }
            },
            "CommonIssue": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "field": {"type": "string"},
                    "severity": {"type": "string"},
                    "occurrence_count": {"type": "integer"},
                    "percentage": {"type": "number"}
                }
            },
            "QualityDashboard": {
                "type": "object",
                "properties": {
                    "summary": {"$ref": "#/components/schemas/BatchQualityResponse"},
                    "trends": {"type": "array", "items": {"type": "object"}},
                    "top_issues": {"type": "array", "items": {"$ref": "#/components/schemas/CommonIssue"}},
                    "alcoa_compliance": {"type": "object"},
                    "sample_scores": {"type": "array", "items": {"type": "object"}},
                    "generated_at": {"type": "string", "format": "date-time"}
                }
            },
            "MTBFResponse": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string"},
                    "mtbf_hours": {"type": "number"},
                    "mtbf_days": {"type": "number"},
                    "total_operating_hours": {"type": "number"},
                    "failure_count": {"type": "integer"},
                    "calculation_period_days": {"type": "integer"},
                    "confidence_level": {"type": "string"},
                    "trend": {"type": "string"}
                }
            },
            "MTTRResponse": {
                "type": "object",
                "properties": {
                    "equipment_id": {"type": "string"},
                    "mttr_hours": {"type": "number"},
                    "min_repair_time": {"type": "number"},
                    "max_repair_time": {"type": "number"},
                    "repair_count": {"type": "integer"},
                    "std_deviation": {"type": "number"},
                    "trend": {"type": "string"}
                }
            },
            "FMEAResponse": {
                "type": "object",
                "properties": {
                    "fmea_items": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/FMEAItem"}
                    },
                    "total_count": {"type": "integer"},
                    "period_days": {"type": "integer"}
                }
            },
            "FMEAItem": {
                "type": "object",
                "properties": {
                    "failure_mode": {"type": "string"},
                    "potential_effect": {"type": "string"},
                    "severity": {"type": "integer", "minimum": 1, "maximum": 10},
                    "occurrence": {"type": "integer", "minimum": 1, "maximum": 10},
                    "detection": {"type": "integer", "minimum": 1, "maximum": 10},
                    "rpn": {"type": "integer"},
                    "recommended_action": {"type": "string"},
                    "current_controls": {"type": "string"},
                    "equipment_affected": {"type": "array", "items": {"type": "string"}},
                    "occurrence_count": {"type": "integer"}
                }
            },
            "ReliabilityDashboard": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_equipment": {"type": "integer"},
                            "average_reliability_score": {"type": "number"},
                            "average_availability": {"type": "number"},
                            "critical_risk_count": {"type": "integer"},
                            "high_risk_count": {"type": "integer"}
                        }
                    },
                    "equipment_list": {"type": "array", "items": {"type": "object"}},
                    "attention_required": {"type": "array", "items": {"type": "object"}},
                    "fmea_highlights": {"type": "array", "items": {"type": "object"}},
                    "period_days": {"type": "integer"},
                    "generated_at": {"type": "string", "format": "date-time"}
                }
            },
            "ChangeHistoryResponse": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ChangeEntry"}
                    },
                    "count": {"type": "integer"}
                }
            },
            "ChangeEntry": {
                "type": "object",
                "properties": {
                    "change_number": {"type": "string"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "user": {"type": "string"},
                    "object_type": {"type": "string"},
                    "object_id": {"type": "string"},
                    "change_type": {"type": "string", "enum": ["Created", "Updated", "Deleted"]},
                    "fields_changed": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/FieldChange"}
                    },
                    "transaction_code": {"type": "string"}
                }
            },
            "FieldChange": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "field": {"type": "string"},
                    "old_value": {"type": "string"},
                    "new_value": {"type": "string"}
                }
            },
            "AuditReport": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_changes": {"type": "integer"},
                            "objects_changed": {"type": "integer"},
                            "users_involved": {"type": "integer"},
                            "inserts": {"type": "integer"},
                            "updates": {"type": "integer"},
                            "deletes": {"type": "integer"}
                        }
                    },
                    "by_object_class": {"type": "array", "items": {"type": "object"}},
                    "by_user": {"type": "array", "items": {"type": "object"}}
                }
            },
            "AvailableReports": {
                "type": "object",
                "properties": {
                    "pdf_generation_available": {"type": "boolean"},
                    "reports": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "endpoint": {"type": "string"},
                                "formats": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                }
            },
            "Configuration": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["en", "de"]},
                    "theme": {"type": "string"},
                    "notifications_per_page": {"type": "integer"}
                }
            },
            "Error": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"}
                        }
                    }
                }
            }
        },
        "responses": {
            "BadRequest": {
                "description": "Bad request - invalid parameters",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "NotFound": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "InternalError": {
                "description": "Internal server error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "ServiceUnavailable": {
                "description": "Service unavailable - required dependency not installed",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            }
        }
    }
}


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PM Notification Analyzer API - Swagger UI</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .topbar { display: none; }
        .swagger-ui .info .title { color: #0054a6; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true
            });
        };
    </script>
</body>
</html>
"""


@openapi_bp.route('/openapi.json')
def get_openapi_spec():
    """Return OpenAPI specification as JSON"""
    return jsonify(OPENAPI_SPEC)


@openapi_bp.route('/docs')
def swagger_ui():
    """Serve Swagger UI"""
    return render_template_string(SWAGGER_UI_HTML)


@openapi_bp.route('/redoc')
def redoc():
    """Serve ReDoc documentation"""
    redoc_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PM Notification Analyzer API - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
        <style>body { margin: 0; padding: 0; }</style>
    </head>
    <body>
        <redoc spec-url='/api/openapi.json'></redoc>
        <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
    return render_template_string(redoc_html)


def register_openapi(app):
    """Register OpenAPI blueprint with the Flask app"""
    app.register_blueprint(openapi_bp, url_prefix='/api')

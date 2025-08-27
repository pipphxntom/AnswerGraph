"""
Configuration settings for rule-based intent classification.
"""
from typing import Dict, List, Any

# Define rule-based intents
RULE_INTENTS = [
    "deadline_inquiry",
    "fee_inquiry",
    "program_info",
    "application_process",
    "registration_process",
    "contact_info",
    "campus_services"
]

# Define slot configurations for each intent
INTENT_SLOTS = {
    "deadline_inquiry": ["program", "semester", "campus"],
    "fee_inquiry": ["program", "semester", "campus"],
    "program_info": ["program", "campus"],
    "application_process": ["program", "semester", "campus"],
    "registration_process": ["program", "semester", "campus"],
    "contact_info": ["program", "campus"],
    "campus_services": ["campus", "service"]
}

# Example patterns for each intent
INTENT_PATTERNS = {
    "deadline_inquiry": [
        "when is the deadline for {program}",
        "what is the due date for {program} {semester}",
        "application deadline {program}",
        "when do I need to apply for {program}",
        "last day to register for {program} {semester}",
        "registration deadline {program}",
        "deadline {program} {campus}",
        "due date {program}"
    ],
    "fee_inquiry": [
        "how much does {program} cost",
        "tuition fee for {program}",
        "what are the fees for {program} {semester}",
        "cost of {program} at {campus}",
        "fee structure {program}",
        "payment for {program}",
        "tuition {program} {campus}",
        "program fee {program}"
    ],
    "program_info": [
        "tell me about {program}",
        "information on {program}",
        "details about {program} at {campus}",
        "what is {program}",
        "description of {program}",
        "overview {program}",
        "learn about {program}"
    ],
    "application_process": [
        "how do I apply for {program}",
        "application process for {program}",
        "steps to apply for {program} {semester}",
        "apply {program} {campus}",
        "how to submit application {program}",
        "application procedure {program}"
    ],
    "registration_process": [
        "how do I register for {program}",
        "registration process {program}",
        "enroll in {program} {semester}",
        "steps to register {program}",
        "registration procedure {program} {campus}",
        "how to sign up for {program}"
    ],
    "contact_info": [
        "who do I contact about {program}",
        "contact information for {program}",
        "email for {program} at {campus}",
        "phone number {program}",
        "who to ask about {program}",
        "department contact {program}"
    ],
    "campus_services": [
        "services at {campus}",
        "what services are available at {campus}",
        "{service} at {campus}",
        "where is {service} at {campus}",
        "how to access {service} {campus}",
        "available services {campus}"
    ]
}

# Common values for each slot type to help with pattern matching
SLOT_VALUES = {
    "program": [
        "computer science", "cs", "business", "mba", "psychology", "engineering", 
        "biology", "chemistry", "physics", "mathematics", "math", "english", 
        "history", "political science", "art", "music", "nursing", "medicine",
        "law", "education", "sociology", "anthropology", "economics", "finance",
        "marketing", "accounting", "information technology", "it", "data science",
        "machine learning", "artificial intelligence", "ai", "cybersecurity",
        "biochemistry", "communications", "journalism", "philosophy", "theater",
        "architecture", "dentistry", "pharmacy", "public health", "social work"
    ],
    "semester": [
        "fall", "spring", "summer", "winter", "fall 2025", "spring 2026", 
        "summer 2026", "winter 2025", "fall semester", "spring semester",
        "summer session", "winter session"
    ],
    "campus": [
        "main campus", "downtown", "north", "south", "east", "west", 
        "medical center", "technology park", "satellite campus", "online",
        "virtual", "remote"
    ],
    "service": [
        "library", "cafeteria", "dining hall", "gym", "fitness center", 
        "health center", "counseling", "career services", "tutoring",
        "writing center", "computer lab", "financial aid", "bursar",
        "registrar", "admissions", "housing", "parking", "transportation"
    ]
}

# Statistics tracking for system health
STATS = {
    "total_requests": 0,
    "rule_based_responses": 0,
    "rag_responses": 0,
    "intent_distribution": {},
    "slot_hit_rate": {},
    "avg_response_time": 0,
    "response_times": []
}

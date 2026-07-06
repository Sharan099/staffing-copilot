"""
THE ONE EXERCISE.
Run this once, read every print statement, and you understand agents better
than most people who've used LangChain for 6 months.

Install: pip install anthropic --break-system-packages
Set your key: export ANTHROPIC_API_KEY=sk-ant-...

This is YOUR staffing agent, but with 1 tool and zero frameworks.
"""

import json
from anthropic import Anthropic

client = Anthropic()

# ---------------------------------------------------------
# 1. THE "DATABASE" — this is your mock.Employees from Go
# ---------------------------------------------------------
EMPLOYEES = [
    {
        "name": "Alice",
        "skills": ["Python", "LLM", "RAG"],
        "years": 5,
        "available_from": "November 15, 2026",
        "industries": ["Healthcare", "Finance"],
        "project_history": ["Healthcare RAG chatbot", "Finance fraud detection LLM"],
        "location": "Berlin",
    },
    {
        "name": "Bob",
        "skills": ["Python", "FastAPI"],
        "years": 3,
        "available_from": "March 15, 2026",
        "industries": ["Retail"],
        "project_history": ["E-commerce backend API"],
        "location": "Munich",
    },
    {
        "name": "David",
        "skills": ["Python", "LangGraph"],
        "years": 6,
        "available_from": "September 10, 2026",
        "industries": ["Finance"],
        "project_history": ["Finance risk-scoring agent", "Trading bot orchestration"],
        "location": "Hamburg",
    },
    {
        "name": "Sarah",
        "skills": ["Java", "Spring"],
        "years": 4,
        "available_from": "January 5, 2026",
        "industries": ["Retail"],
        "project_history": ["Inventory management system"],
        "location": "Frankfurt",
    },
    {
        "name": "John",
        "skills": ["Python", "LLM", "LangGraph", "RAG"],
        "years": 7,
        "available_from": "August 1, 2026",
        "industries": ["Healthcare"],
        "project_history": ["Healthcare diagnosis assistant", "Patient records RAG system"],
        "location": "Berlin",
    },
    {
        "name": "Priya",
        "skills": ["Python", "TensorFlow"],
        "years": 4,
        "available_from": "February 20, 2026",
        "industries": ["Manufacturing"],
        "project_history": ["Predictive maintenance model"],
        "location": "Stuttgart",
    },
    {
        "name": "Tom",
        "skills": ["Go", "Kubernetes"],
        "years": 8,
        "available_from": "October 1, 2026",
        "industries": ["Finance"],
        "project_history": ["Payments infrastructure migration"],
        "location": "Cologne",
    },
    {
        "name": "Lena",
        "skills": ["Python", "LLM"],
        "years": 2,
        "available_from": "April 10, 2026",
        "industries": ["Healthcare"],
        "project_history": ["Clinical notes summarizer"],
        "location": "Munich",
    },
    {
        "name": "Marco",
        "skills": ["Python", "RAG", "LangGraph"],
        "years": 5,
        "available_from": "September 25, 2026",
        "industries": ["Healthcare", "Retail"],
        "project_history": ["Healthcare RAG chatbot", "Retail product search agent"],
        "location": "Berlin",
    },
    {
        "name": "Nina",
        "skills": ["JavaScript", "React"],
        "years": 3,
        "available_from": "May 1, 2026",
        "industries": ["Retail"],
        "project_history": ["E-commerce frontend redesign"],
        "location": "Hamburg",
    },
]

# ---------------------------------------------------------
# 2. THE REAL FUNCTION — this is your SearchPeopleTool.Execute
#    Notice: normal Python function. Nothing AI about it.

# ---------------------------------------------------------
def search_people(required_skills):
    print(f"\n[REAL CODE RUNNING] search_people(skills={required_skills})")
    matches = [
        e for e in EMPLOYEES
        if all(skill in e["skills"] for skill in required_skills)
    ]
    print(f"[REAL CODE RESULT] {matches}")
    return matches


def get_availability(required_availability):
    print(f"\n[REAL CODE RUNNING] get_availability(availability={required_availability})")
    matches = [
        e for e in EMPLOYEES
        if any(availability in e["available_from"] for availability in required_availability)
    ]
    print(f"[REAL CODE RESULT] {matches}")
    return matches

def check_project_history(employee_name):
    print(f"\n[REAL CODE RUNNING] check_project_history(employee_name={employee_name})")
    matches = [
        e for e in EMPLOYEES
        if any(name in e["name"] for name in employee_name)
    ]
    print(f"[REAL CODE RESULT] {matches}")
    return matches



# ---------------------------------------------------------
# 3. TELL THE LLM THIS TOOL EXISTS — just a JSON description,
#    not a live connection. The LLM never "sees" your Python.
# ---------------------------------------------------------
tools = [
    {
        "name": "search_people",
        "description": "Search company employees who have ALL the given skills .",
        "input_schema": {
            "type": "object",
            "properties": {
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["required_skills"]
        }
    },

    {
        "name": "get_availability",
        "description": "Search  employees who are available for the project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "required_availability": {
                    "type": "string",
                }
            },
            "required": ["required_availability"]
        }
    },
     {
        "name": "check_project_history",
        "description": "Search project history who are fit for the project .",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_name": {
                    "type": "string",
        
                }
            },
            "required": ["employee_name"]
        }
    }
]

# ---------------------------------------------------------
# 4. THE ORCHESTRATOR LOOP — this is the whole "agent"
# ---------------------------------------------------------
messages = [
    {"role": "user", "content": "find a Blockchain engineer available in Berlin"},
    {"role":"system", "content": "You must call the relevant tools before answering. If no employee matches, say so directly — never invent a name or infer skills that weren't returned by a tool"}
]

while True:
    print("\n[STEP] Calling the LLM with current conversation state...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        tools=tools,
        messages=messages,
    )

    # The LLM's reply becomes part of the conversation state (your "AgentState")
    messages.append({"role": "assistant", "content": response.content})

    # Did the LLM ask for a tool, or just answer in text?
    tool_calls = [block for block in response.content if block.type == "tool_use"]

    if not tool_calls:
        # No tool requested -> LLM gave a final answer -> loop ends
        final_text = next(b.text for b in response.content if b.type == "text")
        print("\n[FINAL ANSWER FROM LLM]:", final_text)
        break

    # The LLM asked for a tool. WE run it, not the LLM.
    tool_results = []
    for call in tool_calls:
        print(f"[LLM REQUESTED TOOL] {call.name} with input {call.input}")

        if call.name == "search_people":
            result = search_people(call.input["required_skills"])
        elif call.name == "get_availability":
            result = get_availability(call.input["required_availability"])
        elif call.name == "check_project_history":
            result = get_availability(call.input["employee_name"])
        else:
            result = {"error": "unknown tool"}

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": json.dumps(result),
        })

        

    # Feed the real result back into the conversation, loop again
    messages.append({"role": "user", "content": tool_results})
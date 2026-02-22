import json

try:
    with open("backend_response_gemini_slow.json", "r") as f:
        data = json.load(f)
    
    print("Status:", data.get("status"))
    print("Intent:", data.get("intent"))
    
    response = data.get("response", "")
    print("\n--- RESPONSE START ---")
    print(response[:2000] + "..." if len(response) > 2000 else response)
    print("--- RESPONSE END ---\n")
    
    chart = data.get("chart")
    if chart:
        print("Chart Type:", chart.get("type"))
        print("Chart Title:", chart.get("title"))
        print("Chart Base64 Length:", len(chart.get("base64", "")))
    else:
        print("No chart found.")

    if data.get("data_used"):
         print("Data Used keys:", data["data_used"].keys())

except Exception as e:
    print(f"Error reading response: {e}")

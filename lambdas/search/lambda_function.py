import json, os, urllib.request, boto3

def handler(event, context):
    question = event["question"]
    secret_name = os.environ["SERPER_SECRET_NAME"]

    secrets = boto3.client("secretsmanager")
    secret_value = secrets.get_secret_value(SecretId=secret_name)["SecretString"]
    serper_key = json.loads(secret_value)["serper-api-key"]

    url = "https://google.serper.dev/search"
    data = json.dumps({"q": question}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "X-API-KEY": serper_key,
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    snippets = [item.get("snippet", "") for item in result.get("organic", [])[:3]]
    return {"search_results": snippets}
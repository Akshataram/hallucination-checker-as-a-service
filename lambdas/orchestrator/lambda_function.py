import json, boto3, hashlib, time, os
from concurrent.futures import ThreadPoolExecutor

MODELS = [
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "meta.llama3-1-70b-instruct-v1:0",
    "mistral.mistral-large-2407-v1:0"
    # Add your exact enabled models from Bedrock Model access page
]

def call_llm(model_id, prompt):
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 512, "temperature": 0.5}
    )
    return resp["output"]["message"]["content"][0]["text"]

def handler(event, context):
    question = event["question"]
    ai_answer = event.get("ai_answer", "")
    cache_key = hashlib.md5((question + ai_answer).encode()).hexdigest()

    table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

    cached = table.get_item(Key={"cache_key": cache_key})
    if "Item" in cached:
        return cached["Item"]["result"]

    prompt = f"Answer accurately and concisely: {question}"
    with ThreadPoolExecutor(max_workers=len(MODELS)) as executor:
        llm_answers = list(executor.map(lambda m: call_llm(m, prompt), MODELS))

    search_resp = boto3.client("lambda").invoke(
        FunctionName=os.environ["SEARCH_LAMBDA_ARN"],
        Payload=json.dumps({"question": question})
    )
    search_results = json.loads(search_resp["Payload"].read())["search_results"]

    decision_payload = {
        "question": question,
        "ai_answer": ai_answer or llm_answers[0],
        "llm_answers": llm_answers,
        "search_results": search_results,
        "cache_key": cache_key,
        "table_name": os.environ["TABLE_NAME"]
    }
    decision_resp = boto3.client("lambda").invoke(
        FunctionName=os.environ["DECISION_LAMBDA_ARN"],
        Payload=json.dumps(decision_payload)
    )
    result = json.loads(decision_resp["Payload"].read())

    boto3.client("s3").put_object(
        Bucket=os.environ["LOG_BUCKET"],
        Key=f"logs/{int(time.time())}.json",
        Body=json.dumps({"input": event, "result": result})
    )

    return {
        "hallucination_score": result.get("hallucination_score", 50),
        "explanation": result.get("explanation", ""),
        "verified_answer": result.get("verified_answer", ""),
        "llm_answers": llm_answers,
        "search_facts": search_results
    }
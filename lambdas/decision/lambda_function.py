import json, boto3, os
from datetime import datetime

def handler(event, context):
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # change if you have newer

    prompt = f"""You are an expert hallucination detector.
Question: {event.get('question', 'N/A')}
User AI answer: {event.get('ai_answer', 'N/A')}
Other LLM answers: {event.get('llm_answers', [])}
Search facts: {event.get('search_results', [])}

Return ONLY valid JSON:
{{"hallucination_score": 0-100, "explanation": "reason in 1-3 sentences", "verified_answer": "corrected or same answer"}}
"""

    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 800, "temperature": 0.3}
    )
    text = response["output"]["message"]["content"][0]["text"]

    try:
        result = json.loads(text.strip())
    except:
        result = {"hallucination_score": 50, "explanation": text[:400], "verified_answer": "Parse failed"}

    if "table_name" in event:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(event["table_name"])
        table.put_item(Item={
            "cache_key": event["cache_key"],
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
            "ttl": int(datetime.utcnow().timestamp()) + 86400
        })

    return result
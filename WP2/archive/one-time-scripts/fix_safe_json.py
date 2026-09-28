with open('extractor.py', 'r') as f:
    content = f.read()

old = """def safe_json(text, default):
    if not text:
        return default
    text = re.sub(r'^```[a-z]*\\n?', '', text.strip(), flags=re.I)
    text = re.sub(r'\\n?```$', '', text.strip())
    try:
        return json.loads(text)
    except Exception:
        # Try to find JSON by scanning for { or [ and matching closing bracket
        for ch, close in [('{', '}'), ('[', ']')]:
            start = text.find(ch)
            if start == -1:
                continue
            end = text.rfind(close)
            if end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass"""

new = """def safe_json(text, default):
    if not text:
        return default
    text = re.sub(r'^```[a-z]*\\n?', '', text.strip(), flags=re.I)
    text = re.sub(r'\\n?```$', '', text.strip())
    try:
        return json.loads(text)
    except Exception:
        # For reasoning models: JSON is usually at the end, use rfind
        for ch, close in [('{', '}'), ('[', ']')]:
            end = text.rfind(close)
            if end == -1:
                continue
            start = text.rfind(ch, 0, end)
            if start != -1 and start < end:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass
        # Fallback: find from the beginning
        for ch, close in [('{', '}'), ('[', ']')]:
            start = text.find(ch)
            if start == -1:
                continue
            end = text.rfind(close)
            if end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass"""

if old in content:
    content = content.replace(old, new)
    with open('extractor.py', 'w') as f:
        f.write(content)
    print('Done')
else:
    print('Pattern not found')

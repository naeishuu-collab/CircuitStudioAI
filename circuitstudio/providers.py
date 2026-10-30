"""Optional OpenAI-compatible/local provider. API keys are read only from environment."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .dsl import circuit_json


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, base_url=None, model=None, api_key=None, timeout=45):
        self.base_url = (base_url or os.getenv("CIRCUITSTUDIO_API_BASE", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("CIRCUITSTUDIO_MODEL", "gpt-4o-mini")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.timeout = timeout
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProviderError("API_BASE は http/https のURLにしてください。")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ProviderError("APIキーを送るHTTP接続は拒否しました。リモートにはHTTPSを使ってください。")

    def generate(self, instruction, schema):
        if not instruction.strip() or len(instruction) > 8000:
            raise ProviderError("指示は1〜8000文字で指定してください。")
        if "api.openai.com" in self.base_url and not self.api_key:
            raise ProviderError("OPENAI_API_KEY が設定されていません。手動DSL入力は引き続き利用できます。")
        prompt = ("日本語の電子回路設計指示をCircuitDSLに変換してください。推測できない部品型番/ピンは追加せず、"
                  "design.unknowns と design.parameters に未確定値を残してください。JSONのみを返してください。\n"
                  f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n指示:\n{instruction}")
        body = json.dumps({"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(self.base_url + "/chat/completions", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(2_000_000))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Provider接続に失敗しました: {type(exc).__name__}") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Providerの応答形式を解釈できません。") from exc
        if not isinstance(content, str):
            raise ProviderError("Provider応答のDSLが文字列ではありません。")
        if content.lstrip().startswith("```"):
            content = content.strip().strip("`")
            if content.lower().startswith("json"):
                content = content[4:].lstrip()
        return content

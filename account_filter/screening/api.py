"""Provider-neutral HTTP client for Decisions and compatible Chat Completions."""
import json
import os
import httpx


def api_key(env_name: str) -> str:
    key = os.getenv(env_name)
    if not key and os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
                key = winreg.QueryValueEx(registry, env_name)[0]
        except OSError:
            pass
    if not key:
        raise ValueError(f'请在 .env 或环境变量配置 {env_name}。')
    return key


async def call_model_api(payload: dict, api: str, transport=None, *,
                         endpoint: str, api_key_env: str, timeout=120) -> dict:
    if api not in ('decisions', 'chat') or not endpoint or not api_key_env:
        raise ValueError('模型调用必须明确提供协议、接口地址和密钥变量名。')
    key = api_key(api_key_env)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        # No automatic retries of paid inference calls.
        response = await client.post(endpoint, headers={'Authorization': 'Bearer ' + key}, json=payload)
        if response.status_code != 200:
            try:
                error = response.json().get('error', {})
                message = error.get('message', '') if isinstance(error, dict) else str(error)
            except (ValueError, AttributeError):
                message = ''
            message = str(message).replace(key, '[redacted]')[:500]
            hints = {401: '密钥无效或未授权', 402: '余额不足', 404: '模型或接口不存在', 429: '请求限流', 413: '请求过大'}
            raise ValueError(f"API HTTP {response.status_code}: {message or hints.get(response.status_code, '请求失败')}")
        try:
            raw = response.json()
        except ValueError as exc:
            raise ValueError('API 返回的内容不是有效 JSON。') from exc
    if 'error' in raw:
        error = raw['error']
        message = error.get('message', '未知错误') if isinstance(error, dict) else str(error)
        raise ValueError('API: ' + str(message).replace(key, '[redacted]')[:500])
    if api == 'chat':
        parsed = json.loads(raw['choices'][0]['message']['content'])
        parsed.update({k: raw.get(k) for k in ('model', 'usage', 'id')})
        return parsed
    return raw

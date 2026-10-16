"""Category-independent two-stage multimodal request building and validation."""
import base64
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from .api import call_model_api
from ..category import validate_category


def validate_protocol(api):
    if api not in ('decisions', 'chat'):
        raise ValueError('必须明确选择支持的模型请求协议：decisions 或 chat。')


def channel_questions(task):
    channel = {'type': 'choice', 'instructions': task['channel_instructions'],
               'criteria': {'yes': task['channel_yes'], 'no': task['channel_no']}}
    probability = {'type': 'noul', 'instructions': task['channel_probability_instructions'],
                   'criteria': {'true': task['channel_yes'], 'false': task['channel_no']}}
    return channel, probability


def video_question(key: str, category) -> dict:
    task = validate_category(category)
    return {'type': 'noul', 'instructions': task['video_instructions'].format(key=key),
            'criteria': {'true': task['video_true'], 'false': task['video_false']}}


def candidate_criterion(key: str, category) -> str:
    return category['candidate_criterion'].format(key=key)


# 中文：仅聊天协议使用。频道为独立的 yes/no 选择；频道概率及各视频为 noul。
# 选择题返回恰含所有选项、总和为 1 的概率分布；不得加解释或 Markdown。
CHAT_OUTPUT_INSTRUCTIONS = (
    'Return only {"answers":{...}}. For channel, independently choose yes or no. '
    'For channel_probability and each video, use {"type":"noul","noul":<0 to 1>}. '
    'For choice questions, use {"type":"choice","choice":<option key>,"probabilities":'
    '{<all option keys>:<probability>}}, summing to 1. No explanations or Markdown. '
    'Evaluate these questions: '
)


def encode_cover(path: Path, side: int) -> str:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((side, side))
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def build_title_request(channel: dict, *, model: str, api: str, context_budget: int, category):
    validate_protocol(api)
    task = validate_category(category)
    if not channel.get('videos'):
        raise ValueError('第一页作品缺失，不能进行标题排序。')
    # 中文：第一轮只看第一页的全部标题，类别判据全部来自显式配置。
    state = [task['title_rules']]
    videos, questions = [], {}
    for index, video in enumerate(channel['videos'], 1):
        key = f'v{index:03d}'
        state.append(json.dumps({'key': key, 'title': video.get('title', '')}, ensure_ascii=False))
        question = video_question(key, task)
        # 中文：第一轮只使用该视频自己的标题；没有账号名称、简介或封面作为辅助。
        question['instructions'] = task['title_video_instructions'].format(key=key)
        questions[key] = question
        videos.append({**video, 'key': key})
    estimate = len(json.dumps({'state': state, 'questions': questions}, ensure_ascii=False).encode('utf-8')) + 1800
    if estimate > context_budget:
        raise ValueError(f'第一页全部标题的估算预算 {estimate} 超过 context_budget {context_budget}；请在 API 配置文件提高预算，不会丢弃标题。')
    payload = {'model': model, 'state': state, 'questions': questions}
    if api == 'chat':
        # 中文：聊天协议仅返回第一轮各视频概率，不返回频道或最佳视频答案。
        output = 'Return only {"answers":{<each video key>:{"type":"noul","noul":<probability from 0 to 1>}}}. Questions: '
        payload = {'model': model, 'messages': [{'role': 'system', 'content': task['title_rules']},
                   {'role': 'user', 'content': '\n'.join(state[1:]) + '\n' + output + json.dumps(questions, ensure_ascii=False)}],
                   'response_format': {'type': 'json_object'}, 'max_tokens': 4096, 'temperature': 0}
    return payload, {'prompt_version': task['version'], 'videos': videos, 'estimated_input_tokens': estimate}


def rank_titles(raw: dict, selection: dict) -> list[dict]:
    answers = raw.get('answers')
    if not isinstance(answers, dict):
        raise ValueError('标题排序响应缺少 answers。')
    ranked = []
    for video in selection['videos']:
        answer = answers.get(video['key'], {})
        if answer.get('type') != 'noul':
            raise ValueError(f"标题排序问题 {video['key']} 未返回 noul 概率。")
        ranked.append({**video, 'title_probability': probability(answer.get('noul'))})
    return sorted(ranked, key=lambda video: video['title_probability'], reverse=True)


def build_request(channel: dict, root: Path, *, model: str, api: str,
                  max_videos: int, image_side: int,
                  context_budget: int, image_tokens: int,
                  require_all: bool = False, category) -> tuple[dict, dict]:
    validate_protocol(api)
    task = validate_category(category)
    if not channel.get('name') or not channel.get('videos'):
        raise ValueError('频道名称或作品缺失，不能调用模型。先完成采集。')
    if not 1 <= max_videos <= 128 or not 64 <= image_side <= 2048:
        raise ValueError('max_videos 需为 1..128，image_side 需为 64..2048。')
    if context_budget <= 0 or image_tokens <= 0:
        raise ValueError('预算和图片 token 估值必须为正数。')
    metadata = {'platform': channel['platform'], 'name': channel['name'][:1000],
                # 中文：展示第一页标题排序后选出的候选；旧资料直接分析时按其保存顺序。
                'bio': channel.get('bio', '')[:4000],
                'scope': channel.get('scope', 'Saved sample; may include pinned posts; not the full history.')}
    state = [task['rules'], json.dumps(metadata, ensure_ascii=False)]
    # 中文：启发式估算（UTF-8 字节数 + 固定图片估值），不是实际 tokenizer 的 token 数。
    used = len(json.dumps(state, ensure_ascii=False).encode('utf-8')) + 1800
    selected = []
    warnings = list(channel.get('warnings', []))
    for video in channel['videos'][:max_videos]:
        key = f'v{len(selected) + 1:03d}'
        cover = root / video['cover_path'] if video.get('cover_path') else None
        description = {'key': key, 'id': video['id'], 'title': video.get('title', '')[:1000],
                       'has_cover': bool(cover and cover.is_file())}
        text = json.dumps(description, ensure_ascii=False)
        question_bytes = len(json.dumps({key: video_question(key, task)}, ensure_ascii=False).encode('utf-8'))
        cost = len(text.encode('utf-8')) + question_bytes + 128 + (image_tokens if description['has_cover'] else 0)
        if used + cost > context_budget:
            if require_all:
                raise ValueError('输入预算装不下全部候选标题和封面；请在 API 配置文件提高 context_budget 或减少 --top-videos。')
            warnings.append('输入预算达到上限，已缩短到页面最前面的作品。')
            break
        state.append(text)
        if description['has_cover']:
            try:
                state.append({'type': 'image_url', 'image_url': {'url': encode_cover(cover, image_side)}})
            except (OSError, ValueError):
                description['has_cover'] = False
                state[-1] = json.dumps(description, ensure_ascii=False)
                warnings.append(f"作品 {video['id']} 封面无法解码，使用标题。")
        selected.append({**video, 'key': key, 'has_cover': description['has_cover'],
                         'cover_path': str(cover.resolve()) if cover else None})
        used += cost
    if not selected:
        raise ValueError('预算过小，装不下一个视频；请在 API 配置文件增加 context_budget。')
    channel_question, probability_question = channel_questions(task)
    questions = {'channel': channel_question, 'channel_probability': probability_question}
    for video in selected:
        questions[video['key']] = video_question(video['key'], task)
    criteria = {v['key']: candidate_criterion(v['key'], task) for v in selected}
    criteria['none'] = task['none_criterion']
    questions['best_video'] = {'type': 'choice', 'instructions': task['best_video_instructions'], 'criteria': criteria}
    payload = {'model': model, 'state': state, 'questions': questions}
    if api == 'chat':
        content = [{'type': 'text', 'text': part} if isinstance(part, str) else part for part in state[1:]]
        content.append({'type': 'text', 'text': CHAT_OUTPUT_INSTRUCTIONS + json.dumps(questions, ensure_ascii=False)})
        # Shared rules belong in the system message; user content contains the evidence.
        payload = {'model': model, 'messages': [{'role': 'system', 'content': task['rules']}, {'role': 'user', 'content': content}],
                   'response_format': {'type': 'json_object'}, 'max_tokens': 4096, 'temperature': 0}
    return payload, {'prompt_version': task['version'], 'videos': selected, 'warnings': warnings, 'estimated_input_tokens': used,
                     'context_budget': context_budget, 'image_side': image_side, 'image_token_estimate': image_tokens}


def probability(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('API 返回了无效概率。')
    return float(value)


def normalize_result(raw: dict, selection: dict, channel: dict, *, category) -> dict:
    task = validate_category(category)
    answers = raw.get('answers')
    if not isinstance(answers, dict):
        raise ValueError('API 缺少 answers 对象。')
    def get_prob(key):
        answer = answers.get(key, {})
        if answer.get('type') != 'noul':
            raise ValueError(f'问题 {key} 没有返回 noul 答案（可能拒答）。')
        return probability(answer.get('noul'))
    def get_choice(key, allowed):
        answer = answers.get(key, {})
        if answer.get('type') != 'choice' or answer.get('choice') not in allowed:
            raise ValueError(f'问题 {key} 返回了无效选择。')
        dist = answer.get('probabilities', {})
        if not isinstance(dist, dict) or set(dist) != allowed:
            raise ValueError(f'问题 {key} 的概率分布不完整。')
        dist = {k: probability(v) for k, v in dist.items()}
        if abs(sum(dist.values()) - 1) > 0.02:
            raise ValueError(f'问题 {key} 的概率分布之和不为1。')
        return answer['choice'], dist

    # 中文：直接使用模型的频道选择，不从频道概率、选择题分布或视频分数推导标签。
    label, _ = get_choice('channel', {'yes', 'no'})
    channel_p = get_prob('channel_probability')
    videos = [{**v, 'relevance_probability': get_prob(v['key'])} for v in selection['videos']]
    best_key, dist = get_choice('best_video', {v['key'] for v in videos} | {'none'})
    selected = next((v for v in videos if v['key'] == best_key), None)
    return {'platform': channel['platform'], 'channel_url': channel['url'], 'channel_name': channel['name'],
            'prompt_version': selection['prompt_version'],
            'collected_at': channel.get('collected_at'), 'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'channel_bio': channel.get('bio', ''), 'channel_probability': channel_p,
            'channel_label': label, 'videos': videos,
            'most_likely_video': selected,
            'best_video_distribution': dist,
            'model': raw.get('model'), 'usage': raw.get('usage', {}),
            'budget': {k: v for k, v in selection.items() if k not in ('videos', 'warnings')},
            'warnings': selection['warnings'] + [task['analysis_warning']]}

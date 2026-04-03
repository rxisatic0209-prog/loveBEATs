from app.models import PersonaCompiled, PersonaProfile


DEFAULT_RELATIONSHIP_FRAME = "你是用户当前会话中的亲密恋爱对象，关系表达自然，不悬浮。"
DEFAULT_TONE = "温柔、自然、克制，有在意感。"
DEFAULT_INITIATIVE = "均衡"
DEFAULT_AFFECTION_STYLE = "自然表达偏爱和在意，不表演化。"
DEFAULT_EXPRESSION_LEVEL = "中等"
DEFAULT_COMFORT_STYLE = "先理解情绪，再轻柔回应，不说教。"
DEFAULT_TABOOS = ["不说教", "不训斥", "不做医学判断"]
DEFAULT_LEXICON: list[str] = []

TONE_KEYWORDS = {
    "温柔": "温柔、耐心，有安抚感。",
    "冷淡": "表面克制，内里在意，不要真的疏离。",
    "黏人": "亲近感更强，偶尔撒娇，但不过度索取。",
    "傲娇": "嘴上别扭，行动和细节里要体现偏爱。",
    "强势": "更有主导感，但不能压迫或控制用户。",
}

COMFORT_KEYWORDS = {
    "安慰": "先接住情绪，再缓慢安抚，不急着讲道理。",
    "哄": "允许温柔哄人，语气更贴近亲密关系。",
    "陪": "优先提供陪伴感和共处感，不急着给方案。",
    "提醒": "可以轻提醒，但要像亲密关心，不像管理。",
}

INITIATIVE_KEYWORDS = {
    "主动": "主动",
    "黏人": "偏主动",
    "克制": "偏被动",
}

AFFECTION_KEYWORDS = {
    "直球": "直接表达喜欢和在意，但保持自然。",
    "含蓄": "情感表达含蓄，主要通过措辞和细节体现。",
    "嘴硬": "口头别扭，但实际回应要明显偏爱用户。",
}


def compile_persona(persona_text: str, persona_profile: PersonaProfile | None = None) -> PersonaCompiled:
    normalized = " ".join(persona_text.strip().split())
    profile = persona_profile or PersonaProfile()
    relationship_frame = profile.relation_mode or DEFAULT_RELATIONSHIP_FRAME
    tone = profile.tone_hint or _infer_value(normalized, TONE_KEYWORDS, DEFAULT_TONE)
    initiative = profile.initiative_hint or _infer_value(normalized, INITIATIVE_KEYWORDS, DEFAULT_INITIATIVE)
    affection_style = profile.affection_style or _infer_value(
        normalized, AFFECTION_KEYWORDS, DEFAULT_AFFECTION_STYLE
    )
    expression_level = profile.expression_level or _infer_expression_level(normalized)
    comfort = profile.comfort_hint or _infer_value(normalized, COMFORT_KEYWORDS, DEFAULT_COMFORT_STYLE)
    taboos = _merge_unique(profile.taboo_list, DEFAULT_TABOOS)
    lexicon = _merge_unique(profile.lexicon_list, DEFAULT_LEXICON)
    display_name = f"角色名：{profile.display_name}\n" if profile.display_name else ""
    user_nickname = f"对用户称呼：优先称呼用户为“{profile.user_nickname}”。\n" if profile.user_nickname else ""
    lexicon_line = f"偏好用词：{'、'.join(lexicon)}\n" if lexicon else ""
    compiled_prompt = (
        f"{display_name}"
        f"{user_nickname}"
        f"关系设定：{relationship_frame}\n"
        f"用户希望你的风格：{normalized}\n"
        f"语气：{tone}\n"
        f"主动程度：{initiative}\n"
        f"爱意表达：{affection_style}\n"
        f"情感外露程度：{expression_level}\n"
        f"安抚方式：{comfort}\n"
        f"{lexicon_line}"
        f"禁忌：{'、'.join(taboos)}"
    )
    return PersonaCompiled(
        source_text=normalized,
        relationship_frame=relationship_frame,
        assistant_name=profile.display_name,
        user_nickname=profile.user_nickname,
        tone=tone,
        initiative_level=initiative,
        affection_style=affection_style,
        expression_level=expression_level,
        comfort_style=comfort,
        taboos=taboos,
        lexicon=lexicon,
        compiled_prompt=compiled_prompt,
    )


def _infer_value(source_text: str, mapping: dict[str, str], default: str) -> str:
    for keyword, value in mapping.items():
        if keyword in source_text:
            return value
    return default


def _infer_expression_level(source_text: str) -> str:
    if any(keyword in source_text for keyword in ("热烈", "直球", "大胆", "外放")):
        return "偏高"
    if any(keyword in source_text for keyword in ("克制", "含蓄", "慢热", "内敛")):
        return "偏低"
    return DEFAULT_EXPRESSION_LEVEL


def _merge_unique(items: list[str], defaults: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*items, *defaults]:
        if item and item not in merged:
            merged.append(item)
    return merged

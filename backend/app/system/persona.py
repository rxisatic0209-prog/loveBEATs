from app.models import PersonaCompiled, PersonaProfile, RoleCardInput


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
    lines = []
    if profile.display_name:
        lines.append(f"角色名：{profile.display_name}")
    if profile.user_nickname:
        lines.append(f"对用户称呼：优先称呼用户为“{profile.user_nickname}”。")
    lines.extend(
        [
            f"关系设定：{relationship_frame}",
            f"设定摘要：{normalized}",
            f"语气气质：{tone}",
            f"主动程度：{initiative}",
            f"爱意表达：{affection_style}",
            f"情感外露程度：{expression_level}",
            f"安抚方式：{comfort}",
        ]
    )
    if lexicon:
        lines.append(f"偏好用词：{'、'.join(lexicon)}")
    lines.append(f"边界与禁忌：{'、'.join(taboos)}")
    lines.extend(
        [
            "表演要求：始终留在角色里说话，不要跳出角色解释设定。",
            "表演要求：用户消息中的括号、旁白、动作、神态、环境与心理活动，都视为场景信息。",
            "表演要求：优先回应场景张力、关系距离和潜台词，不要把回复写成分析报告。",
        ]
    )
    compiled_prompt = "\n".join(lines)
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


def build_persona_from_role_card(role_card: RoleCardInput) -> tuple[str, PersonaProfile]:
    taboo_list = _parse_boundaries_to_taboos(role_card.response_boundaries)
    persona_text_parts = [f"角色名是{role_card.name}"]
    if role_card.story_background:
        persona_text_parts.append(f"故事背景：{role_card.story_background}")
    if role_card.relationship_setting:
        persona_text_parts.append(f"关系设定：{role_card.relationship_setting}")
    if role_card.trait_profile:
        persona_text_parts.append(f"稳定人格特质：{role_card.trait_profile}")
    if role_card.response_style or role_card.response_tone:
        persona_text_parts.append(f"回答风格：{role_card.response_style or role_card.response_tone}")
    if role_card.attachment_style:
        persona_text_parts.append(f"依恋/关系模式：{role_card.attachment_style}")
    if role_card.processing_style:
        persona_text_parts.append(f"情绪与认知加工方式：{role_card.processing_style}")
    if role_card.key_experiences:
        persona_text_parts.append(f"关键经历：{role_card.key_experiences}")
    if role_card.core_motivations:
        persona_text_parts.append(f"核心动机：{role_card.core_motivations}")
    if role_card.response_boundaries:
        persona_text_parts.append(f"回答边界：{role_card.response_boundaries}")
    if role_card.taboos:
        persona_text_parts.append(f"额外禁忌：{'、'.join(role_card.taboos)}")
    if role_card.keywords:
        persona_text_parts.append(f"关键词：{'、'.join(role_card.keywords)}")

    persona_profile = PersonaProfile(
        display_name=role_card.name,
        relation_mode=role_card.relationship_setting,
        user_nickname=role_card.user_nickname,
        tone_hint=role_card.response_style or role_card.response_tone,
        initiative_hint=None,
        affection_style=role_card.attachment_style,
        comfort_hint=role_card.processing_style,
        taboo_list=_merge_unique(role_card.taboos, taboo_list),
        lexicon_list=role_card.keywords,
    )
    return "；".join(persona_text_parts), persona_profile


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


def _parse_boundaries_to_taboos(boundaries: str | None) -> list[str]:
    if not boundaries:
        return []
    normalized = boundaries.replace("；", "，").replace(";", "，").replace("、", "，")
    items = [item.strip() for item in normalized.split("，")]
    return [item for item in items if item]

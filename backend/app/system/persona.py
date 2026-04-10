from __future__ import annotations

from app.models import PersonaCompiled, PersonaProfile, RoleCardInput


DEFAULT_BACKGROUND = "背景信息未提供。"
DEFAULT_TRAIT_PROFILE = "性格特质未提供。"
DEFAULT_ATTACHMENT_STYLE = "关系模式未提供。"
DEFAULT_MAJOR_LIFE_EVENTS = "个人重大事件未提供。"
DEFAULT_RESPONSE_STYLE = "自然、生活化、像真人聊天。"
DEFAULT_INITIATIVE = "依据关系阶段与场景自然拿捏，不刻意过度推进。"
DEFAULT_EXPRESSION_LEVEL = "情感表达自然、有温度，不过度夸张。"
DEFAULT_TABOOS = ["不说教", "不做医学判断", "不跳出角色", "不擅自改写设定"]


def compile_persona(
    persona_or_role_card: str | RoleCardInput,
    persona_profile: PersonaProfile | None = None,
) -> PersonaCompiled | str:
    if isinstance(persona_or_role_card, RoleCardInput):
        persona_text, _ = build_persona_from_role_card(persona_or_role_card)
        return persona_text

    source_text = _normalize_block(persona_or_role_card)
    profile = persona_profile or PersonaProfile()
    relationship_frame = profile.relation_mode or DEFAULT_BACKGROUND
    tone = profile.tone_hint or DEFAULT_RESPONSE_STYLE
    initiative = profile.initiative_hint or DEFAULT_INITIATIVE
    affection_style = profile.affection_style or DEFAULT_TRAIT_PROFILE
    expression_level = profile.expression_level or DEFAULT_EXPRESSION_LEVEL
    comfort_style = profile.comfort_hint or DEFAULT_ATTACHMENT_STYLE
    taboos = _merge_unique(profile.taboo_list, DEFAULT_TABOOS)
    lexicon = _merge_unique(profile.lexicon_list, [])

    lines = [
        "[角色身份]",
        f"- 角色名：{profile.display_name or '未命名角色'}",
    ]
    if profile.user_nickname:
        lines.append(f"- 对用户的称呼：{profile.user_nickname}")
    lines.extend(
        [
            "",
            "[角色卡字段]",
            source_text or "- 未提供额外角色卡字段",
            "",
            "[扮演摘要]",
            f"- 关系与背景：{relationship_frame}",
            f"- 人物性格：{affection_style}",
            f"- 关系模式：{comfort_style}",
            f"- 回答风格：{tone}",
            f"- 回应主动性：{initiative}",
            f"- 情感外露：{expression_level}",
            f"- 边界与禁忌：{'、'.join(taboos)}",
        ]
    )
    if lexicon:
        lines.append(f"- 关键词/口头禅：{'、'.join(lexicon)}")

    compiled_prompt = "\n".join(lines)
    return PersonaCompiled(
        source_text=source_text,
        relationship_frame=relationship_frame,
        assistant_name=profile.display_name,
        user_nickname=profile.user_nickname,
        tone=tone,
        initiative_level=initiative,
        affection_style=affection_style,
        expression_level=expression_level,
        comfort_style=comfort_style,
        taboos=taboos,
        lexicon=lexicon,
        compiled_prompt=compiled_prompt,
    )


def build_persona_from_role_card(role_card: RoleCardInput) -> tuple[str, PersonaProfile]:
    background = _normalize_block(role_card.background) or DEFAULT_BACKGROUND
    trait_profile = _normalize_inline(role_card.trait_profile) or DEFAULT_TRAIT_PROFILE
    attachment_style = _normalize_inline(role_card.attachment_style) or DEFAULT_ATTACHMENT_STYLE
    major_life_events = _normalize_block(role_card.major_life_events) or DEFAULT_MAJOR_LIFE_EVENTS
    response_style = _normalize_inline(role_card.response_style) or DEFAULT_RESPONSE_STYLE

    persona_lines = [
        "- 角色名：" + role_card.name,
        "- 背景设定：" + background,
        "- 稳定人格特质：" + trait_profile,
        "- 关系模式 / 依恋风格：" + attachment_style,
        "- 角色个人重大事件：" + major_life_events,
        "- 回答风格：" + response_style,
    ]
    if role_card.user_nickname:
        persona_lines.insert(1, "- 对用户称呼：" + _normalize_inline(role_card.user_nickname))

    persona_profile = PersonaProfile(
        display_name=role_card.name,
        relation_mode=background,
        user_nickname=_normalize_inline(role_card.user_nickname) or None,
        tone_hint=response_style,
        initiative_hint=DEFAULT_INITIATIVE,
        affection_style=trait_profile,
        expression_level=DEFAULT_EXPRESSION_LEVEL,
        comfort_hint=attachment_style,
        taboo_list=DEFAULT_TABOOS,
        lexicon_list=[],
    )
    return "\n".join(persona_lines), persona_profile


def _merge_unique(items: list[str], defaults: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*items, *defaults]:
        normalized = _normalize_token(item)
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _normalize_inline(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().split())


def _normalize_block(value: str | None) -> str:
    if value is None:
        return ""
    lines = [" ".join(line.strip().split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return _normalize_inline(value).rstrip("。！？；;，,")

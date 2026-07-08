import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, StarTools

from .draw import draw_chart

DEFAULT_GROUP_ID = "default"

MESSAGE_DEFAULTS = {
    "welcome_msg": "欢迎新成员！通过自动审核",
    "reject_reason": "检测到关键词%key%，拒绝申请",
    "decrease_msg": "呜呜呜~ %user_name%(%user_id%)退出了群聊",
    "increase_msg": "恭喜你通过人工审核，欢迎入群~",
}


class JoinManager(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 1. 基础路径配置
        self.plugin_dir = Path(__file__).parent.absolute()
        self.assets_dir = self.plugin_dir / "assets"
        self.data_dir = Path(StarTools.get_data_dir("astrbot_plugin_joinmanager"))
        self.records_file = self.data_dir / "join_records.json"
        self.chart_cache_dir = self.data_dir / "chart_cache"
        self.active_chart_paths: set[Path] = set()

        # 2. 目录检查
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.chart_cache_dir.exists():
            self.chart_cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.assets_dir.exists():
            logger.warning(
                f"[JoinManager] 未找到 assets 目录，自定义字体可能无法加载: {self.assets_dir}"
            )

        # 3. 数据加载
        self.records = self._load_records()

        # 4. 配置加载
        self.welcome_config = self._load_message_templates(
            "welcome_msg", MESSAGE_DEFAULTS["welcome_msg"]
        )
        self.decrease_config = self._load_message_templates(
            "decrease_msg", MESSAGE_DEFAULTS["decrease_msg"]
        )
        self.increase_config = self._load_message_templates(
            "increase_msg", MESSAGE_DEFAULTS["increase_msg"]
        )
        self.reject_reason = self._load_message_templates(
            "reject_reason", MESSAGE_DEFAULTS["reject_reason"]
        )

        self.accept_rules, self.accept_rule_groups = self._load_accept_rules()
        self.reject_rules, self.reject_rule_groups = self._load_reject_rules()
        self.seen_group_request_flags: set[str] = set()
        self.group_name_cache: dict[str, str] = {}
        level_limit = self.config.get("level_limit", {})
        if not isinstance(level_limit, dict):
            level_limit = {}
        self.level_limit_enabled = bool(level_limit.get("enabled", False))
        try:
            self.min_level = int(level_limit.get("min_level", 0))
        except (TypeError, ValueError):
            self.min_level = 0
        self.reject_low_level = bool(level_limit.get("reject_low_level", False))
        self.level_limit_reject_reason = str(
            level_limit.get(
                "reject_reason",
                "您的 QQ 等级过低，未通过本群自动审核。",
            )
        )

    @staticmethod
    def _normalize_group_id(value: Any) -> str:
        group_id = str(value or "").strip()
        if (
            not group_id
            or group_id == "默认"
            or group_id.lower() in {DEFAULT_GROUP_ID, "*"}
        ):
            return DEFAULT_GROUP_ID
        return group_id

    @staticmethod
    def _keywords_from_value(value: Any) -> list[str]:
        if isinstance(value, str):
            raw_keywords = value.replace("，", ",").split(",")
        elif isinstance(value, list):
            raw_keywords = value
        else:
            return []
        return [
            str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()
        ]

    def _group_ids_from_rule(self, item: dict[str, Any]) -> list[str]:
        raw_group_ids = item.get("group_ids")
        if raw_group_ids is None:
            raw_group_ids = item.get("group_id", DEFAULT_GROUP_ID)

        if not isinstance(raw_group_ids, list):
            raw_group_ids = [raw_group_ids]

        group_ids: list[str] = []
        for raw_group_id in raw_group_ids:
            group_id = self._normalize_group_id(raw_group_id)
            if group_id not in group_ids:
                group_ids.append(group_id)

        return group_ids or [DEFAULT_GROUP_ID]

    def _load_message_templates(
        self, config_key: str, default_text: str
    ) -> dict[str, str]:
        raw_list = self.config.get("message_templates", {}).get(config_key, [])
        result: dict[str, str] = {}
        for item in raw_list:
            if not isinstance(item, dict):
                continue

            group_ids = self._group_ids_from_rule(item)
            text = str(item.get("text", ""))
            if text:
                for group_id in group_ids:
                    result[group_id] = text

        if DEFAULT_GROUP_ID not in result:
            result[DEFAULT_GROUP_ID] = default_text
        return result

    def _load_accept_rules(self) -> tuple[dict[str, dict[str, list[str]]], set[str]]:
        raw_rules = self.config.get("accept_rules", [])
        rules: dict[str, dict[str, list[str]]] = {}
        configured_groups: set[str] = set()

        for item in raw_rules:
            if not isinstance(item, dict):
                continue

            group_ids = self._group_ids_from_rule(item)
            configured_groups.update(group_ids)
            if not item.get("enabled", True):
                continue

            category = str(item.get("category", "")).strip()
            keywords = self._keywords_from_value(item.get("keywords", []))
            if not category or not keywords:
                continue

            for group_id in group_ids:
                category_rules = rules.setdefault(group_id, {})
                category_keywords = category_rules.setdefault(category, [])
                for keyword in keywords:
                    if keyword not in category_keywords:
                        category_keywords.append(keyword)

        return rules, configured_groups

    def _load_reject_rules(self) -> tuple[dict[str, list[str]], set[str]]:
        raw_rules = self.config.get("reject_rules", [])
        rules: dict[str, list[str]] = {}
        configured_groups: set[str] = set()

        for item in raw_rules:
            if not isinstance(item, dict):
                continue

            group_ids = self._group_ids_from_rule(item)
            configured_groups.update(group_ids)
            if not item.get("enabled", True):
                continue

            keywords = self._keywords_from_value(item.get("keywords", []))
            for group_id in group_ids:
                group_keywords = rules.setdefault(group_id, [])
                for keyword in keywords:
                    if keyword not in group_keywords:
                        group_keywords.append(keyword)

        return rules, configured_groups

    def get_accept_rules(self, group_id: str) -> dict[str, list[str]]:
        group_id = self._normalize_group_id(group_id)
        if group_id in self.accept_rule_groups:
            return self.accept_rules.get(group_id, {})
        return self.accept_rules.get(DEFAULT_GROUP_ID, {})

    def get_reject_keywords(self, group_id: str) -> list[str]:
        group_id = self._normalize_group_id(group_id)
        if group_id in self.reject_rule_groups:
            return self.reject_rules.get(group_id, [])
        return self.reject_rules.get(DEFAULT_GROUP_ID, [])

    def _load_records(self) -> dict:
        """加载 JSON 统计记录"""
        if self.records_file.exists():
            try:
                with self.records_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载入群记录失败: {e}")
        return {}

    def get_notice_session(
        self,
        event: AstrMessageEvent,
        type: str,  # reject_notice / accept_notice / decrease_notice / increase_notice
    ) -> set[str]:
        """获取需要通知的会话ID"""
        umo = event.unified_msg_origin
        sessions = self.config.get("notice", {}).get(type, [])
        filtered_sessions = {item for item in sessions if item != "origin"}
        if "origin" in sessions:
            filtered_sessions.add(umo)
        return filtered_sessions

    def _save_records(self):
        """保存 JSON 统计记录"""
        try:
            with self.records_file.open("w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存入群记录失败: {e}")

    async def terminate(self):
        self._save_records()

    def _check_permission(self, group_id: str) -> bool:
        """检查会话权限"""
        divide_group = self.config.get("divide_group", {})
        block_method = divide_group.get("block_method", "blacklist")
        control_list = divide_group.get("control_list", [])

        control_list_str = [str(i) for i in control_list]

        if block_method == "whitelist":
            return group_id in control_list_str
        else:
            return group_id not in control_list_str

    def _get_chart_cleanup_seconds(self) -> int:
        try:
            seconds = int(self.config.get("chart_cleanup_seconds", 600))
        except (TypeError, ValueError):
            seconds = 600
        return max(seconds, 1)

    def _build_chart_cache_path(self, group_id: str) -> Path:
        safe_group_id = (
            "".join(char for char in group_id if char.isdigit()) or "unknown"
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return (
            self.chart_cache_dir
            / f"joinmanager_{safe_group_id}_{timestamp}_{uuid4().hex[:8]}.png"
        )

    def _cleanup_chart_cache_sync(self, active_paths: set[Path]):
        cleanup_seconds = self._get_chart_cleanup_seconds()
        if not self.chart_cache_dir.exists():
            return

        expires_before = time.time() - cleanup_seconds
        for chart_path in self.chart_cache_dir.glob("joinmanager_*.png*"):
            try:
                if chart_path in active_paths:
                    continue
                if chart_path.is_file() and chart_path.stat().st_mtime < expires_before:
                    if chart_path.suffix == ".deleting":
                        chart_path.unlink()
                    else:
                        deleting_path = chart_path.with_suffix(
                            f"{chart_path.suffix}.deleting"
                        )
                        chart_path.rename(deleting_path)
                        deleting_path.unlink()
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"[JoinManager] 清理图表缓存失败: {chart_path} | {e}")

    async def _cleanup_chart_cache(self):
        active_paths = set(self.active_chart_paths)
        await asyncio.to_thread(self._cleanup_chart_cache_sync, active_paths)

    def _release_chart_path(self, chart_path: Path | None):
        if chart_path:
            self.active_chart_paths.discard(chart_path)

    def _delete_chart_path_sync(self, chart_path: Path):
        try:
            if chart_path.parent != self.chart_cache_dir:
                return
            if chart_path.is_file():
                deleting_path = chart_path.with_suffix(f"{chart_path.suffix}.deleting")
                chart_path.rename(deleting_path)
                deleting_path.unlink()
        except FileNotFoundError:
            return
        except Exception as e:
            logger.warning(f"[JoinManager] 删除图表缓存失败: {chart_path} | {e}")

    async def _dispose_chart_path(self, chart_path: Path | None):
        if not chart_path:
            return

        self._release_chart_path(chart_path)
        await asyncio.to_thread(self._delete_chart_path_sync, chart_path)

    async def _generate_chart(self, group_id: str, group_name: str = "") -> Path | None:
        """异步绘图包装器"""
        if group_id not in self.records:
            return None

        await self._cleanup_chart_cache()

        group_data = dict(self.records[group_id])
        font_name = self.config.get("font", "cute_font.ttf")
        bg_img = self.config.get("bg_img", "bg.png")
        chart_path = self._build_chart_cache_path(group_id)
        self.active_chart_paths.add(chart_path)
        try:
            success = await asyncio.to_thread(
                draw_chart,
                group_id,
                group_data,
                chart_path,
                self.assets_dir,
                font_name,
                bg_img,
                group_name or group_id,
            )
        except Exception:
            await self._dispose_chart_path(chart_path)
            raise
        if success:
            return chart_path
        await self._dispose_chart_path(chart_path)
        return None

    async def _get_stranger_info(
        self, event: AstrMessageEvent, user_id: str
    ) -> dict[str, Any]:
        """Get stranger profile information through the OneBot client.

        Args:
            event: Current AstrBot message event.
            user_id: QQ user ID to query.

        Returns:
            A normalized user info dict. Fields unavailable from the adapter are
            returned as empty strings.
        """
        info: dict[str, Any] = {
            "user_id": str(user_id),
            "nickname": "",
            "nick": "",
            "sex": "",
            "age": "",
            "level": "",
            "qq_level": "",
            "qid": "",
            "login_days": "",
            "reg_time": "",
            "long_nick": "",
            "country": "",
            "province": "",
            "city": "",
            "profile_available": False,
            "level_available": False,
        }

        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
            AiocqhttpMessageEvent,
        )

        if not isinstance(event, AiocqhttpMessageEvent):
            logger.debug("[JoinManager] 跳过获取陌生人信息：当前事件不是aiocqhttp事件")
            return info

        client = event.bot
        try:
            if not client:
                logger.warning("[JoinManager] 获取陌生人信息失败：bot client 不可用")
                return info

            logger.debug(f"[JoinManager] 调用get_stranger_info: user_id={user_id}")
            resp = await client.call_action("get_stranger_info", user_id=int(user_id))
            if not resp or not isinstance(resp, dict):
                logger.warning(
                    f"[JoinManager] 获取陌生人信息失败：接口返回为空或类型异常，用户 {user_id}"
                )
                return info

            data = resp.get("data")
            if not isinstance(data, dict):
                data = resp
            logger.debug(
                "[JoinManager] get_stranger_info返回字段: "
                f"top={list(resp.keys())}, data={list(data.keys())}"
            )

            aliases = {
                "user_id": ("user_id", "qq", "uin"),
                "nickname": ("nickname", "nick", "name"),
                "nick": ("nick", "nickname", "name"),
                "sex": ("sex", "gender"),
                "age": ("age",),
                "qid": ("qid",),
                "login_days": ("login_days", "loginDays"),
                "reg_time": ("reg_time", "regTime", "register_time"),
                "long_nick": ("long_nick", "longNick", "long_nickname"),
                "country": ("country",),
                "province": ("province",),
                "city": ("city",),
            }
            for target_key, source_keys in aliases.items():
                for source_key in source_keys:
                    value = data.get(source_key)
                    if value not in (None, ""):
                        info[target_key] = value
                        info["profile_available"] = True
                        break

            level = ""
            for source_key in ("level", "qq_level", "qqLevel", "qlevel"):
                value = data.get(source_key)
                if value in (None, ""):
                    continue
                try:
                    level = int(value)
                except (TypeError, ValueError):
                    level = value
                break
            info["level"] = level
            info["qq_level"] = level
            info["level_available"] = level != ""
            if info["level_available"]:
                logger.debug(
                    f"[JoinManager] 成功获取用户等级: user_id={user_id}, level={level}"
                )
            elif self.level_limit_enabled:
                logger.warning(
                    f"[JoinManager] get_stranger_info未返回等级字段，用户 {user_id}"
                )
            else:
                logger.debug(
                    f"[JoinManager] get_stranger_info未返回等级字段，用户 {user_id}"
                )
        except Exception as e:
            logger.error(f"[JoinManager] 获取用户信息API出错: {e}")
        return info

    async def _get_group_info(
        self, event: AstrMessageEvent, group_id: str
    ) -> dict[str, Any]:
        """Get group information through the OneBot client.

        Args:
            event: Current AstrBot message event.
            group_id: QQ group ID to query.

        Returns:
            A normalized group info dict. Fields unavailable from the adapter are
            returned as empty strings.
        """
        info: dict[str, Any] = {
            "group_id": str(group_id),
            "group_name": "",
            "member_count": "",
            "max_member_count": "",
            "group_create_time": "",
            "group_level": "",
            "group_memo": "",
            "group_info_available": False,
        }

        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
            AiocqhttpMessageEvent,
        )

        if not isinstance(event, AiocqhttpMessageEvent):
            logger.debug("[JoinManager] 跳过获取群信息：当前事件不是aiocqhttp事件")
            return info

        client = event.bot
        try:
            if not client:
                logger.warning("[JoinManager] 获取群信息失败：bot client 不可用")
                return info

            logger.debug(f"[JoinManager] 调用get_group_info: group_id={group_id}")
            resp = await client.call_action("get_group_info", group_id=int(group_id))
            if not resp or not isinstance(resp, dict):
                logger.warning(
                    f"[JoinManager] 获取群信息失败：接口返回为空或类型异常，群 {group_id}"
                )
                return info

            data = resp.get("data")
            if not isinstance(data, dict):
                data = resp
            logger.debug(
                "[JoinManager] get_group_info返回字段: "
                f"top={list(resp.keys())}, data={list(data.keys())}"
            )

            aliases = {
                "group_id": ("group_id", "groupId"),
                "group_name": ("group_name", "groupName", "name"),
                "member_count": ("member_count", "memberCount"),
                "max_member_count": ("max_member_count", "maxMemberCount"),
                "group_create_time": ("group_create_time", "groupCreateTime"),
                "group_level": ("group_level", "groupLevel"),
                "group_memo": ("group_memo", "groupMemo", "memo"),
            }
            for target_key, source_keys in aliases.items():
                for source_key in source_keys:
                    value = data.get(source_key)
                    if value not in (None, ""):
                        info[target_key] = value
                        info["group_info_available"] = True
                        break
        except Exception as e:
            logger.warning(f"[JoinManager] 获取群信息API出错: {e}")
        return info

    async def _get_group_name(self, event: AstrMessageEvent, group_id: str) -> str:
        """Get group name.

        Args:
            event: Current AstrBot message event.
            group_id: QQ group ID to query.

        Returns:
            Group name when available, otherwise the group ID.
        """
        if group_id in self.group_name_cache:
            return self.group_name_cache[group_id]

        info = await self._get_group_info(event, group_id)
        group_name = str(info.get("group_name") or "").strip()
        if group_name:
            self.group_name_cache[group_id] = group_name
            logger.debug(f"[JoinManager] 成功获取群名称: {group_name} ({group_id})")
            return group_name

        logger.debug(f"[JoinManager] 未获取到群名称，使用群号兜底: {group_id}")
        return group_id

    async def _get_user_nickname(self, event: AstrMessageEvent, user_id: str) -> str:
        """Get user nickname.

        Args:
            event: Current AstrBot message event.
            user_id: QQ user ID to query.

        Returns:
            User nickname when available, otherwise an empty string.
        """
        info = await self._get_stranger_info(event, user_id)
        nick = info.get("nickname") or info.get("nick")
        return str(nick) if nick else ""

    # ------------------ 占位符处理逻辑 ------------------

    def _format_placeholder(
        self,
        text: str,
        group_id: str,
        user_id: str,
        user_name: str = "",
        group_name: str = "",
        extra: dict[str, str] | None = None,
    ) -> str:
        """
        统一的占位符替换方法
        支持: %group_id%, %user_id%, %user_name%
        extra: 额外的替换键值对，如 {"%key%": "keyword"}
        """
        if not text:
            return ""

        mapping = {
            r"%group_id%": str(group_id),
            r"%group_name%": str(group_name or group_id),
            r"%user_id%": str(user_id),
            r"%user_name%": str(user_name),
        }

        if extra:
            mapping.update(extra)

        for k, v in mapping.items():
            text = text.replace(k, str(v))
        return text

    def get_welcome_msg(self, group_id: str) -> str:
        """获取原始欢迎语模版"""
        group_id = self._normalize_group_id(group_id)
        default = self.welcome_config.get(
            DEFAULT_GROUP_ID, MESSAGE_DEFAULTS["welcome_msg"]
        )
        return self.welcome_config.get(group_id, default)

    def get_decrease_msg(self, group_id: str) -> str:
        """获取原始退群语模版"""
        group_id = self._normalize_group_id(group_id)
        default = self.decrease_config.get(
            DEFAULT_GROUP_ID, MESSAGE_DEFAULTS["decrease_msg"]
        )
        return self.decrease_config.get(group_id, default)

    def get_increase_msg(self, group_id: str) -> str:
        group_id = self._normalize_group_id(group_id)
        default = self.increase_config.get(
            DEFAULT_GROUP_ID, MESSAGE_DEFAULTS["increase_msg"]
        )
        return self.increase_config.get(group_id, default)

    def get_reject_reason(
        self, event: AstrMessageEvent, matched_key: str, group_name: str = ""
    ) -> str:
        group_id = self._normalize_group_id(event.get_group_id())
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        reason_tmpl = self.reject_reason.get(
            group_id,
            self.reject_reason.get(DEFAULT_GROUP_ID, MESSAGE_DEFAULTS["reject_reason"]),
        )

        # 占位符
        return self._format_placeholder(
            reason_tmpl,
            group_id,
            user_id,
            user_name,
            group_name,
            extra={r"%key%": matched_key},
        )

    # ------------------ 事件处理 ------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_request(self, event: AstrMessageEvent):
        """监听加群事件并处理"""
        if not hasattr(event, "message_obj") or not hasattr(
            event.message_obj, "raw_message"
        ):
            return

        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return

        if (
            raw.get("post_type") != "request"
            or raw.get("request_type") != "group"
            or raw.get("sub_type") != "add"
        ):
            return

        delay = self.config.get("delay", 0.5)
        group_id = str(raw.get("group_id", ""))
        user_id = str(raw.get("user_id", ""))
        comment = raw.get("comment", "")
        flag = str(raw.get("flag", ""))
        logger.info(
            f"[JoinManager] 收到申请 | Group: {group_id} | User: {user_id} | Msg: {comment}"
        )

        if not self._check_permission(group_id):
            return
        if flag:
            if flag in self.seen_group_request_flags:
                logger.info(
                    f"[JoinManager] 跳过重复加群请求事件: Group={group_id}, User={user_id}"
                )
                return
            self.seen_group_request_flags.add(flag)
            if len(self.seen_group_request_flags) > 1000:
                self.seen_group_request_flags.clear()
                self.seen_group_request_flags.add(flag)

        group_name = await self._get_group_name(event, group_id)
        comment_lower = comment.lower()
        user_name = user_id
        stranger_info: dict[str, Any] = {}

        # Fetch profile once for nickname and optional level gate.
        if event.get_platform_name() == "aiocqhttp":
            stranger_info = await self._get_stranger_info(event, user_id)
            fetched_name = stranger_info.get("nickname") or stranger_info.get("nick")
            if fetched_name:
                user_name = str(fetched_name)
                logger.info(f"[JoinManager] 成功获取昵称: {user_name} ({user_id})")
            else:
                logger.debug(f"[JoinManager] 未获取到用户昵称: {user_id}")

        if self.level_limit_enabled:
            logger.debug(
                "[JoinManager] 等级限制已启用: "
                f"min_level={self.min_level}, reject_low_level={self.reject_low_level}"
            )
            raw_level = stranger_info.get("level", "")
            user_level = None
            if isinstance(raw_level, int):
                user_level = raw_level
            elif isinstance(raw_level, str) and raw_level.isdigit():
                user_level = int(raw_level)
            elif raw_level:
                logger.warning(
                    f"[JoinManager] 用户等级字段不可解析: user_id={user_id}, level={raw_level}"
                )

            if user_level is None or user_level < self.min_level:
                if user_level is None:
                    if stranger_info.get("profile_available"):
                        level_reason = f"接口未返回QQ等级，最低要求{self.min_level}级"
                    else:
                        level_reason = (
                            f"未获取到用户资料或QQ等级，最低要求{self.min_level}级"
                        )
                else:
                    level_reason = f"QQ等级{user_level}级低于最低要求{self.min_level}级"
                logger.info(
                    f"[JoinManager] 等级限制拦截用户: {user_id} | {level_reason}"
                )
                reject_message = self._format_placeholder(
                    self.level_limit_reject_reason,
                    group_id,
                    user_id,
                    user_name,
                    group_name,
                    extra={
                        r"%user_level%": str(user_level)
                        if user_level is not None
                        else "",
                        r"%min_level%": str(self.min_level),
                        r"%level_reason%": level_reason,
                    },
                )

                if self.reject_low_level and event.get_platform_name() == "aiocqhttp":
                    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                        AiocqhttpMessageEvent,
                    )

                    assert isinstance(event, AiocqhttpMessageEvent)
                    client = event.bot
                    try:
                        await client.call_action(
                            "set_group_add_request",
                            flag=flag,
                            approve=False,
                            reason=reject_message,
                        )
                        logger.info(
                            f"[JoinManager] 已按等级限制直接拒绝用户: {user_id}"
                        )
                        target_sids = self.get_notice_session(event, "reject_notice")
                        if target_sids is not None:
                            chain: list[Comp.BaseMessageComponent] = [
                                Comp.Plain(
                                    f"🚫 已自动拒绝用户 {user_id}\n"
                                    f"📝 原因: {reject_message}"
                                )
                            ]
                            for target_sid in target_sids:
                                try:
                                    await self.context.send_message(
                                        target_sid, MessageChain(chain)
                                    )  # type: ignore
                                except Exception as e:
                                    logger.error(f"发送消息到{target_sid}失败: {e}")
                                await asyncio.sleep(delay)
                    except Exception as e:
                        error_text = str(e)
                        if "already refuse msg by self" in error_text:
                            logger.info(
                                "[JoinManager] 等级限制拒绝请求已由本账号处理，"
                                f"跳过重复拒绝: {user_id}"
                            )
                            return
                        logger.warning(f"[JoinManager] 等级限制拒绝请求失败: {e}")
                else:
                    logger.info(f"[JoinManager] 等级限制已跳过处理用户请求: {user_id}")
                return
            logger.info(
                f"[JoinManager] 用户等级通过限制: user_id={user_id}, level={user_level}"
            )

        # ---------------- 关键词匹配 (自动拒绝) ----------------
        reject_keywords = self.get_reject_keywords(group_id)
        matched_reject_kw = None

        for kw in reject_keywords:
            if kw.lower() in comment_lower:
                matched_reject_kw = kw
                break

        if matched_reject_kw:
            logger.info(
                f"[JoinManager] 命中拒绝词: {matched_reject_kw} -> 拒绝用户: {user_id}"
            )
            # 拒绝理由
            reject_reason = self.get_reject_reason(event, matched_reject_kw, group_name)
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                    AiocqhttpMessageEvent,
                )

                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                try:
                    await client.call_action(
                        "set_group_add_request",
                        flag=flag,
                        approve=False,
                        reason=reject_reason,
                    )
                    target_sids = self.get_notice_session(event, "reject_notice")

                    if target_sids is not None:
                        # 逐群发送
                        chain: list[Comp.BaseMessageComponent] = [
                            Comp.Plain(
                                f"🚫 已自动拒绝用户 {user_id}\n"
                                + f"📝 原因: 触发拒绝词【{matched_reject_kw}】"
                            )
                        ]
                        for target_sid in target_sids:
                            try:
                                await self.context.send_message(
                                    target_sid, MessageChain(chain)
                                )  # type: ignore
                            except Exception as e:
                                logger.error(f"发送消息到{target_sid}失败: {e}")
                            await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"[JoinManager] 拒绝操作或发送通知失败: {e}")
            return

        # ---------------- 关键词匹配 (自动同意) ----------------
        matched_category = None
        matched_keyword = None

        accept_rules = self.get_accept_rules(group_id)
        for category_name, keywords in accept_rules.items():
            for kw in keywords:
                if kw.lower() in comment_lower:
                    matched_category = category_name
                    matched_keyword = kw
                    break
            if matched_category:
                break

        if matched_category:
            logger.info(f"[JoinManager] 匹配成功 -> 分类: {matched_category}")

            approved_success = False
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                    AiocqhttpMessageEvent,
                )

                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                try:
                    await client.call_action(
                        "set_group_add_request", flag=flag, approve=True
                    )
                    approved_success = True
                except Exception as e:
                    logger.error(f"API调用失败: {e}")
                    return
            else:
                return

            if approved_success:
                if group_id not in self.records:
                    self.records[group_id] = {}

                self.records[group_id][user_id] = {
                    "accept_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "accept_reason": f"匹配关键词: {matched_keyword}",
                    "category": matched_category,
                }
                self._save_records()

                chart_path = None
                disabled_statisics_group = self.config.get("divide_group", {}).get(
                    "disabled_statistics", []
                )
                disabled_list_str = [str(g) for g in disabled_statisics_group]

                if group_id not in disabled_list_str:
                    try:
                        chart_path = await self._generate_chart(group_id, group_name)
                    except Exception as e:
                        logger.error(f"生成图表失败: {e}")

                # 欢迎语处理 (支持占位符)
                welcome_tmpl = self.get_welcome_msg(group_id)
                welcome_msg = self._format_placeholder(
                    welcome_tmpl,
                    group_id,
                    user_id,
                    user_name,
                    group_name,
                    extra={r"%category%": matched_category, r"%comment%": comment},
                )

                sdmsg = (
                    f" 🎉 {welcome_msg}\n"
                    + f"📝 验证消息:\n{comment}\n"
                    + f"🏷️ 分类: {matched_category}\n"
                )

                if chart_path and chart_path.exists():
                    sdmsg += "\n📊 来源分布:"
                    chain: list[Comp.BaseMessageComponent] = [
                        Comp.At(qq=user_id),
                        Comp.Plain(sdmsg),
                        Comp.Image.fromFileSystem(str(chart_path)),
                    ]
                else:
                    chain: list[Comp.BaseMessageComponent] = [
                        Comp.At(qq=user_id),
                        Comp.Plain(sdmsg),
                    ]

                await asyncio.sleep(2)

                try:
                    target_sids = self.get_notice_session(event, "accept_notice")
                    if target_sids is not None:
                        # 逐群发送
                        for target_sid in target_sids:
                            wait_chain = chain.copy()
                            try:
                                if target_sid != event.unified_msg_origin:
                                    # 构造非UMO消息通知
                                    tartget_msg = (
                                        f"🎉 群{group_id} 已自动审核通过{user_id}的请求\n"
                                        + f"📝 验证消息:\n{comment}\n"
                                        + f"🏷️ 分类: {matched_category}\n"
                                    )
                                    if chart_path and chart_path.exists():
                                        wait_chain: list[Comp.BaseMessageComponent] = [
                                            Comp.Plain(tartget_msg),
                                            Comp.Image.fromFileSystem(str(chart_path)),
                                        ]
                                    else:
                                        wait_chain: list[Comp.BaseMessageComponent] = [
                                            Comp.Plain(tartget_msg)
                                        ]
                                await self.context.send_message(
                                    target_sid, MessageChain(wait_chain)
                                )  # type: ignore
                                logger.info(
                                    f"[JoinManager] 已完成加群请求，消息发送到{target_sid}成功"
                                )
                            except Exception as e:
                                logger.error(f"发送消息到{target_sid}失败: {e}")
                            await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"发送消息失败: {e}")
                finally:
                    await self._dispose_chart_path(chart_path)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_decrease(self, event: AstrMessageEvent):
        """监听退群事件，清理统计数据并发送消息"""
        if event.get_platform_name() != "aiocqhttp":
            return

        if not hasattr(event, "message_obj") or not hasattr(
            event.message_obj, "raw_message"
        ):
            return

        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return

        if (
            raw.get("post_type") == "notice"
            and raw.get("notice_type") == "group_decrease"
        ):
            group_id = str(raw.get("group_id", ""))
            user_id = str(raw.get("user_id", ""))

            # 权限检查
            if not self._check_permission(group_id):
                return
            group_name = await self._get_group_name(event, group_id)

            # 从数据中移除
            if group_id in self.records:
                if user_id in self.records[group_id]:
                    self.records[group_id].pop(user_id)
                    logger.info(
                        f"[JoinManager] 用户 {user_id} 退出群 {group_id}，已从统计记录中移除"
                    )
                    self._save_records()

            user_name = user_id
            fetched_name = await self._get_user_nickname(event, user_id)
            if fetched_name:
                user_name = fetched_name

            decrease_tmpl = self.get_decrease_msg(group_id)
            if not decrease_tmpl:
                return

            final_msg = self._format_placeholder(
                decrease_tmpl, group_id, user_id, user_name, group_name
            )
            target_sids = self.get_notice_session(event, "decrease_notice")

            if target_sids:
                delay = self.config.get("delay", 0.5)
                for target_sid in target_sids:
                    try:
                        await self.context.send_message(
                            target_sid, MessageChain([Comp.Plain(final_msg)])
                        )  # type: ignore
                        logger.info(f"[JoinManager] 已发送退群提示到 {target_sid}")
                    except Exception as e:
                        logger.error(
                            f"[JoinManager] 发送退群提示到 {target_sid} 失败: {e}"
                        )
                    await asyncio.sleep(delay)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_increase(self, event: AstrMessageEvent):
        """监听入群事件，对于手动同意进群者发送通知"""
        if event.get_platform_name() != "aiocqhttp":
            return

        if not hasattr(event, "message_obj") or not hasattr(
            event.message_obj, "raw_message"
        ):
            return

        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return

        if (
            raw.get("post_type") == "notice"
            and raw.get("notice_type") == "group_increase"
        ):
            group_id = str(raw.get("group_id", ""))
            user_id = str(raw.get("user_id", ""))

            await asyncio.sleep(2)
            # 权限检查
            if not self._check_permission(group_id):
                return
            group_name = await self._get_group_name(event, group_id)

            if group_id not in self.records:
                self.records[group_id] = {}

            # 检查是否是自动审核
            if user_id in self.records[group_id]:
                return

            # 加入统计数据（分类: 人工审核）
            self.records[group_id][user_id] = {
                "accept_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "accept_reason": "人工审核",
                "category": "人工审核",
            }
            self._save_records()

            inscrease_tmpl = self.get_increase_msg(group_id)
            if not inscrease_tmpl:
                return

            chart_path = None
            disabled_statisics_group = self.config.get("divide_group", {}).get(
                "disabled_statistics", []
            )
            disabled_list_str = [str(g) for g in disabled_statisics_group]

            if group_id not in disabled_list_str:
                try:
                    chart_path = await self._generate_chart(group_id, group_name)
                except Exception as e:
                    logger.error(f"生成图表失败: {e}")

            # 构造欢迎消息
            user_name = user_id
            fetched_name = await self._get_user_nickname(event, user_id)
            if fetched_name:
                user_name = fetched_name

            welcome_msg = self._format_placeholder(
                text=inscrease_tmpl,
                group_id=group_id,
                user_id=user_id,
                user_name=user_name,
                group_name=group_name,
            )
            sdmsg = f" 🎉 {welcome_msg}\n" + "🏷️ 分类: 人工审核"
            if chart_path and chart_path.exists():
                sdmsg += "\n\n📊 来源分布:"
                chain: list[Comp.BaseMessageComponent] = [
                    Comp.At(qq=user_id),
                    Comp.Plain(sdmsg),
                    Comp.Image.fromFileSystem(str(chart_path)),
                ]
            else:
                chain: list[Comp.BaseMessageComponent] = [
                    Comp.At(qq=user_id),
                    Comp.Plain(sdmsg),
                ]

            target_sids = self.get_notice_session(event, "increase_notice")
            delay = self.config.get("delay", 0.5)

            if target_sids is not None:
                try:
                    # 逐群发送
                    for target_sid in target_sids:
                        wait_chain = chain.copy()
                        try:
                            if target_sid != event.unified_msg_origin:
                                # 构造非UMO消息通知
                                tartget_msg = (
                                    f"🎉 群{group_id} 已由管理员审核通过{user_id}的请求\n"
                                    + "🏷️ 分类: 人工审核\n"
                                )
                                if chart_path and chart_path.exists():
                                    wait_chain: list[Comp.BaseMessageComponent] = [
                                        Comp.Plain(tartget_msg),
                                        Comp.Image.fromFileSystem(str(chart_path)),
                                    ]
                                else:
                                    wait_chain: list[Comp.BaseMessageComponent] = [
                                        Comp.Plain(tartget_msg)
                                    ]
                            await self.context.send_message(
                                target_sid, MessageChain(wait_chain)
                            )  # type: ignore
                            logger.info(
                                f"[JoinManager] 检测到手动同意入群，消息发送到{target_sid}成功"
                            )
                        except Exception as e:
                            logger.error(f"发送消息到{target_sid}失败: {e}")
                        await asyncio.sleep(delay)
                finally:
                    await self._dispose_chart_path(chart_path)
            else:
                await self._dispose_chart_path(chart_path)

    @filter.command("入群统计", alias={"加群统计"})
    async def on_statistics_command(self, event: AstrMessageEvent):
        """入群统计命令，生成统计图并发送"""
        group_id = event.get_group_id()

        # 权限检查
        if not self._check_permission(group_id):
            return

        # 非空检查
        if group_id not in self.records:
            yield event.plain_result("本群暂无统计数据！")
            return

        # 生成统计图
        chart_path = None
        try:
            group_name = await self._get_group_name(event, group_id)
            chart_path = await self._generate_chart(group_id, group_name)
        except Exception as e:
            logger.error(f"生成图表失败: {e}")

        try:
            if chart_path and chart_path.exists():
                yield event.image_result(str(chart_path))
            else:
                yield event.plain_result("生成图表出错，请重试！")
        finally:
            await self._dispose_chart_path(chart_path)

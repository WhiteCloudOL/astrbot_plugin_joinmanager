import json, asyncio
from datetime import datetime
from typing import Dict, List
from pathlib import Path
from astrbot.core.platform.message_type import MessageType
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from .draw import draw_chart

class JoinManager(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 1. 基础路径配置
        self.plugin_dir = Path(__file__).parent.absolute()
        self.assets_dir = self.plugin_dir / "assets"
        self.data_dir = Path(StarTools.get_data_dir("astrbot_plugin_joinmanager"))
        self.records_file = self.data_dir / "join_records.json"
        self.chart_temp_path = self.data_dir / "temp_chart.png"
        
        # 2. 目录检查
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.assets_dir.exists():
            logger.warning(f"[JoinManager] 未找到 assets 目录，自定义字体可能无法加载: {self.assets_dir}")
            
        # 3. 数据加载
        self.records = self._load_records()

        # 4. 配置加载
        self.welcome_config = self._load_welcome_msg_config()
        self.accept_rules = self._load_accept_rules()
        self.reject_rules = self._load_reject_rules()
        self.reject_reason = self._load_reject_reason()

    def _load_welcome_msg_config(self) -> dict:
        """解析设置的欢迎语"""
        try:
            welcome_config: list[str] = self.config.get('divide_group', {}).get('welcome_msg', ["default:欢迎新成员！通过自动审核"])
            welcome_dic = {}
            for item in welcome_config:
                group_msg = item.replace('：', ':').split(':', 1)
                if len(group_msg) == 2:
                    group_id, msg = group_msg
                    if group_id and msg:
                        welcome_dic[group_id.strip()] = msg.strip()
                else:
                    logger.warning(f"[加群统计管理器] 欢迎语配置格式错误: {item}")
            
            if 'default' not in welcome_dic:
                welcome_dic['default'] = "欢迎新成员！通过自动审核"
            return welcome_dic
        except Exception as e:
            logger.error(f"[加群统计管理器] 欢迎语解析错误：{e}")
            return {"default": "欢迎新成员！通过自动审核"}

    def _load_accept_rules(self) -> Dict[str, List[str]]:
        """解析同意规则"""
        raw_list = self.config.get('divide_group', {}).get('accept_categories', [])
        rules = {}
        for item in raw_list:
            try:
                item = item.replace('：', ':')
                if ':' in item:
                    category, keywords_str = item.split(':', 1)
                    keywords = [k.strip() for k in keywords_str.replace('，',',').split(',') if k.strip()]
                    if keywords:
                        rules[category.strip()] = keywords
                else:
                    logger.warning(f"[JoinManager] 同意规则格式错误 (缺少冒号): {item}")
            except Exception as e:
                logger.error(f"[JoinManager] 解析单条同意规则失败: {item}, 错误: {e}")
        return rules

    def _load_reject_rules(self) -> List[str]:
        """解析拒绝规则"""
        return self.config.get('divide_group', {}).get('reject', [])
    
    def _load_reject_reason(self) -> dict:
        reject_reason: list[str] = self.config.get("divide_group",{}).get("reject_reason",[])
        reasons = {}
        for item in reject_reason:
            if ':' in item:
                parts = item.replace('：',':').split(':', 1)
                key = parts[0]
                value = parts[1]
                reasons[key] = value
        return reasons

    def _load_records(self) -> Dict:
        """加载 JSON 统计记录"""
        if self.records_file.exists():
            try:
                with self.records_file.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载入群记录失败: {e}")
        return {}
    
    def get_notice_session(self, 
                         event: AstrMessageEvent, 
                         type: str # reject_notice / accept_notice
                         ) -> set[str]:
        """获取需要通知的会话ID"""
        umo = event.unified_msg_origin
        sessions = self.config.get("divide_group",{}).get(type,[])
        filtered_sessions = {item for item in sessions if item != "origin"}
        if "origin" in sessions:
            filtered_sessions.add(umo)
        return filtered_sessions

    def _save_records(self):
        """保存 JSON 统计记录"""
        try:
            with self.records_file.open('w', encoding='utf-8') as f:
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

    async def _generate_chart(self, group_id: str) -> bool:
        """异步绘图包装器"""
        if group_id not in self.records:
            return False
            
        group_data = self.records[group_id]
        font_name = self.config.get("font", "cute_font.ttf")
        
        bg_img = self.config.get("bg_img", "bg.png")
        return await asyncio.to_thread(
            draw_chart, 
            group_id, 
            group_data, 
            self.chart_temp_path, 
            self.assets_dir, 
            font_name,
            bg_img
        )
    
    def get_welcome_msg(self, group_id: str) -> str:
        default = self.welcome_config.get("default", "欢迎新成员！通过自动审核")
        return self.welcome_config.get(group_id, default)

    def get_reject_reason(self, event: AstrMessageEvent, matched_key: str) -> str:
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        reason = ""
        if group_id in self.reject_reason:
            reason = self.reject_reason[group_id]
        else:
            reason = self.reject_reason.get("default","触发关键词，自动拒绝")
        
        placeholder = {
            r"%group_id%": group_id,
            r"%user_id%": user_id,
            r"%user_name%": user_name,
            r"%key%": matched_key
        }
        for key in placeholder:
            reason = reason.replace(key,placeholder[key])
        return reason


    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_request(self, event: AstrMessageEvent):
        """监听加群事件并处理"""
        if not hasattr(event, "message_obj") or not hasattr(event.message_obj, "raw_message"):
            return
        
        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return

        if raw.get("post_type") != "request" or raw.get("request_type") != "group" or raw.get("sub_type") != "add":
            return

        delay = self.config.get("delay",0.5)
        group_id = str(raw.get("group_id", ""))
        user_id = str(raw.get("user_id", ""))
        comment = raw.get("comment", "")
        flag = raw.get("flag", "")
        
        logger.info(f"[JoinManager] 收到申请 | Group: {group_id} | User: {user_id} | Msg: {comment}")

        if not self._check_permission(group_id):
            return

        comment_lower = comment.lower()

        # ---------------- 关键词匹配 (自动拒绝) ----------------
        reject_keywords = self.reject_rules
        matched_reject_kw = None

        for kw in reject_keywords:
            if kw.lower() in comment_lower:
                matched_reject_kw = kw
                break
        
        if matched_reject_kw:
            logger.info(f"[JoinManager] 命中拒绝词: {matched_reject_kw} -> 拒绝用户: {user_id}")
            # 拒绝理由（自定义）
            reject_reason = self.get_reject_reason(event,matched_reject_kw)
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                try:
                    await client.call_action('set_group_add_request', flag=flag, approve=False, reason=reject_reason)
                    target_sids = self.get_notice_session(event,"reject_notice")
                    if target_sids is not None:
                        # 逐群发送（等待0.5s）
                        chain: List[Comp.BaseMessageComponent] = [
                                Comp.Plain(f"🚫 已自动拒绝用户 {user_id}\n"+
                                        f"📝 原因: 触发拒绝词【{matched_reject_kw}】")]
                        for target_sid in target_sids:
                            try:
                                await self.context.send_message(target_sid, MessageChain(chain))
                                logger.info(f"[JoinManager] 已拒绝加群请求，消息发送到{target_sid}成功")
                            except Exception as e:
                                logger.error(f"发送消息到{target_sid}失败: {e}")
                            await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"[JoinManager] 拒绝操作或发送通知失败: {e}")
            return

        # ---------------- 关键词匹配 (自动同意) ----------------
        matched_category = None
        matched_keyword = None
        
        for category_name, keywords in self.accept_rules.items():
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
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                try:
                    await client.call_action('set_group_add_request', flag=flag, approve=True)
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
                    "category": matched_category
                }
                self._save_records()
                
                has_chart = False
                disabled_statisics_group = self.config.get("divide_group", {}).get("disabled_statistics", [])
                disabled_list_str = [str(g) for g in disabled_statisics_group]
                
                if group_id not in disabled_list_str: 
                    try:
                        has_chart = await self._generate_chart(group_id)
                    except Exception as e:
                        logger.error(f"生成图表失败: {e}")

                welcome = self.get_welcome_msg(group_id)

                sdmsg = (f" 🎉 {welcome}\n"+
                         f"📝 验证消息:\n{comment}\n"+
                         f"🏷️ 分类: {matched_category}\n")
                
                if has_chart and self.chart_temp_path.exists():
                    sdmsg += "\n📊 来源分布:"
                    chain: List[Comp.BaseMessageComponent] = [
                        Comp.At(qq=user_id),
                        Comp.Plain(sdmsg),
                        Comp.Image.fromFileSystem(str(self.chart_temp_path))
                    ]
                else:
                    chain: List[Comp.BaseMessageComponent] = [
                        Comp.At(qq=user_id),
                        Comp.Plain(sdmsg)
                    ]

                await asyncio.sleep(2)
                
                try:
                    target_sids = self.get_notice_session(event,"accept_notice")
                    if target_sids is not None:
                        # 逐群发送
                        for target_sid in target_sids:
                            wait_chain = chain.copy()
                            try:
                                if target_sid != event.unified_msg_origin:
                                    # 构造非UMO消息通知
                                    tartget_msg = (f"🎉 群{group_id} 已自动审核通过{user_id}的请求\n"+
                                                   f"📝 验证消息:\n{comment}\n"+
                                                   f"🏷️ 分类: {matched_category}\n")
                                    if has_chart and self.chart_temp_path.exists():
                                        wait_chain: List[Comp.BaseMessageComponent] = [
                                            Comp.Plain(tartget_msg),
                                            Comp.Image.fromFileSystem(str(self.chart_temp_path))
                                        ]
                                    else:
                                        wait_chain: List[Comp.BaseMessageComponent] = [
                                            Comp.Plain(tartget_msg)
                                        ]
                                await self.context.send_message(target_sid, MessageChain(wait_chain))
                                logger.info(f"[JoinManager] 已完成加群请求，消息发送到{target_sid}成功")
                            except Exception as e:
                                logger.error(f"发送消息到{target_sid}失败: {e}")
                            await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"发送消息失败: {e}")
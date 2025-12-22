import json
import asyncio
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import font_manager
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from astrbot.core.platform.message_type import MessageType
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

# 设置 matplotlib 后端为 Agg 
matplotlib.use('Agg')

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
                    logger.warning(f"[JoinManager] 欢迎语配置格式错误: {item}")
            
            if 'default' not in welcome_dic:
                welcome_dic['default'] = "欢迎新成员！通过自动审核"
            return welcome_dic
        except Exception as e:
            logger.error(f"[JoinManager] 欢迎语解析错误：{e}")
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

    def _load_records(self) -> Dict:
        """加载 JSON 统计记录"""
        if self.records_file.exists():
            try:
                with self.records_file.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载入群记录失败: {e}")
        return {}

    def _save_records(self):
        """保存 JSON 统计记录"""
        try:
            with self.records_file.open('w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存入群记录失败: {e}")

    async def terminate(self):
        self._save_records()

    def _get_font_prop(self) -> font_manager.FontProperties:
        """获取字体属性"""
        font_name = self.config.get("font", "cute_font.ttf")
        font_path = self.assets_dir / font_name
        
        if font_path.exists():
            try:
                return font_manager.FontProperties(fname=str(font_path))
            except Exception as e:
                logger.error(f"[JoinManager] 自定义字体加载失败: {e}")
        
        default_fonts = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
        return font_manager.FontProperties(family=default_fonts)

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

    def _draw_chart_sync(self, group_id: str, save_path: Path) -> bool:
        """同步绘图函数 (在线程池运行)"""
        if group_id not in self.records:
            return False

        group_data = self.records[group_id]
        if not group_data:
            return False

        # 数据处理
        category_counts = {}
        for user_data in group_data.values():
            cat = user_data.get("category", "未知")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        sorted_data = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 分类名称\n(5人)
        labels = [f"{item[0]}\n({item[1]}人)" for item in sorted_data]
        
        sizes = [item[1] for item in sorted_data]
        
        font_prop = self._get_font_prop()

        colors = [
            '#FF9999', '#66B2FF', '#99FF99', '#FFCC99', 
            '#c2c2f0', '#ffb3e6', '#c4e17f', '#76D7C4',
            '#F7DC6F', '#E59866'
        ]

        try:
            fig = Figure(figsize=(8, 6), dpi=120)
            FigureCanvasAgg(fig) 
            ax = fig.add_subplot(111)
            
            explode = [0.02] * len(sizes)
            pie_result = ax.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%', 
                startangle=140,
                colors=colors[:len(sizes)],
                explode=explode,
                shadow=True,
                pctdistance=0.85,
                textprops={'fontsize': 14}
            )
            
            texts = pie_result[1]
            autotexts = pie_result[2] if len(pie_result) >= 3 else []
            
            for text in texts: 
                text.set_fontproperties(font_prop)
                text.set_fontsize(15)
                text.set_color('#333333')
                # 标签可能包含多行（因为加入了\n），确保居中对齐
                text.set_horizontalalignment('center')

            for autotext in autotexts: # type: ignore
                autotext.set_fontproperties(font_prop)
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(13)
            
            ax.axis('equal')
            
            ax.set_title(
                f'群 {group_id} 入群来源分布', 
                fontproperties=font_prop, 
                fontsize=20,
                pad=20,
                color='#333333'
            )
            
            fig.tight_layout()
            fig.savefig(str(save_path))
            fig.clf() 
            logger.info(f"生成{group_id}图表成功！")
            return True
            
        except Exception as e:
            logger.error(f"绘图失败: {e}")
            return False

    async def _generate_chart(self, group_id: str) -> bool:
        """异步包装器"""
        return await asyncio.to_thread(self._draw_chart_sync, group_id, self.chart_temp_path)

    def get_sid(self, event: AstrMessageEvent) -> str:
        return event.unified_msg_origin
    
    def get_welcome_msg(self, group_id: str) -> str:
        default = self.welcome_config.get("default", "欢迎新成员！通过自动审核")
        return self.welcome_config.get(group_id, default)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_request(self, event: AstrMessageEvent):
        if not hasattr(event, "message_obj") or not hasattr(event.message_obj, "raw_message"):
            return
        
        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return

        if raw.get("post_type") != "request" or raw.get("request_type") != "group" or raw.get("sub_type") != "add":
            return

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
            
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                try:
                    await client.call_action('set_group_add_request', flag=flag, approve=False, reason="自动拒绝: 命中黑名单关键词")
                    
                    target_sid = self.get_sid(event)
                    chain: List[Comp.BaseMessageComponent] = [
                        Comp.Plain(f"🚫 已自动拒绝用户 {user_id}\n"+
                                   f"📝 原因: 触发拒绝词【{matched_reject_kw}】")
                    ]
                    await self.context.send_message(target_sid, MessageChain(chain))
                    
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

                sdmsg = (f"""🎉 {welcome}\n"""+
                         f"📝 验证消息:\n  {comment}\n"+
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
                    target_sid = self.get_sid(event)
                    await self.context.send_message(target_sid, MessageChain(chain))
                except Exception as e:
                    logger.error(f"发送消息失败: {e}")
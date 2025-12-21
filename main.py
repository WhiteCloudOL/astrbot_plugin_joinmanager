import json
import toml
import asyncio
import matplotlib
import matplotlib.pyplot as plt
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

@register("joinmanager", "User", "智能入群管理与统计", "2.3.3")
class JoinManager(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 1. 路径配置 (全面迁移至 pathlib)
        self.plugin_dir = Path(__file__).parent.absolute()
        self.toml_config_file = self.plugin_dir / "config.toml" 
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
        self.keyword_config = self._load_or_create_toml()

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

    def _load_or_create_toml(self) -> Dict:
        """加载或创建 config.toml"""
        default_config = {
            "categories": [
                {
                    "name": "粉丝",
                    "keywords": ["直播", "老粉", "关注", "up"]
                },
                {
                    "name": "技术交流",
                    "keywords": ["代码", "Python", "编程", "学习"]
                },
                {
                    "name": "老友",
                    "keywords": ["同学", "同事", "亲戚"]
                }
            ],
            "reject": {
                "keywords": ["广告", "兼职", "代刷"]
            }
        }

        # 如果文件不存在，创建默认文件
        if not self.toml_config_file.exists():
            try:
                with self.toml_config_file.open('w', encoding='utf-8') as f:
                    toml.dump(default_config, f)
                logger.info(f"[JoinManager] 已生成默认配置文件: {self.toml_config_file}")
                return default_config
            except Exception as e:
                logger.error(f"[JoinManager] 创建 config.toml 失败: {e}")
                return default_config

        # 如果文件存在，读取
        try:
            with self.toml_config_file.open('r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            logger.error(f"[JoinManager] 读取 config.toml 失败: {e}")
            return default_config

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
        """检查会话权限 (使用 group_id)"""
        divide_group = self.config.get("divide_group", {})
        block_method = divide_group.get("block_method", "blacklist")
        control_list = divide_group.get("control_list", [])
        
        control_list_str = [str(i) for i in control_list]
        
        if block_method == "whitelist":
            return group_id in control_list_str
        else:
            return group_id not in control_list_str

    def _generate_chart(self, group_id: str) -> bool:
        """生成群成员分类统计饼图 (美化版)"""
        if group_id not in self.records:
            return False

        group_data = self.records[group_id]
        if not group_data:
            return False

        category_counts = {}
        for user_data in group_data.values():
            cat = user_data.get("category", "未知")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # 数据排序（从大到小）
        sorted_data = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_data]
        sizes = [item[1] for item in sorted_data]
        
        font_prop = self._get_font_prop()

        # 莫兰迪/马卡龙色系 (Pastel Colors)
        colors = [
            '#FF9999', '#66B2FF', '#99FF99', '#FFCC99', 
            '#c2c2f0', '#ffb3e6', '#c4e17f', '#76D7C4',
            '#F7DC6F', '#E59866'
        ]

        try:
            plt.figure(figsize=(8, 6), dpi=120)
            explode = [0.02] * len(sizes)

            pie_result = plt.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%', 
                startangle=140,
                colors=colors[:len(sizes)], # 使用自定义颜色
                explode=explode,           # 分离效果
                shadow=True,               # 开启阴影
                pctdistance=0.85,          # 百分比距离圆心的距离
                textprops={'fontsize': 14} # 基础字号
            )
            
            texts = pie_result[1]
            autotexts = pie_result[2] if len(pie_result) >= 3 else []
            
            for text in texts: 
                text.set_fontproperties(font_prop)
                text.set_fontsize(15)
                text.set_color('#333333')

            for autotext in autotexts: # type: ignore
                autotext.set_fontproperties(font_prop)
                autotext.set_color('white')
                
                autotext.set_fontweight('bold')  
                
                autotext.set_fontsize(13)
            
            plt.axis('equal')
            plt.title(
                f'群 {group_id} 入群来源分布', 
                fontproperties=font_prop, 
                fontsize=20,
                pad=20,
                color='#333333'
            )
            
            plt.tight_layout()
            
            plt.savefig(str(self.chart_temp_path))
            plt.close()
            return True
        except Exception as e:
            logger.error(f"绘图失败: {e}")
            plt.close()
            return False

    def get_sid(self, event: AstrMessageEvent) -> str:
        """从platform,messagetype,groupid反推sid"""
        platform = event.get_platform_id()
        gotten_message_type = event.get_message_type()
        message_type_dic = {
            MessageType.GROUP_MESSAGE: "GroupMessage",
            MessageType.FRIEND_MESSAGE: "FriendMessage",
            MessageType.OTHER_MESSAGE: "OtherMessage"
        }
        message_type = message_type_dic.get(gotten_message_type,"OtherMessage")
        group_id = event.get_group_id()
        res: str = f"{platform}:{message_type}:{group_id}"
        return res

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_request(self, event: AstrMessageEvent):
        """监听加群请求"""
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

        # 预处理：转小写
        comment_lower = comment.lower()

        # ---------------- 关键词匹配 (自动拒绝) ----------------
        reject_keywords = self.keyword_config.get("reject", {}).get("keywords", [])
        matched_reject_kw = None
        
        for kw in reject_keywords:
            # 均转为小写对比
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
                    # 调用 API 拒绝，approve=False
                    await client.call_action('set_group_add_request', flag=flag, approve=False, reason="自动拒绝: 命中黑名单关键词")
                    
                    # 发送群通知
                    target_sid = self.get_sid(event)
                    # 显式指定类型 List[Comp.BaseMessageComponent]
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
        
        keyword_categories = self.keyword_config.get("categories", [])
        
        for item in keyword_categories:
            if not isinstance(item, dict): continue
                
            category_name = item.get("name", "默认")
            keywords = item.get("keywords", [])
            
            for kw in keywords:
                # 均转为小写对比
                if kw.lower() in comment_lower:
                    matched_category = category_name
                    matched_keyword = kw
                    break
            if matched_category:
                break

        # 处理同意请求
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
                # 记录数据
                if group_id not in self.records:
                    self.records[group_id] = {}
                
                self.records[group_id][user_id] = {
                    "accept_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "accept_reason": f"匹配关键词: {matched_keyword}",
                    "category": matched_category
                }
                self._save_records()
                has_chart = False
                try:
                    has_chart = self._generate_chart(group_id)
                except Exception as e:
                    logger.error(f"生成图表失败: {e}")

                default_welcome = "欢迎新成员！通过自动审核"
                welcome = self.config.get("welcome","")
                if welcome == "":
                    welcome = default_welcome

                sdmsg = (f"""🎉 {welcome}\n"""+
                         f"📝 理由: {matched_keyword}\n"+
                         f"🏷️ 分类: {matched_category}\n")
                
                # 检查图表是否存在
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
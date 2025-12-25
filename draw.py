# draw.py
import matplotlib
# 设置后端为 Agg，防止在无 GUI 环境下报错
matplotlib.use('Agg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import font_manager
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as path_effects
import matplotlib.lines as lines
import matplotlib.image as mpimg
import numpy as np

from pathlib import Path
from typing import Dict, Any
from astrbot.api import logger

def get_mpl_font_prop(assets_dir: Path, font_name: str) -> font_manager.FontProperties:
    """获取 Matplotlib 用的字体属性"""
    font_path = assets_dir / font_name
    if font_path.exists():
        try:
            return font_manager.FontProperties(fname=str(font_path))
        except Exception as e:
            logger.warning(f"[JoinManager] 自定义字体加载失败: {e}")
    
    # 回退字体
    default_fonts = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
    return font_manager.FontProperties(family=default_fonts)

def draw_chart(group_id: str, group_data: Dict[str, Any], save_path: Path, assets_dir: Path, font_name: str = "cute_font.ttf", bg_img_name: str = "bg.png") -> bool:
    """
    绘制统计图表 (美化版：卡片风格 + 可爱元素 + 修复类型报错)
    由Gemini驱动~
    """
    if not group_data:
        return False

    # --- 1. 数据处理 ---
    category_counts = {}
    all_times = []
    for user_data in group_data.values():
        cat = user_data.get("category", "未知")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        t_str = user_data.get("accept_time", "")
        if t_str: all_times.append(t_str)

    sorted_data = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    
    time_range_str = "N/A"
    if all_times:
        all_times.sort()
        start_t = all_times[0][:-3] if len(all_times[0]) > 16 else all_times[0]
        end_t = all_times[-1][:-3] if len(all_times[-1]) > 16 else all_times[-1]
        time_range_str = f"{start_t} ~ {end_t}"

    total_people = sum(category_counts.values())

    # --- 2. 基础设置 ---
    # 马卡龙/糖果色系 (更鲜艳一点)
    cute_colors = [
        '#FFB7C5', # 樱花粉
        '#87CEEB', # 天空蓝
        '#FFD700', # 金色
        '#DDA0DD', # 梅红
        '#98FB98', # 淡绿
        '#FFA07A', # 浅鲑红
        '#B0C4DE', # 钢蓝
        '#FF69B4'  # 热粉
    ]
    
    font_prop = get_mpl_font_prop(assets_dir, font_name)
    
    # 定义固定画布大小 (类似手机海报比例 9:16)
    # figsize=(10, 16), dpi=120 -> 输出约 1200x1920 像素
    FIG_W, FIG_H = 10, 16
    fig = Figure(figsize=(FIG_W, FIG_H), dpi=120)
    FigureCanvasAgg(fig)

    # 文字特效
    stroke_white = path_effects.withStroke(linewidth=5, foreground='white', alpha=1.0)
    
    try:
        # --- 3. 绘制背景层 ---
        # 创建全屏 Axes 用于放背景图
        bg_ax = fig.add_axes((0, 0, 1, 1))
        bg_ax.axis('off')
        
        bg_path = assets_dir / bg_img_name
        has_bg_img = False
        if bg_path.exists():
            try:
                img = mpimg.imread(str(bg_path))
                # aspect='auto' 强制拉伸填满固定大小的画布
                bg_ax.imshow(img, aspect='auto', alpha=1.0, zorder=0)
                has_bg_img = True
            except Exception as e:
                logger.warning(f"背景加载失败: {e}")
        
        if not has_bg_img:
            # 纯色背景回退
            bg_ax.set_facecolor('#FFF0F5') # 薰衣草红

        # --- 4. 绘制半透明磨砂卡片 (核心美化) ---
        # 在画布中间画一个圆角矩形，作为主内容区
        # 坐标(0.05, 0.05) 宽度0.9 高度0.9
        card_ax = fig.add_axes((0.05, 0.05, 0.9, 0.9))
        card_ax.axis('off')
        
        # 绘制圆角矩形背景 (白色，半透明)
        round_box = FancyBboxPatch(
            (0, 0), 1, 1,
            boxstyle="round,pad=0,rounding_size=0.08",
            fc="white",
            ec="#FFB7C5",
            alpha=0.85,
            transform=card_ax.transAxes,
            linewidth=2,
            zorder=0
        )
        card_ax.add_patch(round_box)

        # --- 5. 装饰元素 (星星和点点) ---
        # 在卡片上随机撒一点装饰
        np.random.seed(sum(ord(c) for c in group_id))
        for _ in range(30):
            x = np.random.uniform(0.05, 0.95)
            y = np.random.uniform(0.05, 0.95)
            # 随机选择 星星(*) 或 圆点(o)
            marker = np.random.choice(['*', 'o', 'h']) 
            color = np.random.choice(cute_colors)
            size = np.random.uniform(100, 400)
            card_ax.scatter(x, y, s=size, c=color, marker=marker, alpha=0.3, zorder=1, edgecolors='none')

        # --- 6. 绘制饼图 (主图表) ---
        # 重新建立一个 Axes 用于画饼图，确保位置居中
        # 参数: [left, bottom, width, height]
        pie_ax = fig.add_axes((0.1, 0.25, 0.8, 0.45)) 
        pie_ax.axis('equal')
        
        labels = [f"{item[0]}\n({item[1]}人)" for item in sorted_data]
        sizes = [item[1] for item in sorted_data]
        explode = [0.04] * len(sizes)

        pie_result = pie_ax.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=cute_colors[:len(sizes)],
            explode=explode,
            shadow=False,
            radius=1.0,
            pctdistance=0.80,
            labeldistance=1.15,
            wedgeprops={'linewidth': 3, 'edgecolor': 'white', 'alpha': 0.9},
            textprops={'fontsize': 22}
        )
        
        wedges = pie_result[0]
        texts = pie_result[1]
        autotexts = pie_result[2] if len(pie_result) >= 3 else []

        # 绘制中心白圆 (甜甜圈的洞)
        centre_circle = mpatches.Circle((0,0), 0.60, fc='white', ec='#FFB7C5', lw=4, zorder=1, alpha=1.0)
        pie_ax.add_artist(centre_circle)

        # 设置字体和特效
        for i, text in enumerate(texts):
            text.set_fontproperties(font_prop)
            text.set_fontsize(24)
            text.set_color(cute_colors[i % len(cute_colors)]) # 标签颜色跟随饼块
            text.set_path_effects([stroke_white])

        for autotext in autotexts: # type: ignore
            autotext.set_fontproperties(font_prop)
            autotext.set_color('white')
            autotext.set_fontsize(18)
            autotext.set_path_effects([path_effects.withStroke(linewidth=3, foreground='#FFB7C5')])

        # --- 7. 文本信息绘制 ---
        
        # 7.1 中间圆心统计
        pie_ax.text(0, 0.25, '总计', ha='center', va='center',
                   fontproperties=font_prop, fontsize=22, color='#888888')
        pie_ax.text(0, -0.15, str(total_people), ha='center', va='center',
                   fontproperties=font_prop, fontsize=58, color='#FF69B4',
                   path_effects=[stroke_white])

        # 7.2 顶部标题区域 (使用 card_ax 坐标系)
        # 标题
        card_ax.text(0.5, 0.92, f'群 {group_id}', ha='center', va='center',
                     fontproperties=font_prop, fontsize=28, color='#87CEEB',
                     path_effects=[stroke_white])
        
        card_ax.text(0.5, 0.86, '✨ 成员来源大统计 ✨', ha='center', va='center',
                     fontproperties=font_prop, fontsize=42, color='#FF69B4',
                     path_effects=[stroke_white])

        # 时间胶囊 (圆角框)
        card_ax.text(0.5, 0.78, f"📅 统计时间: {time_range_str}", ha='center', va='center',
                     fontproperties=font_prop, fontsize=20, color='#9370DB',
                     bbox=dict(boxstyle='round,pad=0.8,rounding_size=0.5', fc='#F0F8FF', ec='#87CEEB', lw=2))

        # 底部版权区域
        line = lines.Line2D([0.15, 0.85], [0.12, 0.12], color='#FFB6C1', lw=2, linestyle='--', transform=card_ax.transAxes)
        card_ax.add_line(line)

        card_ax.text(0.5, 0.08, "AstrBot Plugin - JoinManager", ha='center', 
                     fontproperties=font_prop, fontsize=18, color='#AAAAAA')
        card_ax.text(0.5, 0.05, "Powered by 清蒸云鸭", ha='center', 
                     fontproperties=font_prop, fontsize=14, color='#CCCCCC')

        # --- 保存 ---
        fig.savefig(str(save_path)) 
        fig.clf()
        logger.info(f"生成{group_id}美化版图表成功！")
        return True

    except Exception as e:
        logger.error(f"绘图失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
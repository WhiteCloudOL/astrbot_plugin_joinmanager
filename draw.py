# draw.py
import matplotlib
# 设置后端为 Agg，防止在无 GUI 环境下报错
matplotlib.use('Agg')

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import font_manager
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import matplotlib.lines as lines
import matplotlib.image as mpimg
import numpy as np

from pathlib import Path
from typing import Dict, Any, Tuple
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
    绘制统计图表 (纯 Matplotlib 放大版 - 支持背景图与透明特效)
    """
    if not group_data:
        return False

    # --- 数据统计 ---
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

    # --- 绘图设置 ---
    labels = [f"{item[0]}\n({item[1]}人)" for item in sorted_data]
    sizes = [item[1] for item in sorted_data]
    font_prop = get_mpl_font_prop(assets_dir, font_name)

    # 可爱马卡龙色系
    cute_colors = [
        '#FFB7C5', '#AEC6CF', '#FDFD96', '#C3B1E1', 
        '#FFDAC1', '#77DD77', '#FF6961', '#B39EB5'
    ]

    # 文字特效 (描边)
    stroke_white = path_effects.withStroke(linewidth=4, foreground='white', alpha=0.9) 
    stroke_pink = path_effects.withStroke(linewidth=3, foreground='#FF69B4')
    stroke_yellow = path_effects.withStroke(linewidth=4, foreground='#FFD700')

    try:
        default_bg_color = '#FFF5EE'
        
        fig = Figure(figsize=(8, 9.5), dpi=150, facecolor=default_bg_color)
        FigureCanvasAgg(fig) 
        
        fig.subplots_adjust(top=0.88, bottom=0.12, left=0.02, right=0.98)
        
        # --- 背景处理 ---
        has_bg_img = False
        bg_path = assets_dir / bg_img_name
        
        if bg_path.exists():
            try:
                img = mpimg.imread(str(bg_path))
                rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
                bg_ax = fig.add_axes(rect) 
                bg_ax.axis('off')
                
                # 背景图透明度
                bg_ax.imshow(img, aspect='auto', alpha=0.4, zorder=0) 
                has_bg_img = True
            except Exception as e:
                logger.warning(f"[JoinManager] 背景图加载失败: {e}")

        # 主绘图区域
        ax = fig.add_subplot(111)
        ax.set_facecolor('none') 
        ax.axis('off')

        if not has_bg_img:
            np.random.seed(sum(ord(c) for c in group_id))
            for _ in range(45):
                x = np.random.uniform(-1.8, 1.8)
                y = np.random.uniform(-1.8, 1.8)
                dot_color = np.random.choice(['#FFD1DC', '#E0FFFF', '#FAFAD2', '#E6E6FA'])
                size = np.random.uniform(200, 600)
                ax.scatter(x, y, s=size, c=dot_color, alpha=0.4, zorder=0, edgecolors='none')
        
        explode = [0.03] * len(sizes)
        
        # --- 绘制甜甜圈 ---
        pie_result = ax.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%', 
            startangle=90,
            colors=cute_colors[:len(sizes)],
            explode=explode,
            shadow=True,
            radius=0.9,          
            pctdistance=0.85,    
            labeldistance=1.12,  
            # 饼图半透明 alpha
            wedgeprops={'linewidth': 3, 'edgecolor': '#FFF0F5', 'alpha': 0.7},
            textprops={'fontsize': 19} 
        )
        
        # --- 甜甜圈核心 (调整透明度alpha) ---
        centre_circle = mpatches.Circle((0,0), 0.6, fc='#FFFFF0', ec='#FFB7C5', lw=3, zorder=1, alpha=0.7)
        fig.gca().add_artist(centre_circle)
        
        # --- 文本美化 ---
        texts = pie_result[1]
        autotexts = pie_result[2] if len(pie_result) >= 3 else []
        
        for i, text in enumerate(texts): 
            text.set_fontproperties(font_prop)
            text.set_fontsize(20) 
            color_idx = i % len(cute_colors)
            text.set_color(cute_colors[color_idx]) 
            text.set_path_effects([stroke_white])

        for autotext in autotexts: # type: ignore
            autotext.set_fontproperties(font_prop)
            autotext.set_color('white')
            autotext.set_fontsize(16) 
            autotext.set_path_effects([stroke_pink])

        ax.axis('equal')
        ax.set_zorder(2)
        
        # --- 顶部标题 ---
        fig.text(
            0.5, 0.95, 
            f'群 {group_id} 来源大统计', 
            ha='center', va='top',
            fontproperties=font_prop, 
            fontsize=36,           
            color='#FF69B4',
            path_effects=[stroke_white]
        )
        
        # --- 时间胶囊 ---
        fig.text(
            0.5, 0.85, 
            f"统计时间：{time_range_str}", 
            ha='center', va='top',
            fontproperties=font_prop, 
            fontsize=18,           
            color='#9370DB',
            bbox=dict(boxstyle='round,pad=0.6,rounding_size=0.8', facecolor='#E6E6FA', edgecolor='#FFB7C5', linewidth=2, alpha=0.8)
        )
        
        # --- 中间人数统计 ---
        ax.text(
            0, 0.20, '总计人数', 
            ha='center', va='center',
            fontproperties=font_prop,
            fontsize=24,           
            color='#FF69B4',
            zorder=3,
            path_effects=[stroke_white]
        )
        
        ax.text(
            0, -0.10, str(total_people), 
            ha='center', va='center',
            fontproperties=font_prop,
            fontsize=65,           
            color='#FF8C00',
            zorder=3,
            path_effects=[stroke_yellow]
        )

        # --- 底部装饰线与文本 ---
        sep_line = lines.Line2D(
            [0.10, 0.90], [0.11, 0.11], 
            transform=fig.transFigure, 
            figure=fig, 
            color='#E0E0E0',
            linewidth=2,
            alpha=0.6,
            linestyle='-'
        )
        fig.lines.extend([sep_line])

        fig.text(0.5, 0.075, "AstrBot Plugin - joinmanager v1.2.1", ha='center', 
                 fontproperties=font_prop, fontsize=16, color='#888888',
                 path_effects=[stroke_white])
        
        fig.text(0.5, 0.04, "GitHub: WhiteCloudOL/astrbot_plugin_joinmanager", ha='center', 
                 fontproperties=font_prop, fontsize=12, color='#AAAAAA',
                 path_effects=[stroke_white])

        fig.savefig(str(save_path), bbox_inches='tight', pad_inches=0.1)
        fig.clf() 
        logger.info(f"生成{group_id}最终放大版图表成功！")
        return True
        
    except Exception as e:
        logger.error(f"绘图失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
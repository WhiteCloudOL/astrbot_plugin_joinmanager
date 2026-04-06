<div align="center">

![count](https://count.getloli.com/@:astrbot_plugin_joinmanager?name=astrbot_plugin_joinmanager&theme=asoul&padding=7&offset=0&align=center&scale=1&pixelated=1&darkmode=auto)

# Astrbot Plugin joinmanager
💫加群请求管理器v1.5.3💫  

<font color=RED size=4><b>警告：v1.5.0后配置文件结构重置，请备份好所有配置再更新！！！</b></font>

> 💌 **欢迎提交 Issue / PR！**  
> 如果你在使用中遇到问题、想到新功能、或希望优化文档与代码，欢迎在仓库发起 **Issue** 或 **Pull Request**，一起把插件做得更好。

</div>

> 插件灵感来源：https://github.com/qiqi55488/astrbot_plugin_appreview  
> 在此基础上作改进  

# 它能干什么？  
自动审核加群请求，同意申请后根据设定的分类生成精美统计图  
![C8AE6191F09D6E53BDAA319E9D97ED1F.png](https://free.picui.cn/free/2025/12/26/694e165a7651c.png)  

## 🌍安装  
### 自动安装  
Astrbot插件市场搜索 joinmanager 即可自动下载  

### 手动安装
1. 方式一：直接下载：  
点击右上角`<>Code`->`Download Zip`下载压缩包  
打开`Astrbot/data/plugins/`下载本仓库文件，创建 `astrbot_plugins_joinmanager` 目录，解压所有文件到此目录即可  
2. 方式二：Git Clone方法  
请确保系统已经安装git  
打开目录`Astrbot/data/plugins/`，在此目录下启动终端执行:  
```bash
git clone https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager.git  
```

3. 完成后重启Astrbot即可载入插件  

## 🎀 基本命令
| 命令 | 功能 |
| :---: | :---: |
| `/入群统计` | `获取本群的入群统计` |

## ✨ 配置与用法  
1. 安装插件  
2. 在`插件配置` 中配置 `黑/白名单`、`黑/白名单列表`、`自定义欢迎语`等  

### 基本配置项
| 配置项 | 格式 | 类型 | 备注 |
| :---: | :---: | :--: | :---: |
| `绘图字体` | `xxx.ttf`| str | 需要放在插件目录的`assets`文件夹下 |
| `背景图` | `bg.jpg` | str | 需要放在插件目录的`assets`文件夹下 |
| `发送延迟` | `延迟(s)` | float | 填入浮点数 |
| `同意关键词(分类)` | `群号:关键词1,关键词2,关键词3...` | list | 必须添加冒号，中英文`:`/`：`都可以使用 |
| `拒绝关键词` | `关键词` | str | 无 |
| `阻止模式` | `blacklist`/`whitelist` | option | 分别为黑名单，白名单 |
| `黑/白名单列表` | `群号` |str | (例如`12345678`) |
| `统计图表禁用群聊` | `群号` | str | 在哪些群聊禁用统计图表 |
| `notice会话通知项` | `sid` | list | 发送到消息源填入`origin`项，其他群或私聊填sid（可通过AstrBot命令 /sid 获取） |
| `msg消息项` | `群号:消息` | list | 必须添加冒号，中英文`:`/`：`都可以使用，默认为`default:xxx`，均支持占位符 |


> [!NOTE]  
> `同意关键词(分类)`: 按照**分类**同意加群申请，并统计加群来源，不区分大小写  
> `拒绝关键词`: 按照关键词自动**拒绝**申请  
> 如果两者重复，拒绝的优先级会**大于**同意  

### 占位符列表
| 占位符 | 代表什么？ | 适用于 |
|--------|--------| -------- |
| `%group_id%` | 群号 | all |
| `%user_id%` | 用户ID（QQ号） | all |
| `%user_name%` | 用户名（QQ昵称） | all |
| `%key%` | 检测到的关键词 | 拒绝理由 |
| `%category%` | 检测到的分类 | 欢迎语 |
| `%comment%` | 用户加群的验证消息 | 欢迎语 |

## 🎈 数据存储
1. 网页配置：`_conf_schema.json`  
2. 统计数据：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/join_records.json`  
3. 统计图表：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/temp_chart.png`  


## 👀 TODO  
> 画个饼  

✅ 分群设置欢迎语  
✅ 退群自动删除无关用户  
❌ 分群单独设置关键词   
  

## 🩷 问题反馈
| 方式 | 联系 |
| :--: | :--: |
| Github Issue | [跳转](https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager/issues) | 
|QQ群 [637174573](https://qm.qq.com/q/3f2bdkDsyW) | ![](https://docs.meowyun.cn/assets/yungroup.Jsn95Q4J.webp) |


## ♾️支持
[Astrbot帮助文档](https://astrbot.app)
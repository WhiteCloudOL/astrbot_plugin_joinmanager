<div align="center">

![count](https://count.getloli.com/@:astrbot_plugin_joinmanager?name=astrbot_plugin_joinmanager&theme=asoul&padding=7&offset=0&align=center&scale=1&pixelated=1&darkmode=auto)

# Astrbot Plugin joinmanager
💫加群请求管理器v1.6.2💫

<font color=RED size=4><b>警告：v1.6.0 为破坏性配置更新，旧版 `分类:关键词`、`关键词列表`、`群号:消息` 配置不会自动迁移，请更新后在插件配置页重新配置规则和消息模板。</b></font>

> v1.6.2 已兼容 Matplotlib 3.11 的 `PieContainer` 返回结构，避免生成入群统计图时因返回值类型变化而失败。

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
2. 在`插件配置` 中配置 `同意关键词规则`、`拒绝关键词规则`、`黑/白名单`、`通知项`、`消息模板`等

> [!WARNING]
> v1.6.0 起配置结构已重置为 AstrBot 原生 `template_list` 表单。旧配置字段 `accept_categories`、`reject_key`、`msg` 会被 AstrBot 配置系统移除，不再自动迁移；升级前请备份旧配置，升级后按下面的新结构重新填写。

### 基本配置项
| 配置项 | 类型 | 备注 |
| :---: | :---: | :--- |
| `绘图字体` | str | 需要放在插件目录的 `assets` 文件夹下，例如 `cute_font.ttf` |
| `背景图` | str | 需要放在插件目录的 `assets` 文件夹下，例如 `bg.jpg` |
| `发送延迟` | float | 多个通知目标之间的发送间隔，单位秒 |
| `图表兜底清理时间` | int | 统计图发送结束后立即删除；如果发送中断或删除失败，残留图片会在下一次生成图表时按此时间兜底清理，单位秒 |
| `等级限制` | object | 开启后低于最低 QQ 等级或未获取到等级的加群请求不会进入关键词审核；可选择直接拒绝，并自定义拒绝消息 |
| `同意关键词规则` | template_list | 每条规则包含 `启用`、`适用群号列表`、`来源分类`、`同意关键词` |
| `拒绝关键词规则` | template_list | 每条规则包含 `启用`、`适用群号列表`、`拒绝关键词`，拒绝优先级高于同意 |
| `阻止模式` | option | `blacklist` 为黑名单，`whitelist` 为白名单 |
| `黑/白名单列表` | list | 填群号，例如 `12345678` |
| `统计图表禁用群聊` | list | 填群号，这些群不会生成入群来源统计图 |
| `notice会话通知项` | list | 填 SID；`origin` 表示消息源群聊，可通过 `/sid` 获取其他群或私聊 SID |
| `消息模板` | template_list | 分别配置自动同意欢迎语、自动拒绝理由、退群提示、手动同意欢迎语，每条模板包含 `适用群号列表` 和 `消息内容` |


> [!NOTE]
> `同意关键词规则`: 按照**来源分类**同意加群申请，并统计加群来源，不区分大小写。
> `拒绝关键词规则`: 按照关键词自动**拒绝**申请，不区分大小写。
> 如果同意和拒绝同时命中，拒绝优先级更高。

### 分群关键词配置

`适用群号列表` 用于决定规则作用范围。一条规则可以填写多个群号，适合多个群共用同一组关键词：

| 适用群号 | 含义 |
| :---: | :--- |
| `default` | 默认规则。没有专属规则的群会使用它 |
| 具体群号 | 仅该群使用，例如 `637174573` |

如果某个群配置了自己的同意规则，该群只使用自己的同意规则，不再继承 `default` 同意规则。拒绝规则同理。

示例：

| 配置区域 | 适用群号列表 | 分类/用途 | 关键词 |
| :---: | :---: | :---: | :--- |
| 同意关键词规则 | `default` | GitHub | `github`, `gh` |
| 同意关键词规则 | `637174573`, `12345678` | 文档 | `文档`, `插件`, `AstrBot` |
| 拒绝关键词规则 | `default` | 自动拒绝 | `广告`, `代练` |
| 拒绝关键词规则 | `637174573`, `12345678` | 自动拒绝 | `引流`, `互粉` |

上面的配置中，`637174573` 群只会使用自己的同意关键词 `文档/插件/AstrBot`，不会再因为 `github/gh` 自动通过。

如果希望某些群禁用自动同意或自动拒绝，可以给这些群添加一条规则并关闭 `启用`，这些群就不会回退到 `default`。

### 消息模板配置

消息模板同样使用 `适用群号列表`，一条模板可以填写多个群号，适合多个群共用同一套提示语：

| 适用群号 | 含义 |
| :---: | :--- |
| `default` | 默认模板 |
| 具体群号 | 这些群使用的模板，例如 `637174573`、`12345678` |

旧版 `default:欢迎新成员`、`12345678:欢迎新人加入` 这种写法已废弃。请在消息模板列表中新增条目，并分别填写 `适用群号列表` 和 `消息内容`。

### 占位符列表
| 占位符 | 代表什么？ | 适用于 |
|--------|--------| -------- |
| `%group_id%` | 群号 | all |
| `%group_name%` | 群名称，获取不到时使用群号 | all |
| `%user_id%` | 用户ID（QQ号） | all |
| `%user_name%` | 用户名（QQ昵称） | all |
| `%key%` | 检测到的关键词 | 拒绝理由 |
| `%category%` | 检测到的分类 | 欢迎语 |
| `%comment%` | 用户加群的验证消息 | 欢迎语 |
| `%user_level%` | 用户 QQ 等级，未获取到时为空 | 等级限制拒绝消息 |
| `%min_level%` | 配置的最低 QQ 等级 | 等级限制拒绝消息 |
| `%level_reason%` | 等级限制命中的具体原因 | 等级限制拒绝消息 |

`%group_name%` 通过 `get_group_info` 获取；如果接口不可用或未返回群名称，会自动回退为群号。入群统计图标题同样优先显示群名称。

## 🎈 数据存储
1. 网页配置：`_conf_schema.json`
2. 统计数据：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/join_records.json`
3. 统计图表临时文件：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/chart_cache/`，每次生成独立图片，发送结束后删除；异常残留文件会在下一次生成图表时兜底清理


## 👀 TODO  
> 画个饼  

✅ 分群设置欢迎语  
✅ 退群自动删除无关用户  
✅ 分群单独设置关键词
  

## 🩷 问题反馈
| 方式 | 联系 |
| :--: | :--: |
| Github Issue | [跳转](https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager/issues) | 
|QQ群 [637174573](https://qm.qq.com/q/3f2bdkDsyW) | ![](https://docs.meowyun.cn/assets/yungroup.Jsn95Q4J.webp) |


## ♾️支持
[Astrbot帮助文档](https://astrbot.app)

# Astrbot Plugin joinmanager
## Author: 清蒸云鸭   

> 插件灵感来源：https://github.com/qiqi55488/astrbot_plugin_appreview  
> 在此基础上作改进  

## 安装  
### 自动安装
Astrbot插件市场搜索 joinmanager 即可自动下载  

### 手动安装
1. 方式一：直接下载：  
点击右上角`<>Code`->`Download Zip`下载压缩包  
打开`Astrbot/data/plugins/`下载本仓库文件，创建  `astrbot_plugins_joinmanager`目录，解压所有文件到此目录即可  
2. 方式二：Git Clone方法  
请确保系统已经安装git  
打开目录`Astrbot/data/plugins/`，在此目录下启动终端执行:  
```bash
# 全球/海外/港澳台
git clone https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager.git  

# 大陆地区#1
git clone https://gh-proxy.com/https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager.git

# 大陆地区#2
git clone https://cdn.gh-proxy.com/https://github.com/WhiteCloudOL/astrbot_plugin_joinmanager.git
```
以上命令任选其一执行即可  

3. 完成后重启Astrbot即可载入插件  

## 用法  
1. 安装插件  
2. 在`插件配置` 中配置 `欢迎语`、`黑/白名单`、`名单列表`   
3. 找到插件目录：`AstrBot/data/plugins/astrbot_plugin_joinmanager`  
4. 在插件目录下的"config.toml"里配置`categories`,`reject`  
> [!NOTE]  
> `categories`: 按照**分类**同意加群申请，并统计加群来源，不区分大小写  
> `reject`: 按照关键词自动**拒绝**申请  
> 如果两者重复，拒绝的优先级会**大于**同意  

如何添加分类：  
```toml
# 新增分类示例，字段需为categories
[[categories]]
name = "B站"
keywords = [ "B站", "b", "up" ]
```


## 数据存储
1. 网页配置：`_conf_schema.json`
2. 插件配置：`AstrBot/data/plugins/astrbot_plugin_joinmanager/config.toml`
3. 统计数据：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/join_records.json`
4. 统计图表：`AstrBot/data/plugin_data/astrbot_plugin_joinmanager/temp_chart.png`

> [!WARNING]  
> 本插件配置编辑较为复杂，未来可能会对配置作革新  

## TODO  
> 画个饼  

☐ 分群单独设置关键词  
☐ 分群设置欢迎语  

## 问题反馈
GithubIssue / QQ群 637174573  

## 支持
[Astrbot帮助文档](https://astrbot.app)
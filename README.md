# StellaSora Read-only Exporter

这是一个面向《星塔旅人》国服 Windows 客户端的本地只读数据工具。目前支持：

- 招募历史缓存（`PlayerGachaData._mapGachaHistory`）

工具通过 Windows `ReadProcessMemory` 读取当前登录账号已经加载到 Lua 运行时的数据，不注入 DLL、不修改游戏、不发送游戏协议请求。每次启动都会动态发现 Lua 表，不依赖固定内存地址。

## 使用

先登录游戏并进入主界面，然后运行桌面程序：

```powershell
cd E:\xtlr
.\run.ps1
```

程序启动时会先展示最近一次本地结果。点击“刷新游戏数据”后，读取工作在后台进行，完成后自动更新四类招募和五星页面并生成 JSON/CSV。

五星页面顶部的“更新角色资源”会从 GitHub 公开资源清单检查并下载缺失的角色/秘纹头像。资源保存在 `exports/assets/`，下载文件会进行 SHA-256 校验；更新失败不会影响已有抽卡归档。

每次刷新还会更新 `exports/stellasora_gacha_archive.json`。该文件按分类、卡池 ID、时间和结果去重合并历史，不会因为官方只提供最近半年记录而覆盖旧数据；请定期备份这个文件。

“五星一览”会按卡池归类五星角色，使用官方头像显示每次五星之间的抽数。统计仅基于游戏当前加载的历史范围；若卡池早期记录已不在缓存中，首个五星的间隔只代表现有记录范围。

## 加载四类卡池

游戏不会在一次登录中自动把四类招募历史全部放入内存。若首页显示“已加载分类 1/4”，请在游戏内依次打开：

1. 旅人限时招募
2. 秘纹限时招募
3. 旅人常驻招募
4. 秘纹常驻招募

每个记录页面等待列表出现后，再回到本工具点击“刷新游戏数据”。工具会保留 Lua 缓存中的分类，并在首页分别展示；不会主动向游戏发送请求。

命令行导出仍然保留：

```powershell
.\run_cli.ps1
```

也可以指定输出目录：

```powershell
.\run.ps1 --output E:\xtlr\exports
```

默认生成四个文件：

- `stellasora_gacha_<时间>.json`
- `stellasora_gacha_<时间>.csv`

JSON/CSV 不包含进程地址、账号 ID、Cookie、SDK token 或网络会话数据。游戏更新如果改变 Lua 对象布局或字段名，定位可能需要同步更新。

## 测试

```powershell
python -m unittest discover -s tests -v
```

# PythonAnywhere 部署指南（公司多平台经营数据管理系统）

本系统使用 Flask + SQLite，数据文件保存在项目目录 `data/company.db`。
PythonAnywhere 的磁盘是**持久**的，因此 SQLite 数据库会一直保留，
无需外部数据库，也无需持久盘挂载。免费版即可长期使用（每月 2000 请求额度）。

## 一、准备代码
方式 A（推荐，最简单）：
1. 注册 PythonAnywhere 免费账号：https://www.pythonanywhere.com/
2. 登录后进入 **Dashboard → Consoles**，开一个 **Bash** 控制台
3. 在控制台里执行：
   ```bash
   git clone https://github.com/stellagreenewfd-art/company-data-dashboard.git
   ```
   代码会下载到 `/home/<你的用户名>/company-data-dashboard`

方式 B（手动上传）：把仓库文件打包上传到同名目录。

## 二、配置虚拟环境（可选但推荐）
在 Bash 控制台：
```bash
cd ~/company-data-dashboard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
（免费版自带 Flask 等多数包，若启动报缺包再用上面的 venv 安装。）

## 三、设置环境变量（安全相关）
进入 **Dashboard → Web** 标签，在页面最下方 **Environment variables** 里添加：
- `SECRET_KEY` = 一串随机字符串（用于会话加密，建议填新的随机值）
- `SECURE_COOKIES` = `1`

> 不设置也能跑（wsgi.py 里有默认值），但生产环境务必设自己的 SECRET_KEY。

## 四、配置 Web App（关键）
1. **Dashboard → Web → Add a new web app**
2. 选 **Manual configuration**（手动配置），Python 版本选 3.10 或 3.11
3. 在 **Code** 区域：
   - Source code：填 `/home/<你的用户名>/company-data-dashboard`
   - WSGI configuration file：点进去，**把里面内容全部替换为下面这段**，保存：
   ```python
   import sys, os
   path = '/home/<你的用户名>/company-data-dashboard'
   if path not in sys.path:
       sys.path.insert(0, path)
   from app import app as application
   ```
   （把 `<你的用户名>` 换成你真实的 PA 用户名）
4. 如果是用 venv 安装的依赖，在 Web 标签的 **Virtualenv** 那一栏
   填 `/home/<你的用户名>/company-data-dashboard/venv`
5. 页面顶部点 **Reload** 重新加载

## 五、打开使用
Reload 后，访问给你的域名，形如：
**https://<你的用户名>.pythonanywhere.com**

- 默认管理员：**yjdata2026 / yj2026**（首次登录后务必改密码）
- 在「用户管理」里添加同事账号（角色 user / admin）

## 六、上传历史数据
登录后使用「批量上传」把原来的 10 个源文件一次性传上去，
云端数据库即拥有历史数据。之后每天各同事在自己电脑打开链接上传当日数据。

## 七、免费版注意事项
- 每月 2000 次 HTTP 请求额度（看板刷新、上传都算请求），小团队够用；
  若不够可在 **Web → Hacker/paid plans** 升级。
- 数据库 `data/company.db` 一直保存在磁盘上，不会因休眠/重启丢失。
- 上传的文件会通过系统写入 `data/company.db`，不要手删该文件。

## 八、安全提醒
- 部署完成后，到 GitHub 撤销本仓库推送用的 PAT 令牌（Settings → Developer settings → PAT → Revoke）。
- 改掉默认管理员密码，并为同事创建独立账号。

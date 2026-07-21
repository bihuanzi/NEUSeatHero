import requests
from pathlib import Path
import re
import json
import traceback
from datetime import datetime
import time

HERE = Path(__file__).parent
ERROR_LOG = HERE / "log" / "error"

def log_error(msg, exc=None):
    """记录错误到日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with ERROR_LOG.open('a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")
        if exc:
            f.write(traceback.format_exc())
            f.write("\n")

# ========== Selenium 自动登录（可选） ==========
def _get_selenium_driver():
    """尝试启动 Selenium 浏览器，失败则返回 None"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # 复用本地 Chrome 的用户数据，保留已有登录态
        # options.add_argument(f"user-data-dir={HERE / 'chrome_profile'}")
        driver = webdriver.Chrome(options=options)
        return driver
    except ImportError:
        print("[提示] 未安装 selenium，请运行: pip install selenium")
        return None
    except Exception as e:
        print(f"[提示] 浏览器启动失败: {e}")
        return None

def selenium_login(timeout=120):
    """
    弹出浏览器，等待用户手动登录 MOOC，然后自动保存 Cookie
    返回: cookie 字符串，失败返回 None
    """
    driver = _get_selenium_driver()
    if not driver:
        return None

    try:
        driver.get("https://www.icourse163.org/")
        print("\n" + "=" * 50)
        print("🌐 浏览器已打开，请手动登录 MOOC")
        print(f"   等待时间: {timeout} 秒")
        print("=" * 50)

        start = time.time()
        cookie_str = None

        while time.time() - start < timeout:
            time.sleep(2)
            cookies = driver.get_cookies()
            # 检查是否已登录（有 STUDY_SESS 说明已登录）
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            if "STUDY_SESS" in cookie_dict and "NTESSTUDYSI" in cookie_dict:
                # 拼接为 cookie 字符串
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies
                    if c["name"] in (
                        "NTESSTUDYSI", "STUDY_SESS", "STUDY_PERSIST",
                        "NTES_YD_SESS", "NTES_YD_PASSPORT", "STUDY_INFO",
                        "NETEASE_WDA_UID", "EDUWEBDEVICE", "WM_TID",
                        "WM_NI", "WM_NIKE", "__yadk_uid",
                    )
                )
                # 写入文件
                cookie_path = HERE / "config" / "cookie"
                cookie_path.write_text(cookie_str, encoding="utf-8")
                print("✅ 登录成功！Cookie 已自动保存到 config/cookie")
                break

        if not cookie_str:
            print("[超时] 未在限定时间内完成登录")

        return cookie_str

    finally:
        driver.quit()

# ========== 读取配置 ==========
def read_lines(filename):
    """读取配置文件，每行一个，过滤空行和注释"""
    path = HERE / "config" / filename
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
            if line.strip() and not line.strip().startswith('#')]

def read_cookie(auto_login=True):
    """读取 cookie 配置文件，如果没有则尝试自动登录"""
    path = HERE / "config" / "cookie"
    if path.exists():
        cookie_str = path.read_text(encoding='utf-8-sig').strip()
        if cookie_str and not cookie_str.startswith('#'):
            return cookie_str

    # Cookie 不存在或为空，尝试 Selenium 自动登录
    if auto_login:
        print("[提示] Cookie 未配置，尝试自动登录...")
        return selenium_login()
    return None

def ensure_cookie(session, csrf_key, auto_login=True):
    """
    确保 Cookie 有效。调用 API 测试，失败则重新登录。
    返回: (session, csrf_key) 或 (None, None)
    """
    # 先用 fast API 测试 Cookie 是否有效
    test_url = "https://www.icourse163.org/web/j/courseBean.getLastLearnedMocTermDto.rpc"
    try:
        resp = session.post(test_url,
            params={"csrfKey": csrf_key},
            data={"termId": "1476488478"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "edu-script-token": csrf_key,
            },
            timeout=10
        )
        # 如果返回正常 JSON 且 code=0，Cookie 有效
        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("code") == 0:
                    return True  # Cookie 有效
            except:
                pass
    except:
        pass

    # Cookie 失效，尝试重新登录
    if not auto_login:
        return False

    print("\n⚠ Cookie 已失效，正在重新登录...")
    new_cookie = selenium_login()
    if not new_cookie:
        return False

    # 用新 Cookie 重建 session
    new_cookies = build_cookies(new_cookie)
    new_csrf = new_cookies.get("NTESSTUDYSI", "")
    if not new_csrf:
        return False

    session.cookies.clear()
    session.cookies.update(new_cookies)
    # 更新外部 csrf_key（通过返回新值）
    return new_csrf

# ========== 调用 API ==========
API_URL = "https://www.icourse163.org/web/j/courseBean.getLastLearnedMocTermDto.rpc"

def get_course_data(session, term_id, csrf_key):
    """获取课程完整数据，失败返回 None"""
    params = {"csrfKey": csrf_key}
    data = {"termId": str(term_id)}
    try:
        resp = session.post(API_URL, params=params, data=data, timeout=15)
        # 检测是否被重定向到登录页
        if resp.status_code != 200 or "passport" in resp.url.lower():
            return "__AUTH_FAILED__"
        result = resp.json()
        if result.get("code") != 0:
            print(f"  [错误] API 返回: {result}")
            return None
        return result["result"]["mocTermDto"]
    except requests.exceptions.JSONDecodeError:
        return "__AUTH_FAILED__"
    except Exception as e:
        print(f"  [异常] {e}")
        return None
def parse_course_url(url):
    """
    从课程 URL 中提取 courseId 和 termId
    例如: https://www.icourse163.org/learn/NEU-1001638002?tid=1476488478
    返回: (courseId, termId)
    """
    # 匹配 /learn/XXX-数字?tid=数字
    m = re.search(r'/learn/\w+-(\d+)\?tid=(\d+)', url)
    if m:
        return m.group(1), m.group(2)
    return None, None

# ========== 构建请求头 ==========
def build_headers(csrf_key):
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "edu-script-token": csrf_key,
        "Referer": "https://www.icourse163.org/",
        "Origin": "https://www.icourse163.org",
    }

def build_cookies(cookie_str):
    """将 cookie 字符串转为字典"""
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, _, value = item.partition('=')
            cookies[key.strip()] = value.strip()
    return cookies

# ========== 解析作业/测验/考试 ==========
def ts_to_str(ts):
    """毫秒时间戳 → 日期字符串"""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

def parse_tasks(moc_data, course_name):
    """
    从课程数据中提取所有待完成任务
    返回: [(任务类型, 任务名, 截止时间, 分数/状态, 唯一ID), ...]
    """
    tasks = []

    for ch in moc_data.get("chapters", []):
        ch_name = ch.get("name", "")

        # 章节测验 (quizs)
        for q in (ch.get("quizs") or []):
            test = q.get("test") or {}
            task_id = f"quiz_{test.get('id', q['id'])}"
            deadline = ts_to_str(test["deadline"]) if test.get("deadline") else "无截止"
            score = f"{test.get('userScore', '?')}/{test.get('totalScore', '?')}"
            tasks.append((
                "章节测验",
                f"{ch_name} → {q['name']}",
                deadline,
                score,
                task_id
            ))

        # 章节作业 (homeworks)
        for hw in (ch.get("homeworks") or []):
            test = hw.get("test") or {}
            task_id = f"hw_{test.get('id', hw['id'])}"
            deadline = ts_to_str(test["deadline"]) if test.get("deadline") else "无截止"
            score = f"{test.get('userScore', '?')}/{test.get('totalScore', '?')}"
            used = test.get("usedTryCount", 0)
            max_try = test.get("trytime", "∞")
            tasks.append((
                "章节作业",
                f"{ch_name} → {hw['name']}",
                deadline,
                f"{score} (已提交{used}/{max_try}次)",
                task_id
            ))

            # 检查互评状态
            if test.get("enableEvaluation") and test.get("evaluateStart"):
                eval_start = ts_to_str(test["evaluateStart"])
                eval_end = ts_to_str(test["evaluateEnd"]) if test.get("evaluateEnd") else "?"
                tasks.append((
                    "⚠互评",
                    f"{ch_name} → {hw['name']} [互评]",
                    f"{eval_start} ~ {eval_end}",
                    "待互评" if test.get("evaluateJudgeType") != 2 else "已完成",
                    f"peer_{test.get('id', hw['id'])}"
                ))

        # 随堂测验 (units 中 contentType=5)
        for lesson in (ch.get("lessons") or []):
            for unit in (lesson.get("units") or []):
                if unit.get("contentType") == 5:
                    task_id = f"quizlet_{unit['id']}"
                    tasks.append((
                        "随堂测验",
                        f"{ch_name} → {lesson['name']} → {unit['name']}",
                        "无截止",
                        "未做" if unit.get("viewStatus", 0) == 0 else "已完成",
                        task_id
                    ))

        # 考试 (exam) - 在 chapter 级别
        exam = ch.get("exam")
        if exam:
            task_id = f"exam_{exam.get('id', '?')}"
            deadline = ts_to_str(exam["deadline"]) if exam.get("deadline") else "无截止"
            tasks.append((
                "📝考试",
                f"{ch_name} → {exam.get('name', '考试')}",
                deadline,
                f"{exam.get('userScore', '?')}/{exam.get('totalScore', '?')}",
                task_id
            ))

    return tasks

# ========== 状态追踪 & 变更对比 ==========
STATE_FILE = HERE / "log" / "task_state.json"

def load_state():
    """加载上次任务快照 {task_id: {type, name, score, status, deadline}}"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except:
            pass
    return {}

def save_state(tasks):
    """保存当前任务快照"""
    state = {}
    for task_type, task_name, deadline, status, task_id in tasks:
        state[task_id] = {
            "type": task_type,
            "name": task_name,
            "score": status,
            "deadline": deadline,
        }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def compare_state(old_state, tasks, ignore_set):
    """
    对比新旧状态，返回变更列表
    返回: [(标记, 任务类型, 任务名, 截止, 状态, 旧状态或空), ...]
    标记: 🆕新增 | 📊分数变化 | 🔄状态变化
    """
    changes = []
    for task_type, task_name, deadline, status, task_id in tasks:
        if task_type in ignore_set:
            continue

        if task_id not in old_state:
            changes.append(("🆕", task_type, task_name, deadline, status, ""))
        else:
            old = old_state[task_id]
            # 提取分数部分做对比
            old_score = _extract_score(old.get("score", ""))
            new_score = _extract_score(status)
            old_rest = _extract_rest(old.get("score", ""))
            new_rest = _extract_rest(status)

            if old_score != new_score and old_score is not None and new_score is not None:
                changes.append(("📊", task_type, task_name, deadline,
                               status, old.get("score", "")))
            elif old_rest != new_rest:
                changes.append(("🔄", task_type, task_name, deadline,
                               status, old.get("score", "")))

    return changes

def _extract_score(status_str):
    """从状态字符串中提取分数: '50.0/50.0' → (50.0, 50.0)"""
    import re as _re
    m = _re.search(r'([\d.]+)/([\d.]+)', status_str)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    return None

def _extract_rest(status_str):
    """提取分数以外的部分，如 '(已提交1/2次)' """
    import re as _re
    return _re.sub(r'[\d.]+/[\d.]+', '', status_str).strip()

# ========== 通知推送 ==========
def load_notify_config():
    """读取通知配置"""
    lines = read_lines("notify")
    config = {"to": [], "smtp_server": "smtp.qq.com", "smtp_port": "465"}
    for line in lines:
        if "=" in line:
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key == "to":
                config["to"].append(val)
            else:
                config[key] = val
    return config

def send_email(config, subject, body):
    """通过 SMTP 发送邮件通知"""
    sender = config.get("sender", "")
    password = config.get("password", "")
    recipients = config.get("to", [])

    if not sender or not password or not recipients:
        print("  [通知] 邮件配置不完整，跳过发送")
        return False

    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg.set_content(body, subtype="plain", charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        smtp_server = config.get("smtp_server", "smtp.qq.com")
        smtp_port = int(config.get("smtp_port", "465"))

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender, password)
            server.send_message(msg)

        print(f"  [通知] 邮件已发送 → {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"  [通知] 发送失败: {e}")
        return False

def send_notification(changes, ignore_set):
    """有变更时发送通知"""
    cfg = load_notify_config()
    if not cfg.get("sender"):
        return

    # 过滤掉忽略类型
    important = [c for c in changes if c[1] not in ignore_set]
    if not important:
        return

    now = datetime.now().strftime('%m-%d %H:%M')
    lines = [f"MOOC 作业变更通知 - {now}", "=" * 30, ""]
    for flag, ttype, name, deadline, status, old in important:
        if flag == "🆕":
            lines.append(f"🆕 [{ttype}] {name}")
            lines.append(f"   截止: {deadline}  |  {status}")
        elif flag == "📊":
            lines.append(f"📊 [{ttype}] {name}")
            lines.append(f"   分数变更: {old} → {status}")
        elif flag == "🔄":
            lines.append(f"🔄 [{ttype}] {name}")
            lines.append(f"   状态变更: {old} → {status}")
        lines.append("")

    body = "\n".join(lines)
    # 用简单标题，避免 emoji 编码问题
    flags = [c[0] for c in important[:3]]
    flag_text = " ".join(flags)
    subject = f"MOOC {flag_text} ({len(important)}项变更)"
    send_email(cfg, subject, body)

# ========== 去重 & 输出 ==========
def load_done():
    """读取已完成/已通知的任务 ID 集合"""
    path = HERE / "log" / "doneTask"
    if not path.exists():
        return set()
    return set(line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip())

def load_ignore():
    """读取忽略的任务类型（如：随堂测验）"""
    ignore_types = read_lines("ignore")
    return set(ignore_types)

def save_done(task_ids):
    """追加新的任务 ID 到 doneTask"""
    path = HERE / "log" / "doneTask"
    with path.open('a', encoding='utf-8') as f:
        for tid in task_ids:
            f.write(tid + '\n')

def save_result(lines, filename="checkresult"):
    """追加检测结果到日志文件"""
    path = HERE / "log" / filename
    with path.open('a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        for line in lines:
            f.write(line + '\n')

# ========== 主流程 ==========
def main():
    print("=" * 50)
    print(f"MOOC 作业检测系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 读取 Cookie（没有则自动弹出浏览器登录）
    cookie_str = read_cookie(auto_login=True)
    if not cookie_str:
        print("[错误] 无法获取 Cookie，退出")
        return

    cookies = build_cookies(cookie_str)
    csrf_key = cookies.get("NTESSTUDYSI", "")
    if not csrf_key:
        print("[错误] Cookie 中未找到 NTESSTUDYSI，请检查")
        return

    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v)

    # 2. 读取课程列表
    course_urls = read_lines("aimLesson")
    if not course_urls:
        print("[警告] config/aimLesson 为空，请添加课程 URL")
        return

    done_set = load_done()
    ignore_set = load_ignore()
    old_state = load_state()
    all_new_lines = []
    important_lines = []
    new_task_ids = []
    all_tasks = []  # 用于保存完整快照
    all_changes = []  # 变更列表

    if ignore_set:
        print(f"[忽略] 已忽略类型: {', '.join(sorted(ignore_set))}")

    # 3. 遍历每门课
    for course_url in course_urls:
        course_id, term_id = parse_course_url(course_url)
        if not course_id or not term_id:
            print(f"[跳过] 无法解析 URL: {course_url}")
            continue

        print(f"\n📖 正在检查: {course_url}")
        print(f"   courseId={course_id}, termId={term_id}")

        moc_data = get_course_data(session, term_id, csrf_key)

        # Cookie 过期 → 自动重新登录 → 重试一次
        if moc_data == "__AUTH_FAILED__":
            new_csrf = ensure_cookie(session, csrf_key)
            if isinstance(new_csrf, str) and new_csrf:
                csrf_key = new_csrf
                print("   已重新登录，重试获取课程数据...")
                moc_data = get_course_data(session, term_id, csrf_key)
            else:
                print("   [错误] 重新登录失败，跳过此课程")
                continue

        if not moc_data or moc_data == "__AUTH_FAILED__":
            continue

        course_name = moc_data.get("courseName", "未知课程")
        end_time = ts_to_str(moc_data["endTime"]) if moc_data.get("endTime") else "未知"
        print(f"   课程名: {course_name}")
        print(f"   结课时间: {end_time}")

        tasks = parse_tasks(moc_data, course_name)
        all_tasks.extend(tasks)

        print(f"\n   {'类型':<8} {'任务名':<40} {'截止时间':<22} {'状态/分数'}")
        print(f"   {'-'*8} {'-'*40} {'-'*22} {'-'*15}")

        for task_type, task_name, deadline, status, task_id in tasks:
            is_new = task_id not in done_set
            is_ignored = task_type in ignore_set

            # 检查状态变更
            old = old_state.get(task_id, {})
            change_flag = ""
            if old:
                old_status = old.get("score", "")
                if _extract_score(old_status) != _extract_score(status) and \
                   _extract_score(old_status) is not None and _extract_score(status) is not None:
                    change_flag = " 📊"
                elif _extract_rest(old_status) != _extract_rest(status):
                    change_flag = " 🔄"

            flag = "🆕" if is_new else ("  ")
            ignore_mark = " [忽略]" if (is_new and is_ignored) else ""
            print(f" {flag} {task_type:<6} {task_name[:38]:<40} {deadline:<22} {status}{ignore_mark}{change_flag}")

            if is_new:
                line = f"[{task_type}] {task_name} | 截止: {deadline} | {status}"
                all_new_lines.append(line)
                new_task_ids.append(task_id)
                if not is_ignored:
                    important_lines.append(line)

    # 5. 完整对比变更
    all_changes = compare_state(old_state, all_tasks, ignore_set)
    changes_new = [c for c in all_changes if c[0] == "🆕"]
    changes_score = [c for c in all_changes if c[0] == "📊"]
    changes_status = [c for c in all_changes if c[0] == "🔄"]
    total_changes = len(all_changes)

    # 6. 汇总输出
    if total_changes > 0:
        print(f"\n{'='*50}")
        print(f"📋 变更汇总: 🆕{len(changes_new)}  📊{len(changes_score)}  🔄{len(changes_status)}")

        if changes_score:
            print(f"\n  📊 分数变化:")
            for _, ttype, name, deadline, status, old in changes_score:
                print(f"     [{ttype}] {name[:50]}")
                print(f"      {old} → {status}")

        if changes_status:
            print(f"\n  🔄 状态变化:")
            for _, ttype, name, deadline, status, old in changes_status:
                print(f"     [{ttype}] {name[:50]}")
                print(f"      {old} → {status}")

        if changes_new:
            print(f"\n  🆕 新增任务:")
            for _, ttype, name, deadline, status, old in changes_new:
                print(f"     [{ttype}] {name[:50]} | 截止: {deadline}")

        # 保存各类日志
        if all_new_lines:
            save_result(all_new_lines, "checkresult")
        if important_lines:
            save_result(important_lines, "important")

        # 变更日志
        change_lines = []
        for flag, ttype, name, deadline, status, old in all_changes:
            if flag == "🆕":
                change_lines.append(f"🆕 [{ttype}] {name} | 截止:{deadline} | {status}")
            elif flag == "📊":
                change_lines.append(f"📊 [{ttype}] {name} | 分数: {old} → {status}")
            elif flag == "🔄":
                change_lines.append(f"🔄 [{ttype}] {name} | 状态: {old} → {status}")
        if change_lines:
            save_result(change_lines, "change_log")

        save_done(new_task_ids)
        save_state(all_tasks)

        # 发送通知
        print(f"\n📧 发送通知...")
        send_notification(all_changes, ignore_set)

    else:
        print(f"\n✅ 没有变更，一切正常")
        save_state(all_tasks)

    print(f"\n日志: checkresult | important | change_log | task_state.json")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"MOOC检测异常: {e}", e)
        print(f"\n[错误] {e}，详情见 log/error")
        raise


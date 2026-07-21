"""
NEU 数学机考选位监控 - 检测目标机房是否开放选位
重构自 NEUseathero PowerShell 脚本，改用 Python 网络请求
"""
import requests
from pathlib import Path
import json
import time
import random
import traceback
from datetime import datetime

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

# ========== 配置 ==========
def read_config(filename):
    """读取键值对配置"""
    path = HERE / "config" / filename
    if not path.exists():
        return {}
    config = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, _, v = line.partition('=')
            config[k.strip()] = v.strip()
    return config

def load_cookies():
    """从配置文件加载 Cookie（兼容旧格式）"""
    cfg = read_config("mathe_auth")
    cookies = {}
    if "JSESSIONID" in cfg:
        cookies["JSESSIONID"] = cfg["JSESSIONID"]
    if "vuex" in cfg:
        cookies["vuex"] = cfg["vuex"]
    return cookies, cfg.get("token", "")

# ========== 自动登录 ==========
def mathe_login(session):
    """
    通过用户名密码自动登录，获取 token
    返回: token 字符串，失败返回 None
    """
    cfg = read_config("mathe_auth")
    username = cfg.get("username", "")
    real_password = cfg.get("real_password", "")

    if not username or not real_password:
        print("[错误] config/mathe_auth 未配置 username 和 real_password")
        return None

    # 先访问首页获取 JSESSIONID
    try:
        session.get(f"{BASE_URL}/login", headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
    except:
        pass

    # MD5 加密密码
    import hashlib
    md5_pwd = hashlib.md5(real_password.encode()).hexdigest()

    # 登录
    login_data = {
        "username": username,
        "password": md5_pwd,
        "real_password": real_password,
    }
    result = api_post(session, "/api/auth/login", login_data)
    if not result or result.get("code") != 0:
        print(f"  [登录失败] {result}")
        return None

    token = result["data"]["token"]
    name = result["data"].get("name", username)

    # 设置 vuex cookie
    vuex_obj = {
        "loginStatus": {
            "username": username,
            "loginStatus": True,
            "token": token,
            "name": name,
            "focusChangePassword": False,
            "isAdmin": False,
            "firstLogin": False,
        }
    }
    vuex_str = json.dumps(vuex_obj, separators=(',', ':'))
    session.cookies.set("vuex", vuex_str, domain="mathe.neu.edu.cn")

    print(f"  登录成功: {name} ({username})")
    return token

# ========== API 调用 ==========
BASE_URL = "http://mathe.neu.edu.cn:8080"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/main/xkxt",
}

def api_post(session, path, data):
    """统一 POST 请求"""
    try:
        resp = session.post(f"{BASE_URL}{path}", json=data, headers=HEADERS, timeout=10)
        result = resp.json()
        return result
    except Exception as e:
        print(f"  [API错误] {path}: {e}")
        return None

def get_dates(session, token, paper_id):
    """获取可选日期"""
    result = api_post(session, "/api/v2/reserve/dates",
                      {"token": token, "paper_id": paper_id})
    if result and result.get("code") == 0:
        return result["data"]
    return []

def get_rooms(session, token, date_id):
    """获取可选机房"""
    result = api_post(session, "/api/v2/reserve/rooms",
                      {"token": token, "date_id": date_id})
    if result and result.get("code") == 0:
        return result["data"]
    return []

def get_seats(session, token, date_id, room_id, paper_id="", round_id=None):
    """查询余座"""
    data = {"token": token, "date_id": date_id, "room_id": room_id}
    if round_id:
        data["round_id"] = round_id
    if paper_id:
        data["paper_id"] = paper_id
    result = api_post(session, "/api/v2/reserve/seats", data)
    if result and result.get("code") == 0:
        return result["data"].get("seats", 0)
    return None

# ========== 状态追踪 & 变更对比 ==========
STATE_FILE = HERE / "log" / "mathe_state.json"
CHANGE_LOG = HERE / "log" / "mathe_change"

def load_state():
    """加载上次扫描快照"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except:
            pass
    return {}

def save_state(current_data):
    """保存当前快照"""
    STATE_FILE.write_text(json.dumps(current_data, ensure_ascii=False, indent=2), encoding='utf-8')

def save_change_log(lines):
    """追加变更日志"""
    with CHANGE_LOG.open('a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*50}\n")
        for line in lines:
            f.write(line + '\n')

def compare_state(old_state, current_rooms):
    """
    对比新旧状态
    old_state: {"日期_机房ID": {"name":..., "seats":..., "date":...}, ...}
    current_rooms: [{"room_name":..., "room_id":..., ...}, ...]
    返回: (new_rooms, changed_rooms, gone_rooms)
    """
    # 构建当前状态的 key → 信息映射
    current_map = {}
    for room in current_rooms:
        key = f"{room['date_id']}_{room['room_id']}"
        current_map[key] = {
            "name": room["room_name"],
            "date_str": room["date_str"],
            "date_id": room["date_id"],
            "room_id": room["room_id"],
            "seats": room["seats"],
        }

    new_rooms = []       # 新增的
    changed_rooms = []   # 余座变化的
    gone_rooms = []      # 消失的（之前有现在没了）

    # 检查新增和变化
    for key, info in current_map.items():
        if key not in old_state:
            new_rooms.append(info)
        else:
            old_info = old_state[key]
            if str(old_info.get("seats")) != str(info["seats"]):
                info["old_seats"] = old_info.get("seats", "?")
                changed_rooms.append(info)

    # 检查消失的
    for key, old_info in old_state.items():
        if key not in current_map:
            gone_rooms.append(old_info)

    return new_rooms, changed_rooms, gone_rooms

# ========== 通知（复用现有 SMTP） ==========
def send_notification(new_rooms, changed_rooms, gone_rooms, target_keywords):
    """发送变更通知"""
    notify_cfg = read_config("notify")
    sender = notify_cfg.get("sender", "")
    password = notify_cfg.get("password", "")
    recipients = notify_cfg.get("to", [])
    if isinstance(recipients, str):
        recipients = [recipients]
    if not sender or not password:
        return

    now = datetime.now().strftime("%m-%d %H:%M")
    total = len(new_rooms) + len(changed_rooms) + len(gone_rooms)
    lines = [f"NEU选位变更 - {now}", "=" * 30, "",
             f"目标: {', '.join(target_keywords)}", f"变更: {total} 项", ""]

    if new_rooms:
        lines.append("🆕 新增机房:")
        for r in new_rooms:
            lines.append(f"  {r['date_str']} | {r['name']} | 余座:{r['seats']}")
        lines.append("")

    if changed_rooms:
        lines.append("📊 余座变化:")
        for r in changed_rooms:
            lines.append(f"  {r['date_str']} | {r['name']} | {r['old_seats']} → {r['seats']}")
        lines.append("")

    if gone_rooms:
        lines.append("❌ 机房消失:")
        for r in gone_rooms:
            lines.append(f"  {r.get('date_str','')} | {r.get('name','')}")
        lines.append("")

    body = "\n".join(lines)
    subject = f"NEU选位 [{now}] 🆕{len(new_rooms)} 📊{len(changed_rooms)} ❌{len(gone_rooms)}"

    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg.set_content(body, subtype="plain", charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        smtp_server = notify_cfg.get("smtp_server", "smtp.qq.com")
        smtp_port = int(notify_cfg.get("smtp_port", "465"))
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"  [通知] 邮件已发送 → {', '.join(recipients)}")
    except Exception as e:
        print(f"  [通知] 发送失败: {e}")

# ========== 主流程 ==========
def main():
    print("=" * 50)
    print(f"NEU 数学机考选位监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 自动登录
    session = requests.Session()
    token = mathe_login(session)
    if not token:
        return

    target_cfg = read_config("mathe_target")
    paper_id = target_cfg.get("paper_id", "")
    target_keywords = [k.strip() for k in target_cfg.get("keywords", "南湖计算中心").split(",")]
    if not paper_id:
        print("[错误] config/mathe_target 未配置 paper_id")
        return

    min_interval = int(target_cfg.get("min_interval", "60"))
    max_interval = int(target_cfg.get("max_interval", "120"))
    cooldown_minutes = int(target_cfg.get("cooldown", "10"))

    print(f"   试卷ID: {paper_id}")
    print(f"   目标关键词: {target_keywords}")
    print(f"   间隔: {min_interval}-{max_interval}s  冷却: {cooldown_minutes}min")

    old_state = load_state()
    last_notify_time = 0

    try:
        while True:
            try:
                now_ts = datetime.now().timestamp()
                ts_str = datetime.now().strftime('%H:%M:%S')
                print(f"\n[{ts_str}] 扫描中...")

            dates = get_dates(session, token, paper_id)
            if not dates:
                print("  [无日期] 暂未开放或Token过期")
                wait = random.randint(min_interval, max_interval)
                next_time = datetime.now().timestamp() + wait
                print(f"  下次扫描: {datetime.fromtimestamp(next_time).strftime('%H:%M:%S')}")
                time.sleep(wait)
                continue

            print(f"  可选日期: {len(dates)} 个")

            # 遍历所有日期查机房
            current_rooms = []
            for date_item in dates:
                date_id = date_item["date_id"]
                date_ts = date_item["date"]
                date_str = datetime.fromtimestamp(date_ts / 1000).strftime("%m-%d")

                rooms = get_rooms(session, token, date_id)
                for room in rooms:
                    room_name = room["room_name"]
                    if any(kw in room_name for kw in target_keywords):
                        seats = get_seats(session, token, date_id, room["room_id"],
                                         paper_id=paper_id)
                        current_rooms.append({
                            "room_name": room_name,
                            "room_id": room["room_id"],
                            "date_id": date_id,
                            "date_str": date_str,
                            "seats": seats if seats is not None else "?",
                        })

            # 对比变更
            new_rooms, changed_rooms, gone_rooms = compare_state(old_state, current_rooms)

            # 构建新快照
            new_state = {}
            for r in current_rooms:
                key = f"{r['date_id']}_{r['room_id']}"
                new_state[key] = {
                    "name": r["room_name"],
                    "date_str": r["date_str"],
                    "date_id": r["date_id"],
                    "room_id": r["room_id"],
                    "seats": r["seats"],
                }

            total_changes = len(new_rooms) + len(changed_rooms) + len(gone_rooms)

            # 显示当前状态
            if current_rooms:
                print(f"  目标机房: {len(current_rooms)} 个")
                for r in current_rooms:
                    print(f"    {r['date_str']} | {r['room_name']} | 余座:{r['seats']}")
            else:
                print(f"  暂未发现目标机房")

            if total_changes == 0 and old_state:
                print(f"  [无变更]")
                save_state(new_state)
                old_state = new_state
                wait = random.randint(min_interval, max_interval)
                next_time = datetime.now().timestamp() + wait
                print(f"  下次扫描: {datetime.fromtimestamp(next_time).strftime('%H:%M:%S')}")
                time.sleep(wait)
                continue

            # 有变更
            print(f"\n  变更: 🆕{len(new_rooms)} 📊{len(changed_rooms)} ❌{len(gone_rooms)}")

            change_lines = []
            for r in new_rooms:
                line = f"🆕 [{r['date_str']}] {r['name']} | 余座:{r['seats']}"
                print(f"    {line}")
                change_lines.append(line)
            for r in changed_rooms:
                line = f"📊 [{r['date_str']}] {r['name']} | {r['old_seats']} → {r['seats']}"
                print(f"    {line}")
                change_lines.append(line)
            for r in gone_rooms:
                line = f"❌ [{r.get('date_str','')}] {r.get('name','')}"
                print(f"    {line}")
                change_lines.append(line)

            # 通知（冷却期内也记录日志但不发邮件）
            cooldown_seconds = cooldown_minutes * 60
            if now_ts - last_notify_time > cooldown_seconds:
                send_notification(new_rooms, changed_rooms, gone_rooms, target_keywords)
                last_notify_time = now_ts

            save_change_log(change_lines)
            save_state(new_state)
            old_state = new_state

            # 随机间隔
            wait = random.randint(min_interval, max_interval)
            if random.random() < 0.05:
                print(f"  [跳过] 本轮休息")
                wait += random.randint(30, 60)
            next_time = datetime.now().timestamp() + wait
            print(f"  下次扫描: {datetime.fromtimestamp(next_time).strftime('%H:%M:%S')}")
            time.sleep(wait)

            except Exception as e:
                print(f"  [异常] {e}")
                log_error(f"扫描异常: {e}", e)
                time.sleep(30)  # 异常后等30秒再继续

    except KeyboardInterrupt:
        print("\n[停止] 监控已退出")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"选位监控异常: {e}", e)
        print(f"\n[错误] {e}，详情见 log/error")
        raise
